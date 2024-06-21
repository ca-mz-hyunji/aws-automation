import boto3
import logging
import json
import os
import urllib3
from datetime import datetime, timedelta, timezone
import base64


#########################################################
### cleint information
#########################################################
ACCOUNT_LIST = [
    {
        "account_id": "700736432587",
        "account_name": "hma-gita-qa",
        "account_env": "QA",
        "customer_name": "HAEA",
        "customer_project": "HAEA GITA 1st",
        "region": "us-west-2"
    },
    {
        "account_id": "358269447795",
        "account_name": "hma-gita-stg",
        "account_env": "STG",
        "customer_name": "HAEA",
        "customer_project": "HAEA GITA 1st",
        "region": "us-west-2"
    },
    {
        "account_id": "696796209136",
        "account_name": "hma-gita-prd",
        "account_env": "PRD",
        "customer_name": "HAEA",
        "customer_project": "HAEA GITA 1st",
        "region": "us-west-2"
    }
]


def assume_role(account):
    try:
        sts_client = boto3.client('sts')
        credential=sts_client.assume_role(
            RoleArn=f"arn:aws:iam::{account['account_id']}:role/mzc-aws-managed-onboarding-role",
            RoleSessionName=account['account_id'],
            ExternalId="duolCenozageM"
        ).get('Credentials')

        session = boto3.Session(
                aws_access_key_id = credential['AccessKeyId'],
                aws_secret_access_key = credential['SecretAccessKey'],
                aws_session_token = credential['SessionToken']
        )
        logger.info(f'Session Connect Success. Account : {account['account_id']}')
        return session
    except Exception as e:
        return logger.error(f'[{account['account_id']}:ERROR] Session Connect Failed. event fallow:\n{e}')
#############################################################

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Atlassian configuration
BASE_URL = os.environ.get('BASE_URL') # https://mzdevs.atlassian.net/rest/api/2
USERNAME = os.environ.get('USERNAME')
API_TOKEN = os.environ.get('API_TOKEN')
# Jira configuration
JIRA_PROJECT_KEY = os.environ.get('JIRA_PROJECT_KEY')
JIRA_ISSUE_TYPE = "Task"
JIRA_SYSTEM_ACCOUNT = "62a27c8ad442e6006842fa57"
# Confluence configuration
CONFLUENCE_SPACE_KEY = 'YOUR_SPACE_KEY'
CONFLUENCE_PARENT_PAGE_ID = 'YOUR_PARENT_PAGE_ID'


http = urllib3.PoolManager()

def check_aws_backup_jobs(session):
    """
    Check the status of AWS Backup jobs from the last 24 hours.
    """
    backup_client = session.client('backup')
    
    # Get the current time and calculate the time 24 hours ago
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=1)
    
    # Convert to ISO 8601 format
    start_time_str = start_time.isoformat() + 'Z'
    end_time_str = end_time.isoformat() + 'Z'
    
    paginator = backup_client.get_paginator('list_backup_jobs')
    
    response_iterator = paginator.paginate(
        ByCreatedAfter=start_time_str,
        ByCreatedBefore=end_time_str,
        PaginationConfig={'PageSize': 100}
    )
    
    issues = []
    targets = []
    for response in response_iterator:
        for job in response['BackupJobs']:
            job_status = job['State']
            resource_name = job['ResourceArn']
            backup_vault_name = job['BackupVaultName']
            
            if job_status != 'COMPLETED':
                issues.append(f"Backup issue: {resource_name} in vault {backup_vault_name} is in {job_status} state.")
            
            targets.append(f"Backup target: {resource_name} in vault {backup_vault_name} is in {job_status} state.")
    
    return issues, targets, len(targets)-len(issues)


def check_rds_snapshots(session):
    """
    Check the status of RDS automated snapshots from the last 24 hours.
    """
    rds_client = session.client('rds')
    
    # Get the current time and calculate the time 24 hours ago
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=1)
    
    response = rds_client.describe_db_snapshots(SnapshotType='automated')
    
    issues = []
    targets = []
    for snapshot in response['DBSnapshots']:
        snapshot_id = snapshot['DBSnapshotIdentifier']
        instance_id = snapshot['DBInstanceIdentifier']
        snapshot_status = snapshot['Status']
        snapshot_create_time = snapshot['SnapshotCreateTime']
        
        # Check if the snapshot was created in the last 24 hours
        if snapshot_create_time > start_time:
            if snapshot_status != 'available':
                issues.append(f"RDS Snapshot issue: {snapshot_id} for instance {instance_id} is in {snapshot_status} state.")
            
            targets.append(f"RDS Snapshot: {snapshot_id} for instance {instance_id} is in {snapshot_status} state.")
    
    return issues, targets, len(targets)-len(issues)


def check_cloudwatch_alarms(session):
    """
    Check the status of CloudWatch alarms.
    """
    cloudwatch_client = session.client('cloudwatch')
    
    issues = []
    targets = []
    next_token = None

    while True:
        if next_token:
            response = cloudwatch_client.describe_alarms(NextToken=next_token)
        else:
            response = cloudwatch_client.describe_alarms()
        
        for alarm in response['MetricAlarms']:
            alarm_name = alarm['AlarmName']
            alarm_state = alarm['StateValue']
            
            # Exclude alarms related to Auto Scaling Groups
            if '-asg-' not in alarm_name.lower() and 'AWS-MZC-' in alarm_name:
                if alarm_state == 'ALARM':
                    issues.append(f"CloudWatch Alarm issue: {alarm_name} is in ALARM state.")
                
                targets.append(f"CloudWatch Alarm: {alarm_name} is in {alarm_state} state.")
        
        next_token = response.get('NextToken')
        if not next_token:
            break
    
    return issues, targets, len(targets)-len(issues)


