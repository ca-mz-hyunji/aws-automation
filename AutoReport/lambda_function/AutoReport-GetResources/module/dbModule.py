import json
import pymysql
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


#Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class WriteDatabase():
    def __init__(self):
        """DB 구축 후 접속 정보 입력"""
        self.db = pymysql.connect(host='FIX_INPUT',
                                  user='FIX_INPUT',
                                  password='FIX_INPUT',
                                  db='FIX_INPUT',
                                  charset='utf8mb4')
        self.cursor = self.db.cursor(pymysql.cursors.DictCursor)

    def execute(self, query, args={}):
        self.cursor.execute(query, args)
        
    def executeBulk(self, query, args={}):
        self.cursor.executemany(query, args)

    def executeOne(self, query, args={}):
        self.cursor.execute(query, args)
        row = self.cursor.fetchone()
        return row

    def executeAll(self, query, args={}):
        self.cursor.execute(query, args)
        row = self.cursor.fetchall()
        return row

    def executeCount(self, query, args={}):
        self.cursor.execute(query, args)
        rows = self.cursor.rowcount
        return rows

    def commit(self):
        self.db.commit()
        
    def rollback(self):
        self.db.rollback()

    def close(self):
        self.db.close()

class ReadDatabase():
    def __init__(self):
        self.db = pymysql.connect(host='FIX_INPUT',
                                  user='FIX_INPUT',
                                  password='FIX_INPUT',
                                  db='FIX_INPUT',
                                  charset='utf8mb4')
        self.cursor = self.db.cursor(pymysql.cursors.DictCursor)

    def execute(self, query, args={}):
        self.cursor.execute(query, args)

    def executeOne(self, query, args={}):
        self.cursor.execute(query, args)
        row = self.cursor.fetchone()
        return row

    def executeAll(self, query, args={}):
        self.cursor.execute(query, args)
        row = self.cursor.fetchall()
        return row

    def executeCount(self, query, args={}):
        self.cursor.execute(query, args)
        rows = self.cursor.rowcount
        return rows
        
    def commit(self):
        self.db.commit()
        
    def rollback(self):
        self.db.rollback()
        
    def close(self):
        self.db.close()
        
class Query:
    def insert_this_month(self, event):
        try:
            W_db_class = WriteDatabase()
            json_result = json.dumps(event['this_month'], ensure_ascii=False)
            write_nowdata = ''
            write_sql = (
                'INSERT INTO report_data (date, resource, account_id, version) VALUES (%s, %s, %s, %s)'
            )
            write_nowdata = W_db_class.executeOne(write_sql, (datetime.now(),  json_result, event['account_id'], '2'))
            # write_nowdata = W_db_class.executeOne(write_sql, ('2022-01-31',  json_result, event['account_id'], '2'))
            W_db_class.commit()
            W_db_class.close()
        except Exception as e:
            logger.error('[Account ID: {}][Database Error] Insert This Month Failed. // {}'.format(event['account_id'], e))
    
    
    def insert_pms_info(self, event):
        try:
            W_db_class = WriteDatabase()
            write_nowdata = ''
            write_sql = (
                'INSERT INTO report_info (account_id, customer_name, customer_project, report_cycle, msp_level, msp_sales, manager_name, region, date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)'
            )
            region_str = ''
            for i in event["region"]:
                region_str += i+","
            if region_str != '':
                region_str = region_str[:-1]
            write_nowdata = W_db_class.executeOne(write_sql, (event["account_id"], event["customer_name"], event["customer_project"], event["report_cycle"], event["msp_level"], event["msp_sales"], event["manager_name"], region_str, datetime.now()))
            # write_nowdata = W_db_class.executeOne(write_sql, (event["account_id"], event["customer_name"], event["customer_project"], event["report_cycle"], event["msp_level"], event["msp_sales"], event["manager_name"], region_str, '2022-01-31'))
            W_db_class.commit()
            W_db_class.close()
        except Exception as e:
            logger.error('[Account ID: {}][Database Error] Insert PMS Info Failed. // {}'.format(event['account_id'], e))
                
    def select_month_data(self, account_id, select_date):
        start_date = select_date.replace(day=1)
        last_date = select_date.replace(day=1) + relativedelta(months=1) - timedelta(days=1)
        try:
            R_db_class = ReadDatabase()
            read_sql = (
                'SELECT resource FROM report_data '+
                'WHERE date between %s AND %s '+
                'AND account_id = %s '+
                'AND version = "2" '+
                'ORDER BY no DESC LIMIT 1'
            )
            data = R_db_class.executeOne(read_sql, (start_date, last_date, account_id))
            if data == None:
                return {}
            else:
                return json.loads(data['resource'])
        except Exception as e:
            logger.error('[Account ID: {}][Database Error] Select Last Month Failed. // {}'.format(account_id, e))
            return {}
