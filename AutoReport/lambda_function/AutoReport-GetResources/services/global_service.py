import json
import logging
from datetime import datetime, timedelta
from botocore.config import Config

#Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class Services:
    def run(self, account_id, session, event):
        
        # IAM_First
        iam_client, create_report = Services.iam_first(account_id, session)
        
        # S3
        s3_data, len = Services.s3(account_id, session)
        if len: 
            event['this_month']['other'] = []
            event['this_month']['other'].append(s3_data)
        
        # Cloud Front
        cloudfront_data, len = Services.cloudfront(account_id, session)
        if len: 
            event['this_month']['cloud_front'] = []
            event['this_month']['cloud_front'].extend(cloudfront_data)
        
        # Route53
        route53_data, len = Services.route53(account_id, session)
        if len:
            event['this_month']['route53'] = []
            event['this_month']['route53'].extend(route53_data)
        
        # Trusted Advisor
        trusted_advisor_data, len = Services.trusted_advisor(account_id, session)
        if len: 
            event['this_month']['trusted_advisor'] = trusted_advisor_data
        
        # IAM
        iam_used, password_policy, user_list = Services.iam(account_id, iam_client, create_report)
        event['this_month']['iam_summary'] = {
            'iam_summary': iam_used,
            'iam_password_policy': password_policy
        }
        
        event['this_month']['iam_list'] = user_list
        
        logger.info('[Account ID: {}] Global Service Success'.format(account_id))   
    
    
    def cloudfront(account_id, session):
        try:
            cloudfront_client = session.client('cloudfront', 'us-east-1')
            cloudwatch_client = session.client('cloudwatch', 'us-east-1')
            distributions = cloudfront_client.list_distributions()
            
            # distribution 리스트
            distribution_list = []
            id_list = []
            if 'Items' in distributions['DistributionList']:
                for distribution in distributions['DistributionList']['Items']:
                    temp = {}
                    temp['domain_name'] = distribution['DomainName']
                    temp['cname'] = '사용' if distribution['Aliases']['Quantity'] != 0 else '미사용'
                    temp['price_class'] = '전체 영역' if distribution['PriceClass'] == 'PriceClass_All' else '전체 영역 중 남아메리카, 호주, 뉴질랜드 제외' if distribution['PriceClass'] == 'PriceClass_200' else '북미, 유럽, 이스라엘'
                    temp['status'] = '사용' if distribution['Enabled'] == True else '미사용'
                    
                    # 한달간(30일) 총 request값 확인
                    points = cloudwatch_client.get_metric_statistics(
                        Namespace ='AWS/CloudFront',
                        Dimensions = [
                            {'Name': 'DistributionId', 'Value': distribution['Id']},
                            {'Name': 'Region', 'Value': 'Global'}
                        ],
                        StartTime = datetime.now() - timedelta(days=30),
                        EndTime = datetime.now(),
                        Period = 2592000,
                        MetricName = 'Requests',
                        Statistics = ['Sum'],
                    )
                    sum = 0
                    for point in points['Datapoints']:
                        sum += point['Sum']
                    temp['request'] = sum
                    distribution_list.append(temp)
            distribution_list = sorted(distribution_list, key = lambda x:x['request'], reverse = True)
            return distribution_list, len(distribution_list)
        except Exception as e:
            logger.error('[Account ID: {}] CloudFront Service // {}'.format(account_id, e))
            return 0, 0
    
    
    def s3(account_id, session):
        try: 
            s3_client = session.client('s3')
            bucket_list = s3_client.list_buckets().get('Buckets')
            result = {}
            if len(bucket_list):
                result['service'] = 'S3'
                result['region'] = 'Global'
                result['category'] = 'Buckets'
                result['count'] = len(bucket_list)
            return result, len(result)
            
        except Exception as e:
            logger.error('[Account ID: {}] S3 Service // {}'.format(account_id, e))
            return 0, 0
    
    
    def trusted_advisor(account_id, session):
        try:
            trusted_advisor_client = session.client('support', 'us-east-1')
            
            # 기본 폼
            result = {
                "cost_optimizing": [],
                "fault_tolerance": [],
                "performance": [],
                "security": [],
                "service_limits": []
            }
            
            # lambda 관련된 target
            lambda_target = ['L4dfs2Q4C5', 'L4dfs2Q3C3', 'L4dfs2Q3C2', 'L4dfs2Q4C6']
            # check list 가져오기
            with open('./library/trusted_advisor_target.json', 'r') as json_file:
                checks = json.loads(json_file.read());
                check_targets = []
                error_targets = []
                
                # check id만 뽑기
                check_targets = [*checks["checks"]]
                
                # summary 뽑기
                check_summary_results = trusted_advisor_client.describe_trusted_advisor_check_summaries(
                    checkIds = check_targets    
                )
                
                # summary중 error인것들만 뽑기
                for check_summary_result in check_summary_results["summaries"]:
                    if(check_summary_result["status"] == "error"):
                        error_targets.append(check_summary_result["checkId"])
                
                for error_target in error_targets:
                    temp_check_result = {}
                    response = trusted_advisor_client.describe_trusted_advisor_check_result(
                        language='ko',
                        checkId=error_target
                    )
                    check = checks["checks"][error_target]
                    # error중 진짜 error만 찾기
                    temp_result = []
                    for flagged_resource in response["result"]["flaggedResources"]:
                        if(flagged_resource["status"] == "error"):
                            # result 대상 뽑기
                            temp_target = ""
                            targetlen = len(check["target"])
                            if targetlen == 1:
                                if check["target"][0] == 50:
                                    temp_target = "Root 계정"
                                elif check["target"][0] == 51:
                                    temp_target = "IAM 없음"
                                else:
                                    if error_target in lambda_target:
                                        temp_target = str(flagged_resource["metadata"][check["target"][0]-1]).split(':')[6]
                                    else:    
                                        temp_target = str(flagged_resource["metadata"][check["target"][0]-1])
                            elif targetlen == 2:
                                temp_target = str(flagged_resource["metadata"][check["target"][0]-1]) + "(" + str(flagged_resource["metadata"][check["target"][1]-1]) + ")"
                            elif targetlen == 3:
                                temp_target = str(flagged_resource["metadata"][check["target"][0]-1]) + " (현재: " + str(flagged_resource["metadata"][check["target"][1]-1]) + " / 한도: " + str(flagged_resource["metadata"][check["target"][2]-1]) + ")"
                            else:
                                logger.error('[{}:ERROR] Trusted Advisor Service Check target Error.// {}'.format(AccountId, flagged_resource["metadata"]))
                            temp_result.append(temp_target)        
                    temp_check_result["name"] = check["name"]
                    temp_check_result["description"] = check["description"]
                    temp_check_result["result"] = temp_result
                    
                    if(temp_check_result):
                        if(check["category"] == "cost_optimizing" and temp_check_result):
                            result["cost_optimizing"].append(temp_check_result)
                        elif(check["category"] == "fault_tolerance" and temp_check_result):
                            result["fault_tolerance"].append(temp_check_result)            
                        elif(check["category"] == "performance" and temp_check_result):
                            result["performance"].append(temp_check_result)            
                        elif(check["category"] == "security" and temp_check_result):
                            result["security"].append(temp_check_result)                
                        elif(check["category"] == "service_limits" and temp_check_result):
                            result["service_limits"].append(temp_check_result)
                        else:
                            logger.error('[{}:ERROR] Trusted Advisor Service Category Separation Error.// {}'.format(AccountId, temp_check_result))
            
            # 존재하는 대상만 return                
            if(len(result["cost_optimizing"]) and len(result["fault_tolerance"]) and len(result["performance"]) and len(result["security"]) and len(result["service_limits"]) == 0):
                return 0, 0
            else:
                if(len(result["cost_optimizing"]) == 0):
                    del result["cost_optimizing"]
                if(len(result["fault_tolerance"]) == 0):
                    del result["fault_tolerance"]
                if(len(result["performance"]) == 0):
                    del result["performance"]
                if(len(result["security"]) == 0):
                    del result["security"]
                if(len(result["service_limits"]) == 0):
                    del result["service_limits"]
                return result, 1
        # except trusted_advisor_client.exceptions.AccessDeniedException as accessdenied:
        #     logger.info('[Account ID: {}] Trusted Advisor Service // {}'.format(account_id, accessdenied))
        #     return 0, 0
        # except trusted_advisor_client.exceptions.SubscriptionRequiredException as subscript:
        #     logger.info('[Account ID: {}] Trusted Advisor Service // {}'.format(account_id, subscript))
        #     return 0, 0
        except Exception as e:
            logger.error('[Account ID: {}] Trusted Advisor Service // {}'.format(account_id, e))
            return 0, 0
    
    
    def route53(account_id, session):
        try:
            route53_client = session.client('route53', 'us-east-1', config=Config(retries={'max_attempts': 40}))
            host_zone_data = route53_client.list_hosted_zones()
            host_zone_list = host_zone_data['HostedZones']
            next_marker = ''
            while True:
                if 'NextMarker' in host_zone_data:
                    next_marker = host_zone_data['NextMarker']
                    host_zone_data = route53_client.list_hosted_zones(Marker = next_marker)
                    host_zone_list.extend(host_zone_data['HostedZones'])
                else:
                    break
            
            # top 29위
            sorted_data = sorted(host_zone_list, key = lambda x:x['ResourceRecordSetCount'], reverse = True)
            sorted_data_top29 = sorted_data[:29]
            sorted_data_under30 = sorted_data[29:]
            record_check_list = ['A', 'TXT', 'NS', 'CNAME']
            host_zone_info = []
            for host_zone in sorted_data_top29:
                record_sets = route53_client.list_resource_record_sets(HostedZoneId = host_zone['Id'], MaxItems = '300')
                record_set_list = record_sets['ResourceRecordSets']
                next_record_name = ''
                while True:
                    if 'NextRecordName' in record_sets:
                        next_record_name = record_sets['NextRecordName']
                        record_sets = route53_client.list_resource_record_sets(HostedZoneId = host_zone['Id'], StartRecordName = next_record_name, MaxItems = '300')
                        record_set_list.extend(record_sets['ResourceRecordSets'])
                    else:
                        break
                        
                record_sets = {'A': 0, 'TXT': 0, 'NS': 0, 'CNAME': 0}
                record_total_count = 0
                temp = {}
                for record_set in record_set_list:
                    if record_set['Type'] in record_check_list:
                        record_sets[record_set['Type']] += 1
                        record_total_count += 1
                    else:
                        record_sets['ETC'] = record_sets.get('ETC', 0) + 1
                        record_total_count += 1
                temp['domain_name'] = host_zone['Name']
                temp['record'] = record_sets
                temp['total'] = record_total_count
                temp['type'] = 'Public' if host_zone['Config']['PrivateZone'] == False else 'Private'
                host_zone_info.append(temp)
            
            # under 30위
            if len(sorted_data_under30):
                record_counter = 0
                for host_zone in sorted_data_under30:
                    record_counter += host_zone['ResourceRecordSetCount']
                temp = {}
                temp['domain_name'] = '이외 ' + str(len(sorted_data_under30)) + ' 개 도메인'
                temp['record'] = {'A': ' ', 'TXT': ' ', 'NS': ' ', 'CNAME': ' ', 'ETC': ' '}
                temp['total'] = record_counter
                temp['type'] = ' '
                host_zone_info.append(temp)
            return host_zone_info, len(host_zone_info)
        except Exception as e:
            logger.error('[Account ID: {}] Route53 Service // {}'.format(account_id, e))
            return 0, 0
    
    
    def iam_first(account_id, session):
        try:
            iam = session.client('iam')
            create_report = iam.generate_credential_report()
            return iam, create_report
        except Exception as e:
            logger.error('[Account ID: {}] IAM_First Service // {}'.format(account_id, e))
            return 0, 0
    
    
    def iam(account_id, iam, create_report):
        try:
            # User List
            get_report = iam.get_credential_report().get('Content').decode('ascii').split('\n')
            index = get_report.pop(0).split(',')
            del index[16:]
            del index[14]
            del index[12]
            del index[11]
            del index[9]
            del index[6]
            del index[1:3]
            
            user_list = []
            for line in get_report:
                line = line.split(',')
                del line[16:]
                del line[14]
                del line[12]
                del line[11]
                del line[9]
                del line[6]
                del line[1:3]
                user_list.append(dict(zip(index, line)))
            root_user_mfa = user_list.pop(0).get('mfa_active')
            if root_user_mfa == 'false':
                root_user_mfa = 'X'
            elif root_user_mfa == 'true':
                root_user_mfa = 'O'
            for user in user_list:
                for u in user.keys():
                    if '+00:00' in user[u]:
                        time_string = user[u].split('+')[0]
                        now = datetime.now()
                        target_time = datetime.strptime(time_string, '%Y-%m-%dT%H:%M:%S') + timedelta(hours=9)
                        old_days = str(now - target_time)
                        if 'days' in old_days:
                            user[u] = int(old_days.split(' ')[0])
                        else:
                            user[u] = 0
                    elif 'N/A' in user[u]:
                        user[u] = '미사용'
                if user['password_enabled'] == 'false':
                    user['password_last_used'] = '-'
                    user['password_last_changed'] = '-'
                    user['mfa_active'] = '-'
                if user['access_key_1_active'] == 'true':
                    if user['access_key_2_active'] == 'false':
                        user['access_key_count'] = 1
                        user['access_key_used_date'] = user['access_key_1_last_used_date']
                    elif user['access_key_2_active'] == 'true':
                        user['access_key_count'] = 2
                        if type(user['access_key_1_last_used_date']) == str:
                            user['access_key_used_date'] = user['access_key_2_last_used_date']
                        elif type(user['access_key_2_last_used_date']) == str:
                            user['access_key_used_date'] = user['access_key_1_last_used_date']
                        elif type(user['access_key_1_last_used_date']) == int and type(user['access_key_1_last_used_date']) == int:
                            user['access_key_used_date'] = sorted([user['access_key_1_last_used_date'], user['access_key_2_last_used_date']],reverse=True)[0]
                elif user['access_key_1_active'] == 'false':
                    if user['access_key_2_active'] == 'true':
                        user['access_key_count'] = 1
                        user['access_key_used_date'] = user['access_key_2_last_used_date']
                    elif user['access_key_2_active'] == 'false':
                        user['access_key_count'] = 0
                        user['access_key_used_date'] = '-'
                del user['access_key_1_active']
                del user['access_key_2_active']
                del user['access_key_1_last_used_date']
                del user['access_key_2_last_used_date']
                for u in user.keys():
                    if user[u] == 'no_information':
                        user[u] = '-'
                    if user[u] == 'true':
                        user[u] = '활성화'
                    if user[u] == 'false':
                        user[u] = '비활성화'
                    if u == 'password_last_used' or u == 'password_last_changed' or u == 'access_key_used_date':
                        if type(user[u]) == int:
                            if user[u] == 0:
                                user[u] = '1일 미만'
                            else:
                                user[u] = str(user[u])+' 일 전'
            ##Password Policy
            try:
                policys = iam.get_account_password_policy().get('PasswordPolicy')
            except iam.exceptions.NoSuchEntityException as e:
                # logger.info('[Empty] {}'.format(e))
                password_policy = {'root_mfa_active': root_user_mfa}
            else:
                # PasswordReusePrevention
                for p in policys.keys():
                    if policys[p] == True:
                        policys[p] = 'O'
                    elif policys[p] == False:
                        policys[p] = 'X'
                password_policy = {
                    'root_mfa_active': root_user_mfa, # Root MFA
                    'minimum_password_length': policys['MinimumPasswordLength'], # 암호길이
            		'require_symbols': policys['RequireSymbols'], # 암호특수문자
            		'require_numbers': policys['RequireNumbers'], # 암호 숫자
            		'require_uppercase_characters': policys['RequireUppercaseCharacters'], # 암호 대문자
            		'require_lowercase_characters': policys['RequireLowercaseCharacters'], # 암호 소문자
            		'expire_passwords': policys['ExpirePasswords'] #암호 만료
                }
                # 암호 만료 활성화 / 암호 재사용 기간
                if 'MaxPasswordAge' in policys:
                    password_policy['max_password_age'] = policys['MaxPasswordAge']
                else:
                    password_policy['max_password_age'] = '-'
                if 'PasswordReusePrevention' in policys:
                    password_policy['prevent_password_reuse_enable'] = 'O'
                    password_policy['password_reuse_prevention'] = policys['PasswordReusePrevention']
                else:
                    password_policy['prevent_password_reuse_enable'] = 'X'
                    password_policy['password_reuse_prevention'] = '-'
            iam_summery = iam.get_account_summary().get('SummaryMap')
            iam_used = {
                'group': iam_summery['Groups'],
                'user': iam_summery['Users'],
                'role': iam_summery['Roles'],
                'policy': iam_summery['Policies']
            }
            return iam_used, password_policy, user_list
        except Exception as e:
            logger.error('[Account ID: {}] IAM_Main Service // {}'.format(account_id, e))
            return 0, 0, 0