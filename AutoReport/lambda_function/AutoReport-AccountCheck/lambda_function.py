import json
import boto3
import botocore
from datetime import datetime, date, timedelta
import logging


logger = logging.getLogger()
logger.setLevel(logging.INFO)


class check:
    def assume_role(customer):
        sts_client = boto3.client('sts')
        credential=sts_client.assume_role(
            RoleArn="arn:aws:iam::"+customer['account_id']+":role/mzc-assumerole",
            RoleSessionName=customer['account_id'],
            ExternalId="mzc-cms"
        ).get('Credentials')
        return credential


def lambda_handler(event, context):
    
    # 보고서 발행 대상 프로젝트 확인
    project_list = ['FIX_INPUT']
    """
    FIX_INPUT: 위의 Project_list는 데이터를 수집할 Account의 목록입니다. 
    DB 구축 후 report_info Table의 모든 값들을 수집해 다음으로 넘겨주어야 하므로 여기서 데이터를 겟하십시요. 외부에서 수집하는 구조는 사용하시는 jira or db 에 맞게 코드 구현하시면 됩니다.
    
    <customer 변수 샘플>
    {
        'account_id': '고객사 Account Id',
        'customer_name': '고객명',
        'customer_project': 'Account 프로젝트 명',
        'region': ['ap-northeast-2', '리전 리스트'],
        'report_cycle': '분기' | '월간',
        'msp_sales': '담당 영업 이름',
        'msp_level': 'MSP 등급',
        'manager_name': '담당 기술지원 매니저 이름',
        'work_summary': {
            '업무 구분 카테고리': '변경관리 | 보안관리 | 백업관리 | 문제관리 | 사고관리',
            '대상 구분 카테고리' : 'Server | Network | Database | ETC',
            '변경관리-Server': 2,
            '보안관리-ETC': 1
        },
        'work_list': [{
            'service': 'ETC',
            'work_type': '보안관리',
            'work_date': '03월 04일',
            'work_value': 'S3 Browser 및 Policy 관련 티켓 문의 처리'
        }, {
            'service': 'ETC',
            'work_type': '변경관리',
            'work_date': '04월 12일',
            'work_value': '[ISEC] 분기 보고서 정리 및 전달'
        }, {
            'service': 'ETC',
            'work_type': '문제관리',
            'work_date': '04월 13일',
            'work_value': '[ISEC] EC2 AMI 관련 문의 확인 및 답변'
        }, {
            'service': 'ETC',
            'work_type': '문제관리',
            'work_date': '05월 02일',
            'work_value': '[ISEC] 티켓 답변 / proxy서버 관련'
        }]
    }

    """
    for customer in project_list:
        # assume Role check
        try:
            credential = check.assume_role(customer)
        except Exception as e:
            logger.error('[{}-{}({})] assume_role Check: Failed. // error: {}'.format(customer['customer_name'], customer['customer_project'], customer['account_id'], e))
        else:
            # logger.info('[{}({})] - Assuome Role Check: Complate.'.format(customer['customer_name'], customer['account_id']))
            lamb = boto3.client('lambda')
            account_info = {'access_key': credential['AccessKeyId'], 'secret_key': credential['SecretAccessKey'], 'token': credential['SessionToken']}
            account_info.update(customer)
            
            # run_date 추가
            account_info['run_date'] = run_date
            payload = json.dumps(account_info, ensure_ascii=False)
            logger.info('[{}-{}({}): Invoke_Body] \n{}'.format(customer['customer_name'], customer['customer_project'], customer['account_id'], payload))
            
            # Next Function Invoke
            try:
                next_step = lamb.invoke(
                    FunctionName = 'AutoReport-GetResources',
                    InvocationType = 'Event',
                    Payload = payload
                )
                pass
            except Exception as e:
                logger.error('[{}({})] Lambda Invoke: Failed. // error: {}'.format(customer['customer_name']+'-'+customer['customer_project'], customer['account_id'], e))
            else:
                logger.info('[{}-{}({})] Account Check Finish.'.format(customer['customer_name'], customer['customer_project'], customer['account_id']))