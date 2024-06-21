import json
import logging
from module import session_connector , sanitize_key, dbModule, invoke_lambda
from services import global_service, region_service
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


#Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    ## Initial ##
    logger.info('input data: {}'.format(json.dumps(event)))
    
    # Session 설정
    session = session_connector.connector(event)
    
    # Access Key 제거
    event = sanitize_key.sanitize_key(event)
    account_id = event['account_id']
    
    # Services
    gs = global_service.Services()
    rs = region_service.Services()
    query = dbModule.Query()
    
    ## Global Service ##
    gs.run(account_id, session, event)
    
    ## Regional Service ##
    for region in event['region']:
        rs.run(account_id, session, region, event)
    # print(json.dumps(event))
    
    # 이번월 데이터 저장
    query.insert_this_month(event)
    
    # 날짜 정보
    run_date = event['run_date']
    if type(run_date) is not date:
        run_date = datetime.strptime(run_date, '%Y-%m-%d').date().replace(day=1)
    
    ## Database ##
    # 전월 데이터 가져오기 / 이번달 데이터 확인 
    event['month_data_0'] = event.pop('this_month')
    event['month_data_1'] = query.select_month_data(account_id, run_date - relativedelta(month=1))
    event['month_data_2'] = query.select_month_data(account_id, run_date - relativedelta(month=2))
    event['month_data_3'] = query.select_month_data(account_id, run_date - relativedelta(month=3))
    
    # Invoke Lambda
    invoke_lambda.invoke_lambda(account_id, event)
    
    