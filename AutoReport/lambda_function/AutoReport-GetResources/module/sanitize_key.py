def sanitize_key(event):
    del event['access_key']
    del event['secret_key']
    del event['token']
    event['this_month'] = {}
    event['work_summary'] = {}
    event['work_summary'] = event['resources']['works']['count']
    event['work_list'] = []
    event['work_list'] = event['resources']['works']['work_list']
    del event['resources']
    return event