import os
import re
import json
import requests
from datetime import datetime
from requests.exceptions import RequestException
from requests_toolbelt import MultipartEncoder

# ####################
# 配置区 (与您的Secrets完全匹配)
# ####################
BASE_DOMAIN = "ikuuu.one"
EMAIL = os.getenv("EMAIL")        # 使用您现有的Secrets名称
PASSWORD = os.getenv("PASSWD")    # 使用您现有的Secrets名称
SCKEY = os.getenv("SCKEY")        # Server酱Key
TOKEN = os.getenv("TOKEN")        # PushPlus Token

# ####################
# 常量配置
# ####################
BASE_URL = f"https://{BASE_DOMAIN}"
LOGIN_URL = f"{BASE_URL}/auth/login"
CHECKIN_URL = f"{BASE_URL}/user/checkin"
USER_INFO_URL = f"{BASE_URL}/user"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/auth/login"
}

# 流量解析正则表达式（根据新界面调整）
TRAFFIC_REGEX = re.compile(
    r'剩余流量<\/span>[\s\S]*?<span class="counter">([\d.]+)\s*([A-Z]+B)<\/span>.*?今日已用<\/span>[\s\S]*?<span class="counter">([\d.]+)\s*([A-Z]+B)<\/span>',
    re.DOTALL
)

# ####################
# 工具函数
# ####################
def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ####################
# 核心功能模块
# ####################
class IKuuuClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        
    def login(self):
        try:
            form = MultipartEncoder(fields={
                'email': EMAIL,
                'passwd': PASSWORD
            })
            
            response = self.session.post(
                LOGIN_URL,
                data=form,
                headers={'Content-Type': form.content_type},
                timeout=15
            )
            return self._handle_response(response, "登录")
        except RequestException as e:
            return f"❌ 登录失败：{str(e)}"

    def checkin(self):
        try:
            response = self.session.post(CHECKIN_URL, timeout=10)
            data = response.json()
            if data.get("ret") == 1:
                return f"✅ 签到成功：{data.get('msg')}"
            elif "已经签到" in data.get('msg', ''):
                return f"😎 已经签到了"
            else:
                return f"❌ 签到失败：{data.get('msg')}"
        except json.JSONDecodeError:
            return f"❌ 签到失败：接口返回数据异常"
        except RequestException as e:
            return f"❌ 签到失败：{str(e)}"

    def get_traffic(self):
        try:
            response = self.session.get(USER_INFO_URL, timeout=15)
            match = TRAFFIC_REGEX.search(response.text)
            if match:
                remain = f"{match.group(1)}{match.group(2)}"
                today_used = f"{match.group(3)}{match.group(4)}"
                return f"今日已用：{today_used} | 剩余流量：{remain}"
            return "流量查询失败：未匹配到流量数据"
        except RequestException as e:
            return f"❌ 流量查询失败：{str(e)}"

    def _handle_response(self, response, action):
        try:
            data = response.json()
            if data.get("ret") == 1:
                return f"✅ {action}成功：{data.get('msg')}"
            return f"❌ {action}失败：{data.get('msg')}"
        except json.JSONDecodeError:
            return f"❌ {action}失败：接口返回数据异常"

# ####################
# 通知模块
# ####################
def send_notification(status, traffic_info):
    timestamp = get_current_time()
    
    # Server酱通知
    if SCKEY and SCKEY != "1":
        try:
            title = "✅ 签到成功" 
            if "失败" in status:
                title = "❌ 签到失败"
            content = f"""
            **账户状态通知**
            
            - 邮箱账户：`{EMAIL}`
            - 执行时间：{timestamp}
            - {traffic_info}
            """
            requests.post(
                f"https://sctapi.ftqq.com/{SCKEY}.send",
                params={"title": title, "desp": content.strip()}
            )
        except Exception:
            pass

    # PushPlus通知
    if TOKEN and TOKEN != "1":
        try:
            content = f"""
            ## 签到状态报告
            - **账户**：{EMAIL}
            - **时间**：{timestamp}
            - **结果**：{status}
            - **流量信息**：{traffic_info}
            """
            requests.post(
                "http://www.pushplus.plus/send",
                json={
                    "token": TOKEN,
                    "title": "iKuuu签到通知",
                    "content": content.strip(),
                    "template": "markdown"
                }
            )
        except Exception:
            pass

# ####################
# 主执行流程
# ####################
def main():
    print(f"\n====== 任务启动 {get_current_time()} ======")
    
    if not all([EMAIL, PASSWORD]):
        print("❌ 请配置EMAIL和PASSWD环境变量")
        exit(1)
    
    client = IKuuuClient()
    
    # 登录
    login_result = client.login()
    print(login_result)
    
    if "成功" in login_result:
        # 签到
        checkin_result = client.checkin()
        print(checkin_result)
        
        # 获取流量
        traffic_info = client.get_traffic()
        print(traffic_info)
        
        # 发送通知
        status_for_notify = "成功" 
        if "失败" in checkin_result or "异常" in checkin_result:
            status_for_notify = "失败"
        send_notification(status_for_notify, traffic_info)
    else:
        send_notification("失败", login_result)
    
    print(f"====== 任务结束 {get_current_time()} ======\n")

if __name__ == "__main__":
    main()
