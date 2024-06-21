import json
import logging
import time
import copy
from datetime import datetime, timedelta
from module import cron_descriptor

#Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class Services:
    def run(self, account_id, session, region, event):
        
        # EC2 RI
        ri_ec2_info, len = Services.ri_ec2(account_id, session, region)
        if len:
            if 'ri_info' not in event['this_month']:
                event['this_month']['ri_info'] = {}
                event['this_month']['ri_usage'] = {}
            if region not in event['this_month']['ri_info']:
                event['this_month']['ri_info'][region] = []
                event['this_month']['ri_usage'][region] = []
            event['this_month']['ri_info'][region].extend(ri_ec2_info['reserved_info'])
            event['this_month']['ri_usage'][region].extend(ri_ec2_info['reserved_usage'])
        
        # RDS RI
        ri_rds_info, len = Services.ri_rds(account_id, session, region)
        if len:
            if 'ri_info' not in event['this_month']:
                event['this_month']['ri_info'] = {}
                event['this_month']['ri_usage'] = {}
            if region not in event['this_month']['ri_info']:
                event['this_month']['ri_info'][region] = []
                event['this_month']['ri_usage'][region] = []
            event['this_month']['ri_info'][region].extend(ri_rds_info['reserved_info'])
            event['this_month']['ri_usage'][region].extend(ri_rds_info['reserved_usage'])
        
        # Backup
        backup_info, len = Services.backup(account_id, session, region)
        if len: 
            if 'backup' not in event['this_month']:
                event['this_month']['backup'] = {}
            if region not in event['this_month']['backup']:
                event['this_month']['backup'][region] = []
            event['this_month']['backup'][region].extend(backup_info)
        
        # RDS
        cluster_data, single_data, cluster_len, single_len = Services.rds(account_id, session, region)
        
        if cluster_len:
            if 'rds_cluster' not in event['this_month']:
                event['this_month']['rds_cluster'] = {}
            if region not in event['this_month']['rds_cluster']:
                event['this_month']['rds_cluster'][region] = cluster_data
        if single_len:
            if 'rds_single' not in event['this_month']:
                event['this_month']['rds_single'] = {}
            if region not in event['this_month']['rds_single']:
                event['this_month']['rds_single'][region] = single_data
            
        # Cache
        cache_data, len = Services.cache(account_id, session, region)
        if len:
            if 'cache' not in event['this_month']:
                event['this_month']['cache'] = {}
            if region not in event['this_month']['cache']:
                event['this_month']['cache'][region] = cache_data
          
        # Elastc Load Balancer
        elb_data, len = Services.elb(account_id, session, region)
        if len:
            if 'elb' not in event['this_month']:
                event['this_month']['elb'] = {}
            if region not in event['this_month']['elb']:
                event['this_month']['elb'][region] = elb_data
        
        # EBS
        ebs_data, len = Services.storage(account_id, session, region)
        if len:
            if 'ebs' not in event['this_month']:
                event['this_month']['ebs'] = {}
            if region not in event['this_month']['ebs']:
                event['this_month']['ebs'][region] = ebs_data
        
        # EC2
        ec2_data, len = Services.ec2(account_id, session, region)
        if len:
            if 'ec2' not in event['this_month']:
                event['this_month']['ec2'] = {}
            if region not in event['this_month']['ec2']:
                event['this_month']['ec2'][region] = ec2_data
        
        # Lambda
        lambda_data, len = Services.lambda_service(account_id, session, region)
        if len:
            if 'other' not in event['this_month']:
                event['this_month']['other'] = []
            event['this_month']['other'].append(lambda_data)
        
        # Other
        other_data, len = Services.rgapi(account_id, session, region)
        if len:
            if 'other' not in event['this_month']:
                event['this_month']['other'] = []
            event['this_month']['other'].extend(other_data)
        
        logger.info('[Account ID: {}] Region Service Success // region: {}'.format(account_id, region))
    
    
    def ri_ec2(account_id, session, region):
        try:
            ec2_client = session.client('ec2', region)
            normalize = {
                'nano': 0.25,
                'micro': 0.5,
                'small': 1,
                'medium': 2,
                'large': 4,
                'xlarge': 8,
                '2xlarge': 16,
                '3xlarge': 24,
                '4xlarge': 32,
                '6xlarge': 48,
                '8xlarge': 64,
                '9xlarge': 72,
                '10xlarge': 80,
                '12xlarge': 96,
                '16xlarge': 128,
                '18xlarge': 144,
                '24xlarge': 192,
                '32xlarge': 256,
                '56xlarge': 448,
                '112xlarge': 896,
                'metal': 0
            }
            
            '''
            1. running_instances에 Platform이 있으면 먼저 넣어주고 이후 ami로 찾은 데이터에서 PlatformDetails가 존재하면 교체
            '''
            
            # 현재 실행중인 ec2 list
            running_instances = ec2_client.describe_instances( Filters = [{'Name': 'instance-state-name','Values': [ 'running' ]}])
            running_instances_imageid = []
            running_list ={}
            for instances in running_instances['Reservations']:
                for instance in instances['Instances']:
                    platform = instance.get('Platform','Linux/UNIX')
                    platform = platform[:1].capitalize() + platform[1:]
                    running_list[instance['InstanceId']] = {'ImageId': instance['ImageId'], 'InstanceType': instance['InstanceType'], 'InstanceTenancy': instance['Placement']['Tenancy'], 'ProductDescription': platform}
                    running_instances_imageid.append(instance['ImageId'])
            # 현재 실행중인 EC2가 있을때
            if len(running_instances_imageid) != 0:
                # 현재 실행중인 ec2 platform 구하기  
                describe_images = ec2_client.describe_images(ImageIds=running_instances_imageid)
                instances_platform = {}
                for instance in describe_images['Images']:
                    if 'PlatformDetails' in instance: 
                        instances_platform[instance['ImageId']] = instance['PlatformDetails']
                    else:
                        instances_platform[instance['ImageId']] = 'NULL'
                running_normalized_list = {}
                
                # 현재 실행중인 ec2 platform 넣기
                for instance in running_list:
                    platform = instances_platform.get(running_list[instance]['ImageId'], 'NULL')
                    if platform != 'NULL':
                        running_list[instance]['ProductDescription'] = platform
                    # 크기 유연성 대상 확인
                    if running_list[instance]['ProductDescription'] != 'Linux/UNIX' or running_list[instance]['InstanceTenancy'] != 'default' or running_list[instance]['InstanceType'].split('.')[0] == 'G4dn':
                        key = (running_list[instance]['InstanceType'], running_list[instance]['ProductDescription'], 'X', running_list[instance]['InstanceTenancy'])
                        running_normalized_list[key] = running_normalized_list.get(key, 0) + 1
                    else:
                        key = (running_list[instance]['InstanceType'].split('.')[0], running_list[instance]['ProductDescription'], 'O', 'default')
                        running_normalized_list[key] = running_normalized_list.get(key, 0) + normalize[running_list[instance]['InstanceType'].split('.')[1]]
            else:
                logger.info('[ri_ec2] No Running Instance')   
                
            # 예약 ec2
            reserved_instances = ec2_client.describe_reserved_instances(Filters = [{'Name': 'state','Values': [ 'active' ]}])
            reserved_info = []
            reserved_normalized_list = {}
            for instance in reserved_instances['ReservedInstances']:
                # RI 대상 정보
                temp = {}
                temp['service'] = 'EC2'
                temp['instance_type'] = instance['InstanceType']
                temp['count'] = instance['InstanceCount']
                temp['platform'] = instance['ProductDescription']
                temp['offering_type'] = '선결제 없음' if instance['OfferingType'] == 'No Upfront' else '부분 선결제' if instance['OfferingType'] == 'Partial Upfront' else '전체 선결제'
                temp['offering_class'] = '컨버터블' if instance['OfferingClass'] == 'convertible' else '표준' if instance['OfferingClass'] == 'standard' else instance['OfferingClass']
                temp['start'] = (instance['Start'] + timedelta(hours = 9)).strftime('20%y년 %m월 %d일  %I:%M %p')
                temp['end'] = (instance['End'] + timedelta(hours = 9)).strftime('20%y년 %m월 %d일  %I:%M %p')
                reserved_info.append(temp)
                # 크기 유연성 대상 확인, 동일한 대상 
                if instance['ProductDescription'] != 'Linux/UNIX' or instance['InstanceTenancy'] != 'default' or instance['Scope'] != 'Region' or instance['InstanceType'].split('.')[0] == 'G4dn':
                    key = (instance['InstanceType'], instance['ProductDescription'], 'X', instance['InstanceTenancy'])
                    reserved_normalized_list[key] = reserved_normalized_list.get(key, 0) + instance['InstanceCount']
                else:
                    key = (instance['InstanceType'].split('.')[0], instance['ProductDescription'], 'O', 'default')
                    reserved_normalized_list[key] = reserved_normalized_list.get(key, 0) + normalize[instance['InstanceType'].split('.')[1]] * instance['InstanceCount']
            
            # RI 사용량 확인
            reserved_usage = []
            for instance in reserved_normalized_list:
                temp = {}
                temp['service'] = 'EC2'
                temp['instance_type'] = instance[0]
                temp['platform'] = instance[1]
                temp['flexibility'] = instance[2]
                temp['normalized'] = str(reserved_normalized_list.get(instance, 0)) #+ 'ea' if instance[2] == 'X' else reserved_normalized_list.get(instance, 0)
                temp['normalized_used'] = str(running_normalized_list.get(instance, 0)) #+ 'ea' if instance[2] == 'X' else running_normalized_list.get(instance, 0)
                temp['normalized_used_percent'] = str(round(running_normalized_list.get(instance, 0) / reserved_normalized_list[instance] * 100)) + '%'
                reserved_usage.append(temp)
            
            # 현재 실행중인 EC2 + 사용량 확인 (host)
            host_instances = ec2_client.describe_hosts(Filters = [{'Name': 'state','Values': [ 'available' ]}])
            for instance in host_instances['Hosts']:
                temp = {}
                temp['service'] = 'EC2'
                temp['instance_type'] = instance['HostProperties']['InstanceFamily'] + '(host)'
                temp['platform'] = '-'
                temp['flexibility'] = 'X'
                temp['normalized'] = str(instance['HostProperties']['TotalVCpus']) + ' vCPU'
                temp['normalized_used'] = str(instance['HostProperties']['TotalVCpus'] - instance['AvailableCapacity']['AvailableVCpus']) + ' vCPU'
                temp['normalized_used_percent'] = str(round((instance['HostProperties']['TotalVCpus'] - instance['AvailableCapacity']['AvailableVCpus']) / instance['HostProperties']['TotalVCpus'] * 100)) + '%'
                reserved_usage.append(temp)
            
            # 예약 ec2(host)
            host_reserved_instances = ec2_client.describe_host_reservations(Filters = [{'Name': 'state','Values': [ 'active' ]}])
            for instance in host_reserved_instances['HostReservationSet']:
                # RI 대상 정보
                temp = {}
                temp['service'] = 'EC2'
                temp['instance_type'] = instance['InstanceFamily'] + '(host)'
                temp['count'] = instance['Count']
                temp['platform'] = '-'
                temp['offering_type'] = '선결제 없음' if instance['PaymentOption'] == 'NoUpfront' else '부분 선결제' if instance['PaymentOption'] == 'PartialUpfront' else '전체 선결제'
                temp['offering_class'] = '-'
                temp['start'] = (instance['Start'] + timedelta(hours = 9)).strftime('20%y년 %m월 %d일  %I:%M %p')
                temp['end'] = (instance['End'] + timedelta(hours = 9)).strftime('20%y년 %m월 %d일  %I:%M %p')
                reserved_info.append(temp)
            reserved_info = sorted(reserved_info, key = lambda x:(x['platform'], x['instance_type']), reverse = False)
            reserved_usage = sorted(reserved_usage, key = lambda x:(x['platform'], x['instance_type']), reverse = False)
            # Return    
            result = {}
            result['reserved_info'] = reserved_info
            result['reserved_usage'] = reserved_usage
            return result, len(reserved_info)
        except Exception as e:
            logger.error('[Account ID: {}] RI(EC2) Service // {}'.format(account_id, e))
            return 0, 0
    
    
    def ri_rds(account_id, session, region):
        try:
            rds_client = session.client('rds', region)
            normalize = {
                'nano': 0.25, 
                'micro': 0.5,
                'small': 1,
                'medium': 2,
                'large': 4,
                'xlarge': 8,
                '2xlarge': 16,
                '3xlarge': 24,
                '4xlarge': 32,
                '6xlarge': 48,
                '8xlarge': 64,
                '9xlarge': 72,
                '10xlarge': 80,
                '12xlarge': 96,
                '16xlarge': 128,
                '18xlarge': 144,
                '24xlarge': 192,
                '32xlarge': 256,
                '56xlarge': 448,
                '112xlarge': 896,
                'metal': 0
            }
            
            # 현재 사용중인 RDS list
            rds_list = rds_client.describe_db_instances()
            running_rds_normalized_list = {}
            for instance in rds_list['DBInstances']:
                if instance['DBInstanceStatus'] == 'available':
                    license = ''
                    engine = ''
                    if 'LicenseModel' in instance:
                        if instance['LicenseModel'] == 'license-included':
                            license = '(li)'
                    if 'EngineVersion' in instance:
                        if 'mysql' in instance['EngineVersion'].split('_')[0]:
                            engine = 'aurora-mysql'
                        else:
                            engine = instance['Engine']
                    else:
                        engine = instance['Engine']
                    key = (instance['DBInstanceClass'].split('.')[1], engine + license)
                    running_rds_normalized_list[key] = running_rds_normalized_list.get(key,0) \
                    + (1 if instance['MultiAZ'] != 'True' else 2) \
                    * normalize[instance['DBInstanceClass'].split('.')[2]]
            
            # 예약 RDS        
            reserved_rds_list = rds_client.describe_reserved_db_instances()
            reserved_rds_normalized_list = {}
            reserved_rds_info = []
            for instance in reserved_rds_list['ReservedDBInstances']:
                if instance['State'] == 'active':
                    key = (instance['DBInstanceClass'].split('.')[1], instance['ProductDescription'])
                    reserved_rds_normalized_list[key] = reserved_rds_normalized_list.get(key, 0) \
                    + (1 if instance['MultiAZ'] != 'True' else 2) \
                    * normalize[instance['DBInstanceClass'].split('.')[2]] \
                    * instance['DBInstanceCount']
    
                    temp = {}
                    temp['service'] = 'RDS'
                    temp['instance_type'] = instance['DBInstanceClass']
                    temp['count'] = (1 if instance['MultiAZ'] != 'True' else 2) * instance['DBInstanceCount']
                    temp['platform'] = instance['ProductDescription']
                    temp['offering_type'] = '선결제 없음' if instance['OfferingType'] == 'No Upfront' else '부분 선결제' if instance['OfferingType'] == 'Partial Upfront' else '전체 선결제'
                    temp['offering_class'] = '표준'
                    temp['start'] = (instance['StartTime'] + timedelta(hours = 9)).strftime('20%y년 %m월 %d일  %I:%M %p')
                    temp['end'] = (instance['StartTime'] + timedelta(hours = 9, seconds = instance['Duration'])).strftime('20%y년 %m월 %d일  %I:%M %p')
                    reserved_rds_info.append(temp)
            
            # RI 사용 계산
            reserved_rds_normalized_list_used = copy.deepcopy(reserved_rds_normalized_list)
            for reserved_rds_normalized_used in reserved_rds_normalized_list_used:
                if reserved_rds_normalized_used in running_rds_normalized_list:
                    reserved_rds_normalized_list_used[reserved_rds_normalized_used] = running_rds_normalized_list[reserved_rds_normalized_used]
                else:
                    reserved_rds_normalized_list_used[reserved_rds_normalized_used] = 0
            
            # RI 사용 퍼센트 계산
            reserved_rds_normalized_list_used_percent = copy.deepcopy(reserved_rds_normalized_list)
            for reserved_rds_normalized_key in reserved_rds_normalized_list_used_percent:
                if reserved_rds_normalized_key in running_rds_normalized_list:
                    reserved_rds_normalized_list_used_percent[reserved_rds_normalized_key] = round(running_rds_normalized_list[reserved_rds_normalized_key] / reserved_rds_normalized_list_used_percent[reserved_rds_normalized_key] * 100)
                else:
                    reserved_rds_normalized_list_used_percent[reserved_rds_normalized_key] = 0
            
            # RI 사용량 확인
            reserved_usage = []
            for key in reserved_rds_normalized_list:
                temp = {}
                temp['service'] = 'RDS'
                temp['instance_type'] = key[0]
                temp['platform'] = key[1]
                temp['flexibility'] = 'O'
                temp['normalized'] = reserved_rds_normalized_list[key]
                temp['normalized_used'] = reserved_rds_normalized_list_used[key]
                temp['normalized_used_percent'] = str(reserved_rds_normalized_list_used_percent[key]) + '%'
                reserved_usage.append(temp)
                
            result = {}    
            reserved_rds_info = sorted(reserved_rds_info, key = lambda x:(x['platform'], x['instance_type']), reverse = False)
            reserved_usage = sorted(reserved_usage, key = lambda x:(x['platform'], x['instance_type']), reverse = False)
            result['reserved_info'] = reserved_rds_info
            result['reserved_usage'] = reserved_usage
            return result, len(result['reserved_info'])
        except Exception as e:
            logger.error('[Account ID: {}] RI(RDS) Service // {}'.format(account_id, e))
            return 0, 0
    
    
    def backup(account_id, session, region):
        try:
            backup = session.client('backup', region)
            resourceapi = session.client('resourcegroupstaggingapi', region)
            backup_vaults = backup.list_backup_vaults()
            result = []
            backup_result = []
            
            # 백업 볼트 
            for backup_vault in backup_vaults['BackupVaultList']:
                # recovery point 중복제거 리스트 => plan 이름, 버전 찾기 위해서 생성
                recovery_points = backup.list_recovery_points_by_backup_vault(BackupVaultName = backup_vault['BackupVaultName'])['RecoveryPoints']
                backup_plans = {}
                backup_targets = {}
                count_all = 0
                for item in recovery_points:
                    # 2019년에 생성된 recovery point는 빼기
                    if 'CreatedBy' not in item:
                        continue
                    # plan ID가 없을 경우 추가
                    if item['CreatedBy']['BackupPlanId'] not in backup_plans:
                        count_all = 0
                        backup_plans[item['CreatedBy']['BackupPlanId']] = {'version': [item['CreatedBy']['BackupPlanVersion']], 'count': count_all, 'resources': {}, 'service': {}, 'rule':{}}
                    # plan 버전 추가
                    if item['CreatedBy']['BackupPlanVersion'] not in backup_plans[item['CreatedBy']['BackupPlanId']]['version']:
                        backup_plans[item['CreatedBy']['BackupPlanId']]['version'].append(item['CreatedBy']['BackupPlanVersion'])
                    # resource ARN, 타겟 추가
                    if item['ResourceArn'] not in  backup_plans[item['CreatedBy']['BackupPlanId']]['resources']:
                        backup_plans[item['CreatedBy']['BackupPlanId']]['resources'][item['ResourceArn']] = 0
                        service = item['ResourceArn'].split(':')[2].upper()
                        if service == 'ELASTICFILESYSTEM':
                            service = 'EFS'
                        if service not in backup_plans[item['CreatedBy']['BackupPlanId']]['service']:
                            backup_plans[item['CreatedBy']['BackupPlanId']]['service'][service] = 0
                    # Rule별로 대상 추가
                    if item['CreatedBy']['BackupRuleId'] not in backup_plans[item['CreatedBy']['BackupPlanId']]['rule']:
                        backup_plans[item['CreatedBy']['BackupPlanId']]['rule'][item['CreatedBy']['BackupRuleId']] = {}
                    if item['ResourceArn'] not in backup_plans[item['CreatedBy']['BackupPlanId']]['rule'][item['CreatedBy']['BackupRuleId']]:
                        backup_plans[item['CreatedBy']['BackupPlanId']]['rule'][item['CreatedBy']['BackupRuleId']][item['ResourceArn']] = 0
                    # rule의 EC2 대상 추가
                    backup_plans[item['CreatedBy']['BackupPlanId']]['rule'][item['CreatedBy']['BackupRuleId']][item['ResourceArn']] += 1
                    # resource ARN 추가
                    backup_plans[item['CreatedBy']['BackupPlanId']]['resources'][item['ResourceArn']] += 1
                    # 총 카운트, 타겟 추가
                    backup_plans[item['CreatedBy']['BackupPlanId']]['service'][service] += 1
                    backup_plans[item['CreatedBy']['BackupPlanId']]['count'] += 1
                
                # Rule당 저장된 EC2 backup point
                for backup_plan in backup_plans:
                    backup_rules = []
                    # rule 버전 확인
                    for version in backup_plans[backup_plan]['version']:
                        backup_rules.extend(backup.get_backup_plan(BackupPlanId = backup_plan, VersionId = version)['BackupPlan']['Rules'])
                    # rule의 ID를 키로 저장
                    backup_rules_key = {}
                    for backup_rule in backup_rules:
                        backup_rules_key[backup_rule['RuleId']] = backup_rule
                    # rule의 ID에 대한 데이터 저장
                    for rule in backup_plans[backup_plan]['rule']:
                        temp = {}
                        count = 0
                        service = ''
                        for item in backup_plans[backup_plan]['service']:
                            service += item + ', '
                        for item in backup_plans[backup_plan]['rule'][rule]:
                            count += backup_plans[backup_plan]['rule'][rule][item]
                        temp['count'] = count
                        temp['source'] = 'AWS Backup'
                        temp['target'] = len(backup_plans[backup_plan]['resources'])
                        temp['service'] = service[:-2]
                        temp['life_cycle'] = str(backup_rules_key[rule]['Lifecycle']['DeleteAfterDays']) + '일' if 'Lifecycle' in backup_rule else '만료기한 없음'
                        temp['converted_schedule_expression'] = cron_descriptor.cron_descriptor(backup_rules_key[rule]['ScheduleExpression'])
                        backup_result.append(temp)
            
            # rule의 내용은 똑같으나 버전이 다른 중복된 내용 합치기
            deduplication_list = {}
            for item in backup_result:
                deduplication_key = item['source'] + ';' + str(item['target']) + ';' + item['service'] + ';' + item['life_cycle'] + ';' + item['converted_schedule_expression']
                if deduplication_key in deduplication_list:
                    deduplication_list[deduplication_key] += item['count']
                else:
                    deduplication_list[deduplication_key] = item['count']
            for deduplication_item in deduplication_list:
                temp = {}
                deduplication_tuple = deduplication_item.split(';')
                temp['count'] = deduplication_list[deduplication_item]
                temp['source'] = deduplication_tuple[0]
                temp['target'] = deduplication_tuple[1]
                temp['service'] = deduplication_tuple[2]
                temp['life_cycle'] = deduplication_tuple[3]
                temp['converted_schedule_expression'] = deduplication_tuple[4]
                result.append(temp)
            
            # Console대상 RDS 백업
            rds_console = []
            rds_session = session.client('rds', region)
            rds_list = rds_session.describe_db_instances()
            for rds_info in rds_list['DBInstances']:
                if rds_info['Engine'] != 'docdb' and 'DBClusterIdentifier' not in rds_info:
                    # 저장기간 0일 제외
                    if rds_info['BackupRetentionPeriod'] == 0:
                        continue
                    temp = {}
                    temp['source'] = 'Console'
                    temp['service'] = 'RDS'
                    temp['life_cycle'] = str(rds_info['BackupRetentionPeriod']) + '일'
                    if int(rds_info['PreferredBackupWindow'].split('-')[0].split(':')[0]) > 12:
                        time = "0" + str(int(rds_info['PreferredBackupWindow'].split('-')[0].split(':')[0]) % 12) + ':' + rds_info['PreferredBackupWindow'].split('-')[0].split(':')[1] + "PM"
                    else:
                        time = rds_info['PreferredBackupWindow'].split('-')[0] + "AM"
                    temp['converted_schedule_expression'] = '매일 ' + time
                    temp['target'] = 1
                    temp['count'] = len(rds_session.describe_db_snapshots(SnapshotType = 'automated', Filters=[{'Name': 'db-instance-id', 'Values': [rds_info['DBInstanceIdentifier']]}])['DBSnapshots'])
                    rds_info_list = next((item for item in rds_console if item['life_cycle'] == temp['life_cycle'] and item['converted_schedule_expression'] == temp['converted_schedule_expression']),False)
                    if rds_info_list:
                        rds_info_list['target'] += 1
                        rds_info_list['count'] += temp['count']
                    else: 
                        rds_console.append(temp)
                else:
                    # document DB 제외
                    pass
            
            # Console대상 Aurora 
            rds_cluster_list = rds_session.describe_db_clusters()
            for rds_info in rds_cluster_list['DBClusters']:
                # 저장기간 0일 제외
                if rds_info['BackupRetentionPeriod'] == 0:
                    continue
                temp = {}
                temp['source'] = 'Console'
                temp['service'] = 'RDS'
                temp['life_cycle'] = str(rds_info['BackupRetentionPeriod']) + '일'
                if int(rds_info['PreferredBackupWindow'].split('-')[0].split(':')[0]) > 12:
                    time = "0" + str(int(rds_info['PreferredBackupWindow'].split('-')[0].split(':')[0]) % 12) + ':' + rds_info['PreferredBackupWindow'].split('-')[0].split(':')[1] + "PM"
                else:
                    time = rds_info['PreferredBackupWindow'].split('-')[0] + "AM"
                temp['converted_schedule_expression'] = '매일 ' + time
                temp['target'] = 1
                temp['count'] = len(rds_session.describe_db_cluster_snapshots(SnapshotType = 'automated', Filters=[{'Name': 'db-cluster-id', 'Values': [rds_info['DBClusterIdentifier']]}])['DBClusterSnapshots'])
                rds_info_list = next((item for item in rds_console if item['source'] == temp['source'] and item['life_cycle'] == temp['life_cycle'] and item['converted_schedule_expression'] == temp['converted_schedule_expression']),False)
                if rds_info_list:
                    rds_info_list['target'] += 1
                    rds_info_list['count'] += temp['count']
                else: 
                    rds_console.append(temp)
                
            result.extend(rds_console)
            return result, len(result)
        except Exception as e:
            logger.error('[Account ID: {}] Backup Service // {}'.format(account_id, e))
            return 0, 0

    
    def rds(account_id, session, region):
        try:
            rds = session.client('rds', region)
            # Clustering
            clusters = rds.describe_db_clusters().get('DBClusters')
            clustering_list = {'db_class': {}, 'engines': {}}
            if len(clusters) > 0:
                for cluster in clusters:
                    if cluster['Engine'] not in clustering_list['engines']:
                        clustering_list['engines'][cluster['Engine']] = {'Cluster': 1, 'Instance': len(cluster['DBClusterMembers'])}
                    else:
                        clustering_list['engines'][cluster['Engine']]['Cluster'] = clustering_list['engines'][cluster['Engine']]['Cluster'] + 1
                        clustering_list['engines'][cluster['Engine']]['Instance'] = clustering_list['engines'][cluster['Engine']]['Instance'] + len(cluster['DBClusterMembers'])
            elif len(clusters) == 0:
                clustering_list = {}
            
            # None Clustering
            instances = rds.describe_db_instances().get('DBInstances')
            single_list = {'db_class': {}, 'engines': {}}
            if len(instances) > 0:
                for instance in instances:
                    if 'DBClusterIdentifier' not in instance:
                        if instance['DBInstanceClass'] not in single_list['db_class']:
                            single_list['db_class'][instance['DBInstanceClass']] = 1
                        else:
                            single_list['db_class'][instance['DBInstanceClass']] = single_list['db_class'][instance['DBInstanceClass']] + 1
                        if instance['Engine'] not in single_list['engines']:
                            single_list['engines'][instance['Engine']] = 1
                        else:
                            single_list['engines'][instance['Engine']] = single_list['engines'][instance['Engine']] + 1
                    elif 'DBClusterIdentifier' in instance:
                        if instance['DBInstanceClass'] not in clustering_list['db_class']:
                            clustering_list['db_class'][instance['DBInstanceClass']] = 1
                        else:
                            clustering_list['db_class'][instance['DBInstanceClass']] = clustering_list['db_class'][instance['DBInstanceClass']] + 1
            if single_list['db_class'] == {}:
                single_list = {}
            return clustering_list, single_list, len(clustering_list), len(single_list)
        except Exception as e:
            logger.error('[Account ID: {}] RDS Service // {}'.format(account_id, e))
            return 0, 0, 0, 0
    
    
    def cache(account_id, session, region):
        try:
            cache_client = session.client('elasticache', region)
            clusters = cache_client.describe_cache_clusters()
            
            # memcache / redis 노드 분류
            cache_count = {}
            cache_type = {}
            for cluster in clusters['CacheClusters']:
                if cluster['Engine'] == 'memcached':
                    cache_count['Memcached'] = cache_count.get('Memcached', 0) + 1
                elif cluster['Engine'] == 'redis':
                    cache_count['Redis'] = cache_count.get('Redis', 0) + 1
                else:
                    pass
                cache_type[cluster['CacheNodeType']] = cache_type.get(cluster['CacheNodeType'], 0) + 1
            
            # result
            result = {}
            result['cache_count'] = cache_count
            result['cache_type'] = cache_type  
            return result, len(result['cache_count'])
        except Exception as e:
            logger.error('[Account ID: {}] Cache Service // {}'.format(account_id, e))
            return 0, 0
    
    
    def elb(account_id, session, region):
        try:
            elb = session.client('elb',region)
            elbv2 = session.client('elbv2',region)
            elb_lbs = {}
            elb_targets = {}
            response = len(elb.describe_load_balancers().get('LoadBalancerDescriptions'))
            if response > 0:
                elb_lbs['clb'] = response
            response_v2 = elbv2.describe_load_balancers().get('LoadBalancers')
            for v2 in response_v2:
                if v2['Type'] == 'network':
                    if 'nlb' not in elb_lbs:
                        elb_lbs['nlb'] = 0
                    elb_lbs['nlb'] = elb_lbs['nlb'] + 1
                if v2['Type'] == 'application':
                    if 'alb' not in elb_lbs:
                        elb_lbs['alb'] = 0
                    elb_lbs['alb'] = elb_lbs['alb'] + 1
                if v2['Type'] == 'gateway':
                    if 'gwlb' not in elb_lbs:
                        elb_lbs['gwlb'] = 0
                    elb_lbs['gwlb'] = elb_lbs['gwlb'] + 1
            
            #target Unhealthy
            all_targets = elbv2.describe_target_groups().get('TargetGroups')
            # print(all_targets)
            elb_tgs = {'group_total': 0, 'target_total': 0, 'unhealthy': 0, 'healthy': 0}
            for target in all_targets:
                elb_tgs['group_total'] = elb_tgs['group_total'] + 1
                target_health = elbv2.describe_target_health(TargetGroupArn=target['TargetGroupArn']).get('TargetHealthDescriptions')
                for health in target_health:
                    elb_tgs['target_total'] = elb_tgs['target_total'] + 1
                    if health['TargetHealth']['State'] == 'unhealthy':
                        # print('TargetGroupName: {}, TargetId: {}'.format(target['TargetGroupName'], health['Target']['Id']))
                        elb_tgs['unhealthy'] = elb_tgs['unhealthy'] + 1
                    elif health['TargetHealth']['State'] == 'healthy':
                        elb_tgs['healthy'] = elb_tgs['healthy'] + 1
            result = {}
            result['loadbalance'] = elb_lbs
            result['targetgroup'] = elb_tgs
            return result, len(elb_lbs)
        except Exception as e:
            logger.error('[Account ID: {}] ELB Service // {}'.format(account_id, e))
            return 0, 0
    
    
    def storage(account_id, session, region):
        try:
            ebs = session.client('ec2', region)
            #volume
            response = ebs.describe_volumes().get('Volumes')
            volumes = {}
            for vol in response:
                if 'total' not in volumes:
                    volumes['total'] = {'count':0, 'size': 0}
                volumes['total']['count'] = volumes['total']['count'] + 1
                volumes['total']['size'] = volumes['total']['size'] + vol['Size']
                if vol['State'] == 'available':
                    if 'not_used' not in volumes:
                        volumes['not_used'] = {'count':0, 'size': 0}
                    volumes['not_used']['count'] = volumes['not_used']['count'] + 1
                    volumes['not_used']['size'] = volumes['not_used']['size'] + vol['Size']
                volume_type = vol['VolumeType']
                if 'type' not in volumes:
                    volumes['type'] = {}
                if volume_type not in volumes['type']:
                    volumes['type'][volume_type] = 0
                volumes['type'][volume_type] = volumes['type'][volume_type] + 1
            
            #snapshot
            responsnap = ebs.describe_snapshots(
                Filters=[{
                    'Name': 'owner-id',
                    'Values': [account_id]
                }]).get('Snapshots')
            snapshots = {}
            
            for snap_one in responsnap:
                if 'total' not in snapshots:
                    snapshots['total'] = {'count':0, 'size': 0}
                snapshots['total']['count'] = snapshots['total']['count'] + 1
                snapshots['total']['size'] = snapshots['total']['size'] + snap_one['VolumeSize']
            result = {}
            result['volume'] = volumes
            result['snapshot'] = snapshots
            return result, len(volumes)
        except Exception as e:
            logger.error('[Account ID: {}] EBS Service // {}'.format(account_id, e))
            return 0, 0
    
    
    def ec2(account_id, session, region):
        try:
            ec2 = session.client('ec2', region)
            response = ec2.describe_instances(
                Filters=[
                    {
                        'Name': 'instance-state-name',
                        'Values': ['running']
                    }],
                MaxResults=1000
            )
            reservations = response['Reservations']
            while "NextToken" in response:
                response = ec2.describe_instances(
                    Filters=[
                        {
                            'Name': 'instance-state-name',
                            'Values': ['running']
                        }],
                    MaxResults=1000,
                    NextToken=response['NextToken']
                )
                reservations.extend(response['Reservations'])
            result = {'instance': 0}
            type_count = {}
            ec2_instances = []
            for reservation in reservations:
                if 'RequesterId' in reservation and reservation['RequesterId'] == '722737459838':
                    # AutoScaling Instance
                    pass
                else:
                    ec2_instances.extend(reservation['Instances'])
            for instance in ec2_instances:
                result['instance'] = result['instance'] + 1
                if instance['InstanceType'] not in type_count:
                    type_count[instance['InstanceType']] = 0
                type_count[instance['InstanceType']] = type_count[instance['InstanceType']] + 1
            result['instance_type'] = type_count
            return result, result['instance']
        except Exception as e:
            logger.error('[Account ID: {}] EC2 Service // {}'.format(account_id, e))
            return 0, 0
    
    
    def lambda_service(account_id, session, region):
        try:
            lambda_client = session.client('lambda', region)
            count = 0
            next_marker = ''
            data = lambda_client.list_functions()
            while True:
                count += len(data['Functions'])
                if 'NextMarker' in data:
                    next_marker = data['NextMarker']
                    data = lambda_client.list_functions(Marker = next_marker)
                else:
                    break
            result = {}
            result['service'] = 'Lambda'
            result['region'] = region
            result['category'] = 'Function'
            result['count'] = count
            return result, count
        except Exception as e:
            logger.error('[Account ID: {}] Lambda Service // {}'.format(account_id, e))
            return 0, 0
    
    
    def rgapi(account_id, session, region):
        try:
            update_resources = {}
            resource_types = ['ec2:natgateway', 'ec2:vpn-connection',
                'kms:key']
            for rsc in resource_types:
                count = roop_tk.get_rgapi(session, rsc, region)
                if count > 0:
                    update_resources.update({rsc: count})
            result = []
            for k, v in update_resources.items():
                temp = {}
                service_temp = k.split(':')[0]
                if service_temp == 'ec2': service = 'EC2'
                elif service_temp == 'kms': service = 'KMS'
                cate_temp = k.split(':')[1]
                if cate_temp == 'natgateway': category = 'NAT Gateway'
                elif cate_temp == 'vpn-connection': category = 'VPN-Connection'
                elif cate_temp == 'key': category = 'Key'
                temp['service'] = service
                temp['region'] = region
                temp['category'] = category
                temp['count'] = v
                result.append(temp)
            return result, len(result)
        except Exception as e:
            logger.error('[Account ID: {}] Other Service // {}'.format(account_id, e))
            return 0, 0
        """
        ARN만 뽑기
        for to_list in total_list:
            total_arn.append(to_list['ResourceARN'])
        """