def create_jira_issue(summary, description):
    """
    Create an issue in Jira Service Management.
    """
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + base64.b64encode((USERNAME + ':' + API_TOKEN).encode('utf-8')).decode('utf-8')
    }
    payload = {
        "fields": {
            "project": {
                "key": JIRA_PROJECT_KEY
            },
            "summary": summary,
            "description": description,
            "issuetype": {
                "name": JIRA_ISSUE_TYPE
            },
            'reporter': {
                'accountId': JIRA_SYSTEM_ACCOUNT
            }
        }
    }
    response = http.request('POST', BASE_URL+"/rest/api/2/issue", body=json.dumps(payload), headers=headers)
    if response.status != 201:
        logger.error(f'Failed to create Jira ticket: {response.data}')
    else:
        logger.info(f'Successfully created Jira ticket for task: {summary}')


def lambda_handler(event, context):
    """
    Lambda function entry point for daily checkup of AWS Backup, RDS snapshots, and CloudWatch alarms across multiple accounts.
    """
    today = datetime.now().strftime('%Y-%m-%d')
    title = f"Daily Checkup Report for {today}"
    logger.info(f'Starting daily checkup for {today}...')
    
    report = [f"*[{title}]*\n"]
    summary = []
    all_backup_issues = []
    all_alarm_issues = []
    all_targets = []

    backup_target_num = []
    rds_target_num = []
    cw_target_num = []
    
    total_backup_issues_count = 0
    total_alarm_issues_count = 0
    
    for account in ACCOUNT_LIST:
        logger.info(f"Checking account {account['account_id']}...")
        
        # Assume role in target account
        session = assume_role(account)
        
        # Check AWS Backup jobs
        backup_issues, backup_targets, backup_completed = check_aws_backup_jobs(session)
        # Check RDS snapshots
        rds_issues, rds_targets, rds_completed = check_rds_snapshots(session)
        # Check CloudWatch alarms
        cw_issues, cw_targets, cw_completed = check_cloudwatch_alarms(session)
        
        # Combine issues and targets
        account_backup_issues = backup_issues + rds_issues
        # account_targets = backup_targets + rds_targets + cw_targets

        backup_target_num.append((account["account_name"], len(backup_targets), backup_completed)) 
        rds_target_num.append((account["account_name"], len(rds_targets), rds_completed))
        cw_target_num.append((account["account_name"], len(cw_targets), cw_completed))
        
        if account_backup_issues:
            account_summary = f"Backup issues found in account {account['account_id']}: {len(account_backup_issues)} issues"
            summary.append(account_summary)
            total_backup_issues_count += len(account_backup_issues)
            all_backup_issues.extend(sorted(account_backup_issues))

        if cw_issues:
            account_summary = f"Alarms found in account {account['account_id']}: {len(cw_issues)} issues"
            summary.append(account_summary)
            total_alarm_issues_count += len(cw_issues)
            all_alarm_issues.extend(sorted(cw_issues))
        
        # all_targets.extend(sorted(account_targets))
    
    report.append("=" * 80)
    report.append("Checkup Backups and Alarams")
    report.append("=" * 80)

    report.append("AWS Backup Jobs Check")
    for item in backup_target_num:
        report.append(f"- *{item[0]}* is *{item[2]} completed out of {item[1]}*")
    
    report.append("\nRDS Automated Backup Check\n")
    for item in rds_target_num:
        report.append(f"- *{item[0]}* is *{item[2]} completed out of {item[1]}*")

    report.append("\nCloudWatch Alarms State Check\n")
    for item in cw_target_num:
        report.append(f"- *{item[0]}* is *{item[2]} OK state out of {item[1]}*")
    
    # Compile the report
    if all_backup_issues:
        report.append(f"\nSummary of Backup Issues ({total_backup_issues_count} issues found)\n")
        report.extend([f"- {item}" for item in summary])

        report.append("\nDetailed Backup Issues\n")
        report.extend([f"- {issue}" for issue in all_backup_issues])

    if all_alarm_issues:
        report.append(f"\nSummary of Alarm Issues ({total_alarm_issues_count} issues found)\n")
        report.extend([f"- {item}" for item in summary])

        report.append("\nDetailed Alarm Issues\n")
        report.extend([f"- {issue}" for issue in all_alarm_issues])
    
    # report.append("### All Backup Targets")
    # report.extend([f"- {target}" for target in all_targets])
    
    report.append("\n-----")
    report.append("Comment:\n")

    # Create Jira issue if any issues are found
    if all_backup_issues or all_alarm_issues:
        create_jira_issue(title, "\n".join(report))
    else:
        report.append(f"*No issues found during the checkup on {today}.*")
        create_jira_issue(title, "\n".join(report))
    
    logger.info("Daily checkup completed.")
    
    return {
        'statusCode': 200,
        'body': 'Daily checkup completed successfully'
    }
