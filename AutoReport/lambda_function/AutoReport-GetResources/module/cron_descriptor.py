def cron_descriptor(cron):
    def cron_utc_to_kst(schedexp):
        schedexp[1] = int(schedexp[1])
        if schedexp[1] >= 14:
            schedexp[1] = str(schedexp[1] + 9)
        else:
            schedexp[1] = str((schedexp[1] + 9) % 24)
            if schedexp[4] == '?' or schedexp[4] == '*':
                pass
            elif 'L' in schedexp[4]:
                if int(schedexp[4][:-1]) == 7:
                    schedexp[4] = '1L'
                else:
                    schedexp[4] = str(int(schedexp[4][:-1]) + 1) + 'L'
            else:
                days = ''
                for day in schedexp[4].split(','):
                    if day.lower() == 'mon' or day == '2':
                        days += '3,'
                    elif day.lower() == 'tue' or day == '3':
                        days += '4,'
                    elif day.lower() == 'wed' or day == '4':
                        days += '5,'
                    elif day.lower() == 'thu' or day == '5':
                        days += '6,'
                    elif day.lower() == 'fri' or day == '6':
                        days += '7,'
                    elif day.lower() == 'sat' or day == '7':
                        days += '1,'
                    elif day.lower() == 'sun' or day == '1':
                        days += '2,'
                    else:
                        #로깅처리
                        print('Error Occurred')
                schedexp[4] = days[:-1]
        return schedexp
        
    def day_eng_to_kor(day):
        if day.lower() == 'mon' or day == '2':
            return '월요일 '
        elif day.lower() == 'tue' or day == '3':
            return '화요일 '
        elif day.lower() == 'wed' or day == '4':
            return '수요일 '
        elif day.lower() == 'thu' or day == '5':
            return '목요일 '
        elif day.lower() == 'fri' or day == '6':
            return '금요일 '
        elif day.lower() == 'sat' or day == '7':
            return '토요일 '
        elif day.lower() == 'sun' or day == '1':
            return '일요일 '
        else:
            return 'error'
            
    def week_eng_to_kor(day):
        if day == '1':
            return '첫번째 주 '
        elif day == '2':
            return '두번째 주 '
        elif day == '3':
            return '세번째 주 '
        elif day == '4':
            return '네번째 주 '
        elif day == '5':
            return '다섯번째 주 '
        elif day == '6':
            return '여섯번째 '
        else:
            return 'error'
        
    def month_eng_to_kor(month):
        if month.lower() == 'jan' or month.lower() == '1':
            return '1월'
        elif month.lower() == 'feb' or month.lower() == '2':
            return '2월'
        elif month.lower() == 'mar' or month.lower() == '3':
            return '3월'
        elif month.lower() == 'apr' or month.lower() == '4':
            return '4월'
        elif month.lower() == 'may' or month.lower() == '5':
            return '5월'
        elif month.lower() == 'jun' or month.lower() == '6':
            return '6월'
        elif month.lower() == 'jul' or month.lower() == '7':
            return '7월'
        elif month.lower() == 'aug' or month.lower() == '8':
            return '8월'
        elif month.lower() == 'sep' or month.lower() == '9':
            return '9월'
        elif month.lower() == 'oct' or month.lower() == '10':
            return '10월'
        elif month.lower() == 'nov' or month.lower() == '11':
            return '11월'
        elif month.lower() == 'dec' or month.lower() == '12':
            return '12월'
        else:
            return 'error'
        
    schedexp = cron[5:][:-1].split(' ')
    result = ''
    if schedexp[5] != '*':
        if '-' in schedexp[5]:
            result += schedexp[5].split('-')[0] + '년부터 ' + schedexp[5].split('-')[1] + '년까지 '
        else:
            result += schedexp[5]+ '년'
            
    if schedexp[4] != '*':
        if schedexp[4] == '?':
            if schedexp[2] !='*':
                if schedexp[2] == 'L':
                    result += '매년 '
                else:
                    result += '매월 '
            else:
                result += '매일 '
        elif '#' in schedexp[4]:
            temp_data = schedexp[4].split('#')
            result += '매월 ' + week_eng_to_kor(temp_data[1]) + day_eng_to_kor(temp_data[0])
        else:
            if '-' in schedexp[4]:
                result += day_eng_to_kor(schedexp[4].split('-')[0]) + '부터 ' + day_eng_to_kor(schedexp[4].split('-')[1]) + '까지 '
            elif 'L' in schedexp[4]:
                result += '매달 마지막 ' + day_eng_to_kor(schedexp[4][:-1]) + ' '
            else:
                days = ''
                for day in schedexp[4].split(','):
                    days += day_eng_to_kor(day) + '/'
                result += '매주 ' + days[:-1] + ' '
            
    if schedexp[3] != '*':
        if '-' in schedexp[3]:
            result += month_eng_to_kor(schedexp[3].split('-')[0]) + '부터 ' + month_eng_to_kor(schedexp[3].split('-')[1]) + '까지 '
        elif ',' in schedexp[3]:
            result += schedexp[3].replace(',', '월/')
            result += '월 '
    if schedexp[2] != '*':
        if '-' in schedexp[4] or 'L' in schedexp[4]:
            pass
        elif schedexp[2] == '?':
            if schedexp[4] != '*':
                pass
            else:
                result += '매일 '
        elif schedexp[2] == 'L':
            result += '마지막날 '
        else:
            result += schedexp[2] + '일 '
            
    if schedexp[1] != '*':
        if '/' in schedexp[1]:
            result += schedexp[1].split('/')[1] + '시간마다 '
        elif ',' in schedexp[1]:
            pass
        else:
            if int(schedexp[1]) % 12 < 10:
                result += '0' + str(int(schedexp[1]) % 12) + ':'
            else:
                result += str(int(schedexp[1]) % 12) + ':'
            
    if schedexp[0] != '*':
        if '/' in schedexp[1]:
            pass
        elif int(schedexp[0]) < 10:
            if ',' in schedexp[1]:
                hours = ''
                for hour in schedexp[1].split(','):
                    if int(hour) <= 13:
                        hours +=  hour + ':0' + schedexp[0] + 'AM/'
                    else:
                        hours +=  hour + ':0' + schedexp[0] + 'PM/'
                result += hours[:-1]
            else:
                if int(schedexp[1]) <= 13:
                    result += "0" + schedexp[0]+ 'AM'
                else:
                    result += "0" + schedexp[0]+ 'PM'
        else:
            if int(schedexp[1]) <= 13: 
                result += schedexp[0]+ 'AM'
            else:
                result += schedexp[0]+ 'PM'
    return result
    