class roop_tk:
    def get_rgapi(session, resource_type, region):
        rgapi = session.client('resourcegroupstaggingapi', region)
        first_job = roop_tk.rgapi_1(rgapi, resource_type)
        total_arn = []
        total_list = first_job['ResourceTagMappingList']
        token = first_job['PaginationToken']
        if token == "":
            pass
        elif token != "":
            while True:
                next_job = roop_tk.rgapi_2(rgapi, resource_type, token)
                total_list.append(next_job['ResourceTagMappingList'])
                token = next_job['PaginationToken']
                if token == "":
                    break
                elif token != "":
                    pass
        if token == "":
            pass
        elif token != "":
            while True:
                next_job = roop_tk.rgapi_2(rgapi, token)
                total_list.append(next_job['ResourceTagMappingList'])
                token = next_job['PaginationToken']
                if token == "":
                    break
                elif token != "":
                    pass
        return len(total_list)
    def rgapi_1(rgapi, resource_type):
        get_first = rgapi.get_resources(
            ResourceTypeFilters=[
                resource_type
            ]
        )
        return get_first
    def rgapi_2(rgapi, resource_type, token):
        get_more = rgapi.get_resources(
            ResourceTypeFilters=[
                resource_type
            ],
            ResourcesPerPage=100,
            PaginationToken = token
        )
        return get_more