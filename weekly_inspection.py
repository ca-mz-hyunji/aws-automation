import boto3
import json
import logging
import os
import urllib3
import base64
from datetime import datetime, timedelta


#########################################################
##### cleint information
#########################################################
ACCOUNT_LIST = [
    {
        "account_id": "696796209136",
        "account_name": "hma-gita-prd",
        "account_env": "PRD",
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
        "account_id": "700736432587",
        "account_name": "hma-gita-qa",
        "account_env": "QA",
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
BASE_URL = os.environ.get('BASE_URL') # https://mzdevs.atlassian.net
USERNAME = os.environ.get('USERNAME')
API_TOKEN = os.environ.get('API_TOKEN')
# Jira configuration
JIRA_PROJECT_KEY = os.environ.get('JIRA_PROJECT_KEY')
JIRA_ISSUE_TYPE = "Task"
JIRA_SYSTEM_ACCOUNT = "62a27c8ad442e6006842fa57"
# Confluence configuration
CONFLUENCE_SPACE_ID =  os.environ.get('CONFLUENCE_SPACE_ID')
CONFLUENCE_PARENT_PAGE_ID =  os.environ.get('CONFLUENCE_PARENT_PAGE_ID')

http = urllib3.PoolManager()

# Initialize AWS clients
s3_client = boto3.client('s3')
ec2_client = ""
cloudwatch_client = ""
iam_client = ""
health_client = ""

# S3 bucket name
S3_BUCKET = 'mzc-weekly-inspection-states'

def create_confluence_page(title, content):
    url = f'{BASE_URL}/wiki/api/v2/pages'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + base64.b64encode(f"{USERNAME}:{API_TOKEN}".encode()).decode()
    }
    payload = json.dumps( 
        {
        "spaceId": CONFLUENCE_SPACE_ID,
        "status": "current",
        "title": title,
        "parentId": CONFLUENCE_PARENT_PAGE_ID,
        "body": {
            "representation": "storage",
            "value": content
            }
        } 
    )

    response = http.request('POST', url, body=payload, headers=headers)
    if response.status != 200:
        logger.error(f"Failed to create Confluence page: {response.data.decode('utf-8')}")
    else:
        response_data = json.loads(response.data.decode('utf-8'))
        logger.info(f"Confluence page created successfully: {response_data['id']}")
        link = f"Confluence Page: {response_data['_links']['base']}{response_data['_links']['webui']}"
        return link

def create_jira_task(summary, description):
    url = f"{BASE_URL}/rest/api/2/issue"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + base64.b64encode((USERNAME + ':' + API_TOKEN).encode('utf-8')).decode('utf-8')
    }
    payload = json.dumps(
        {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": summary,
            "description": description,
            "issuetype": {"name": JIRA_ISSUE_TYPE},
            'reporter': {'accountId': JIRA_SYSTEM_ACCOUNT}
            }
        }
    )
    response = http.request('POST', url, body=payload, headers=headers)
    
    if response.status != 201:
        print(f"Failed to create Jira task: {response.data.decode('utf-8')}")
    else:
        response_data = json.loads(response.data.decode('utf-8'))
        print(f"Jira task created successfully: {response_data['key']}")

def get_previous_state(task_name, account_id):
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=f'{account_id}/{task_name}.json')
        state = json.loads(response['Body'].read().decode('utf-8'))
    except s3_client.exceptions.NoSuchKey:
        state = {}
    return state

def update_state(task_name, state, account_id):
    s3_client.put_object(Bucket=S3_BUCKET, Key=f'{account_id}/{task_name}.json', Body=json.dumps(state))


def get_iam_roles_policies():
    roles = iam_client.list_roles()['Roles']
    roles_policies = []
    for role in roles:
        role_name = role['RoleName']
        attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)['AttachedPolicies']
        policies = [policy['PolicyName'] for policy in attached_policies]
        roles_policies.append({'RoleName': role_name, 'Policies': policies})
    return roles_policies


def describe_instances():
    instances = ec2_client.describe_instances()
    instance_details = []
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            instance_details.append({
                'InstanceId': instance['InstanceId'],
                'InstanceType': instance['InstanceType'],
                'State': instance['State']['Name'],
                'LaunchTime': instance['LaunchTime'].strftime("%Y-%m-%dT%H:%M:%S")
            })
    return instance_details

def describe_alarms():
    alarms = cloudwatch_client.describe_alarms()
    alarm_details = []
    for alarm in alarms['MetricAlarms']:
        if alarm['AlarmName'].startswith('AWS-MZC') and '-asg-' not in alarm['AlarmName'] and alarm['StateValue'] != 'INSUFFICIENT_DATA':
            alarm_details.append({
                'AlarmName': alarm['AlarmName'],
                'State': alarm['StateValue'],
                'MetricName': alarm['MetricName'],
                'Namespace': alarm['Namespace'],
                'EvaluationPeriods': alarm['EvaluationPeriods'],
                'Threshold': alarm['Threshold']
            })
    return alarm_details

