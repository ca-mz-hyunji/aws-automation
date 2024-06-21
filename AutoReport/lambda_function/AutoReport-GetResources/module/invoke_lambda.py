import json
import boto3 
import logging

#Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def invoke_lambda(account_id, event):
    payload = json.dumps(event)
    try:
        logger.info('[{}-{}({}): Invoke_Body] \n{}'.format(event['customer_name'], event['customer_project'], account_id, payload))
        lamb = boto3.client('lambda')
        next_step = lamb.invoke(
            FunctionName = 'AutoReport-PlacingPPT',
            InvocationType = 'Event',
            Payload = payload
        )
    except Exception as e:
        logger.error('[{}:ERROR] Lambda Invoke Error. {}'.format(account_id, e))
        logger.info('{}'.format(payload))
    else:
        logger.info('[{}-{}({})] Get Resource Finish.'.format(event['customer_name'], event['customer_project'], account_id))