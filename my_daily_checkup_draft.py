import boto3
import logging
import json
import os
import urllib3
from datetime import datetime, timedelta, timezone
import base64

# Set up logging
logger = logging.getLogger()    # Create a logger
logger.setLevel(logging.INFO)   # Configure logger to log messages of INFO level and above

# Atlassian configuration
BASE_URL = 'https://mzdevs.atlassian.net/rest/api/2'
USERNAME = 'hji.kim@mz.co.kr'
API_TOKEN = '''ATATT3xFfGF0fhTMqA1Evu9ZVXPiXQ2vD6-xYBH5Cbh2vH_bue37tbFCKyy5pWwIFtV9C1LUB1-
            s3dGxHHo4D3BwoH5MkhieDaU_xjVGB-XK7xXJJJUPlagmwl0W5iuEL53Tes1I8PxvGznbFlklPUxmz
            3KXwNmSORQGjCeX23q2tc_-DbJfA8c=3AB3672E'''  # Label = daily_checkup
# Confluence configuration
CONFLUENCE_SPACE_ID= 'CCSD'
CONFLUENCE_PARENT_PAGE_ID = '3484778720'

http = urllib3.PoolManager()

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

def create_daily_report():
    today = datetime.now().strftime('%Y-%m-%d')
    title = f"Daily Checkup Report for {today}"
    # logger.info(f'Starting daily checkup for {today}...')
    # report = [f"*[{title}]*\n"]
    report_title = f"Weekly Inspection Report - {last_week.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}"
    report = [f"<h1>{report_title}</h1>"]
    createconfluence_page_link = create_confluence_page(f"{report_title}", "\n".join(report))
    
    return {
        'statusCode': 200,
        'body': 'Daily checkup completed successfully'
    }

#############################################################

def main():
    print(create_daily_report())

if __name__=='__main__':
    main()