def list_services_in_region(session, region_name):
    client = session.client('resourcegroupstaggingapi', region_name=region_name)
    paginator = client.get_paginator('get_resources')
    service_details = []
    for page in paginator.paginate():
        for resource in page['ResourceTagMappingList']:
            service_details.append(resource['ResourceARN'])
    return service_details

def save_report_to_s3(report, report_type):
    report_key = f'{report_type}_report_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.txt'
    s3_client.put_object(Bucket=S3_BUCKET, Key=report_key, Body=report)
    return report_key


def lambda_handler(event, context):

    global ec2_client
    global cloudwatch_client
    global iam_client
    global health_client

    # Calculate the date range for the report title
    today = datetime.now()
    last_week = today - timedelta(days=7)
    report_title = f"Weekly Inspection Report - {last_week.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}"
    report = [f"<h1>{report_title}</h1>"]

    for account in ACCOUNT_LIST:
        logger.info(f"Checking account {account['account_id']}...")
        
        # Assume role in target account
        session = assume_role(account)
        account_id = account['account_id']

        report.append(f'<h2 style="color:Tomato;">Account Name: {account["account_name"]}</h2>')

        # Initialize AWS clients
        ec2_client = session.client('ec2')
        cloudwatch_client = session.client('cloudwatch')
        iam_client = session.client('iam')
        health_client = session.client('health', 'us-east-1') # only provice health information from us-east-1

        report.append("<h3>1. Check AWS Health Dashboard</h3>")
        # 1. Check AWS Health Dashboard
        health_events = health_client.describe_events(filter={'eventStatusCodes': ['upcoming']})
        current_health_events = len(health_events['events'])
        if current_health_events > 0:
            event_details = []
            for event in health_events['events']:
                details = health_client.describe_event_details(eventArns=[event['arn']])['successfulSet'][0]
                event_details.append({
                    'EventType': event['eventTypeCode'],
                    'Service': event['service'],
                    'Region': event['region'],
                    'StartTime': str(event['startTime']),
                    'EndTime': str(event.get('endTime', 'N/A'))
                })
            health_summary = f"<b>Health events at report time: {current_health_events}</b>" + "\nEvent details:\n" + "\n".join(
                [f"EventType: {detail['EventType']}<ul><li>Service: {detail['Service']}</li><li>Region: {detail['Region']}</li><li>StartTime: {detail['StartTime']}</li><li>EndTime: {detail['EndTime']}</li></ul>"
                # [f"<ul><li>{detail['EventType']} | {detail['Service']} | {detail['Region']} | StartTime: {detail['StartTime']}</li></ul>"
                for detail in event_details]
            )
        else:
            health_summary = f"Health events at report time: {current_health_events}"
        
        report.append(health_summary)

        report.append("<h3>2. Check computing resources</h3>")
        # 2. Check whether computing resources increase or decrease
        current_instance_details = describe_instances()
        previous_instance_details = get_previous_state('Computing Resources', account_id).get('instance_details', [])
        
        added_instances = [instance for instance in current_instance_details if instance not in previous_instance_details]
        removed_instances = [instance for instance in previous_instance_details if instance not in current_instance_details]
        
        instance_changes_summary = (
            f"<b>Total EC2 instances: {len(current_instance_details)}</b><ul>"
            f"<li>Added instances: {len(added_instances)}</li>"
            f"<li>Removed instances: {len(removed_instances)}</li></ul>"
        )
        if added_instances:
            instance_changes_summary.append("Added Instances Details:\n" + "\n".join(
                [f"<ul><li>InstanceId: {inst['InstanceId']}</li><li>InstanceType: {inst['InstanceType']}</li><li>State: {inst['State']}</li><li>LaunchTime: {inst['LaunchTime']}</li></ul>"
                for inst in added_instances]))
        if removed_instances:
            instance_changes_summary.append("\nRemoved Instances Details:\n" + "\n".join(
                [f"<ul><li>InstanceId: {inst['InstanceId']}</li><li>InstanceType: {inst['InstanceType']}</li><li>State: {inst['State']}</li><li>LaunchTime: {inst['LaunchTime']}</li></ul>"
                for inst in removed_instances]))
        report.append(instance_changes_summary)
        update_state('Computing Resources', {'instance_details': current_instance_details}, account_id)
    
        report.append("<h3>3. Check monitoring settings</h3>")
        # 3. Check monitoring settings according to increased or decreased resources
        current_alarm_details = describe_alarms()
        previous_alarm_details = get_previous_state('Monitoring Settings', account_id).get('alarm_details', [])
        
        added_alarms = [alarm for alarm in current_alarm_details if alarm not in previous_alarm_details]
        removed_alarms = [alarm for alarm in previous_alarm_details if alarm not in current_alarm_details]
        
        alarms_summary = (
            f"<b>Total CloudWatch alarms: {len(current_alarm_details)}</b><ul>"
            f"<li>Added alarms: {len(added_alarms)}</li>"
            f"<li>Removed alarms: {len(removed_alarms)}</li></ul>"
        )
        if added_alarms:
            alarms_summary.append("Added Alarms Details:\n" + "\n".join(
                [f"<ul><li>AlarmName: {alarm['AlarmName']}</li><li>State: {alarm['State']}</li><li>MetricName: {alarm['MetricName']}</li><li>Threshold: {alarm['Threshold']}</li></ul>"
                for alarm in added_alarms]))
        if removed_alarms:
            alarms_summary.append("\nRemoved Alarms Details:\n" + "\n".join(
                [f"<ul><li>AlarmName: {alarm['AlarmName']}</li><li>State: {alarm['State']}</li><li>MetricName: {alarm['MetricName']}</li><li>Threshold: {alarm['Threshold']}</li></ul>"
                for alarm in removed_alarms]))
        report.append(alarms_summary)
        update_state('Monitoring Settings', {'alarm_details': current_alarm_details}, account_id)

        report.append("<h3>4. Check EC2 backup images</h3>")
        # 4. Check increase/decrease of backup image / Check EC2 backup tag
        snapshots = ec2_client.describe_snapshots(OwnerIds=['self'])
        current_snapshots_count = len(snapshots['Snapshots'])
        previous_snapshots_count = get_previous_state('EC2 Backup Images', account_id).get('snapshots_count', 0)
        
        snapshot_changes_summary = f"<b>Total EC2 snapshots: {current_snapshots_count} (Change: {current_snapshots_count - previous_snapshots_count})</b>"
        report.append(snapshot_changes_summary)
        update_state('EC2 Backup Images', {'snapshots_count': current_snapshots_count}, account_id)
    
        
    
        report.append("<h3>5. Check IAM roles and policies</h3>")
        # 5. Check IAM status
        current_roles_policies = get_iam_roles_policies()
        previous_roles_policies = get_previous_state('IAM Roles and Policies', account_id).get('roles_policies', [])
        
        added_roles = [role for role in current_roles_policies if role not in previous_roles_policies]
        removed_roles = [role for role in previous_roles_policies if role not in current_roles_policies]
        
        iam_changes_summary = (
            f"<b>Total IAM roles: {len(current_roles_policies)}</b><ul>"
            f"<li>Added roles: {len(added_roles)}</li>"
            f"<li>Removed roles: {len(removed_roles)}</li></ul>"
        )
        if added_roles:
            iam_changes_summary.append("Added Roles Details:\n" + "\n".join(
                [f"<ul><li>RoleName: {role['RoleName']}</li><li>Policies: {', '.join(role['Policies'])}</li>" for role in added_roles]))
        if removed_roles:
            iam_changes_summary.append("\nRemoved Roles Details:\n" + "\n".join(
                [f"<ul><li>RoleName: {role['RoleName']}</li><li>Policies: {', '.join(role['Policies'])}</li>" for role in removed_roles]))
        report.append(iam_changes_summary)
        update_state('IAM Roles and Policies', {'roles_policies': current_roles_policies}, account_id)

        # 6. Check Application Service Performance
        # Custom logic for application service performance, e.g., CloudWatch metrics for specific service
        performance_summary = "Checked application service performance."
        # create_jira_task('Check application service performance', performance_summary)

        #############################################
        # report.append("Check new region services\n")
        # # 7. Check the services created in the new region
        # regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
        # regions_to_check = [region for region in regions if region not in ['us-west-2', 'us-east-1']]
        # current_services = {}
        # for region in regions_to_check:
        #     current_services[region] = list_services_in_region(session, region)
        
        # previous_services = get_previous_state('New Region Services', account_id).get('services', {})
        # added_services = {}
        # for region in regions_to_check:
        #     if region in previous_services:
        #         added_services[region] = [service for service in current_services[region] if service not in previous_services[region]]
        #     else:
        #         added_services[region] = current_services[region]
        
        # services_changes_summary = "New services in regions (excluding us-west-2 and us-east-1):\n" + "\n".join(
        #     [f"Region: {region}, New Services: {', '.join(added_services[region])}" for region in added_services if added_services[region]]
        # )
        
        # report.append(services_changes_summary)
        # update_state('New Region Services', {'services': current_services}, account_id)
        #############################################

    createconfluence_page_link = create_confluence_page(f"{report_title}", "\n".join(report))
    create_jira_task(report_title, createconfluence_page_link)
    # services_report_key = save_report_to_s3("\n".join(report), 'Weekly Service')
    # create_jira_task(report_title, f"Services changes summary saved to S3: s3://{S3_BUCKET}/{services_report_key}")

    return {
        'statusCode': 200,
        'body': 'Weekly inspection tasks completed and added to Jira with change information.'
    }
