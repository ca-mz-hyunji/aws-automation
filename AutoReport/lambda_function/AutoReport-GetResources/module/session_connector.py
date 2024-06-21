import sys
# from pip._internal import main
# main(['install', '-I', '-q', 'boto3', '--target', '/tmp/', '--no-cache-dir', '--disable-pip-version-check'])
# sys.path.insert(0,'/tmp/')
import json
import boto3
import botocore
import logging

#Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def connector(event):

    try:
        account_id = event['account_id']
        session = boto3.Session(
                aws_access_key_id = event['access_key'],
                aws_secret_access_key = event['secret_key'],
                aws_session_token = event['token']
        )
        logger.info('Session Connect Success. Account : {}'.format(account_id))
        return session
    except Exception as e:
        return logger.error('[{}:ERROR] Session Connect Failed. event fallow:\n{}'.format(account_id, event))

    