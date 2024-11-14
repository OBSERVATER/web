#记得下载requests库！！！！
#pip install requests
import sys
import requests
import json
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor


Authorization=''
 #personStatus1是位置签到，0是二维码或者数字签到，2是一键签到

def log_in(a,b):#d登录
    global userid
    global Authorization
    #print('请输入账号:')
    loginName=a
    #print('请输入密码')
    password=b
    data = {
    "loginName": loginName,
    "password": hashlib.md5(password.encode()).hexdigest(),
    "device": "HUAWEI-HELL",
    "appVersion":"36",
    "webEnv": "1"
    }
    headers = {
        'User-Agent': 'App ulearning Android',
        'Connection': 'close',
        'Accept-Language': 'CN',
        'uversion': "2",
        'Content-Type': 'application/json;charset=UTF-8'
    }
    url = 'https://apps.ulearning.cn/login'
    dat=json.dumps(data,sort_keys=True)
    resp = requests.post(url, headers=headers,data=dat)
    print(resp.text)
    Authorization=resp.json()['token']
    userid=resp.json()['userID']
    resp.close()

def sign_in(class_id,subject,location,address,log_id):#签到
    time.sleep(2.7)
    global Authorization
    global personStatus
    # getclassid()
    # getcode()
    url='https://apps.ulearning.cn/newAttendance/signByStu'
    header={
        'Authorization':Authorization,
        'User-Agent':'Mozilla/5.0 (Linux; Android 12; RNA-AN00 Build/HONORRNA-AN00; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/99.0.4844.88 Mobile Safari/537.36 umoocApp umoocApp -zh-CN',
        'Content-Type':'application/json;charset=UTF-8',
        'Referer':'https://umobile.ulearning.cn/'
    }
    # if personStatus==1:
    data=json.dumps({"attendanceID":class_id,"classID":subject,"userID":userid,"location":location,"address":address,"enterWay":1,"attendanceCode":log_id},sort_keys=True)
    # elif personStatus==0:
    #     data=json.dumps({"attendanceID":class_id,"classID":subject,"userID":userid,"location":'',"address":'',"enterWay":1,"attendanceCode":log_id},sort_keys=True)
    # elif personStatus==2:
    #     data=json.dumps({"attendanceID":class_id,"classID":subject,"userID":userid,"location":'',"address":'',"enterWay":1,"attendanceCode":''},sort_keys=True)
    resp=requests.post(url=url,headers=header,data=data)
    # print('我签到了！！！')
    if resp.text=='':
        return
    print(resp.text)
    resp.close()
    # return
    


def getcode(class_id,subject):#获取数字码和二维码
    global Authorization
    global log_id,personStatus
    global location,address
    url=f'https://classroomapi.ulearning.cn/newAttendance/getNewAttendanceDetail/{class_id}/4/1'
    header={
        'Authorization':Authorization,
        'User-Agent':'Mozilla/5.0 (Linux; Android 12; RNA-AN00 Build/HONORRNA-AN00; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/99.0.4844.88 Mobile Safari/537.36 umoocApp umoocApp -zh-CN',
    }
    resp=requests.get(url,headers=header)

    # print(resp.text)
    try:
        json_response = resp.json()
        if 'attendanceCode' in json_response:
            personStatus=0
            log_id = json_response['attendanceCode']
            sign_in(class_id,subject,'','',log_id)
    
        elif 'address' in json_response:
            personStatus=1
            # print(json_response['address'])
            address=json_response['address']
            location=json_response['location']
            
            sign_in(class_id,subject,location,address,'')
        resp.close()
    except json.decoder.JSONDecodeError as e:
        return
        # print(f"JSONDecodeError: {e}")
        # print(f"Response text: {resp.text}")

    # if 'attendanceCode' in json_response:
    #     personStatus=0
    #     log_id = json_response['attendanceCode']
    #     sign_in(class_id,subject,'','',log_id)
    #     # print(log_id)
    # elif 'address' in json_response:
    #     personStatus=1
    #     # print(json_response['address'])
    #     address=json_response['address']
    #     location=json_response['location']
    #     sign_in(class_id,subject,location,address,'')
    # resp.close()
            
def getclassid(id,subject):#获取参与点名参数
    global Authorization,personStatus
    url=f'https://courseapi.ulearning.cn/appHomeActivity/v4/{id}'
    
    header={
        'Authorization':Authorization,
        'User-Agent':'Mozilla/5.0 (Linux; Android 12; RNA-AN00 Build/HONORRNA-AN00; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/99.0.4844.88 Mobile Safari/537.36 umoocApp umoocApp -zh-CN',
        'Content-Type':'application/json;charset=UTF-8',
        'Referer':'https://umobile.ulearning.cn/'
    }
    resp=requests.get(url,headers=header)
    resp.close()
    # print(resp.text)
    # print(resp.json()['otherActivityDTOList'])
    id_list=resp.json()['otherActivityDTOList']
    count=0
    # with ThreadPoolExecutor(30) as f:
    for id in id_list:
        if(count==2):
            break
        if id['status']==3:
            count=count+1
            # class_id=int(id['relationId'])
            # print('已截止')
            # getcode(class_id,subject)
            continue
        else:
            class_id=int(id['relationId'])
            if 'personStatus' in id:
                count=count+1
                personStatus=int(id['personStatus'])   
                getcode(class_id,subject)
            # print('进入了！！！！')    
    # print(course['name'] +'本周任务已完成或截止')
    # print('')
def getclass():
    global Authorization,id,subject
    for page in range(1,3):
        url=f'https://courseapi.ulearning.cn/courses/students?keyword=&publishStatus=1&type=1&pn={page}&ps=15&lang=zh'
        header={
            "Authorization":Authorization,
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp=requests.get(url,headers=header)
        resp.encoding='utf-8'
        lists=resp.json()['courseList']
        for course in lists:
            print(course['name'] + ' ' + str(course['classId']))
            if course['classId']==697864:
                print('已跳过')
                continue
            # print(course['name'] + ' ' + str(course['classId']))
            id=course['id']
            subject=course['classId']
            
            getclassid(id,subject)
           

if __name__ =='__main__':#主函数
    try:
        time_be = int(time.time()) 
        log_in(sys.argv[1],sys.argv[2])
        getclass()
        time_ov=int(time.time()-time_be)
        # input('Press <Enter>')
        print('运行时间为' + str(time_ov))
    except Exception as e:
    # 捕获所有异常，并将异常对象存储在变量e中
        print("An error occurred:", e)



