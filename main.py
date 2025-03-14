import os
import re
import json
import requests
from datetime import datetime
from requests.exceptions import RequestException

# ####################
# 配置区 (通过环境变量注入)
# ####################
BASE_DOMAIN = "ikuuu.one"  # 主域名配置
EMAIL = os.getenv("EMAIL")  # 登录邮箱
PASSWORD = os.getenv("PASSWD")  # 登录密码
SERVER_CHAN_KEY = os.getenv("SCKEY")  # Server酱Key
PUSHPLUS_TOKEN = os.getenv("TOKEN")  # PushPlus Token

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

# 流量解析正则表达式
TRAFFIC_REGEX = {
    "today": re.compile(r'今日已用[\s\S]*?(\d+\.?\d*)\s*([GMK]B)'),
    "remaining": re.compile(r'剩余流量[\s\S]*?<span class="counter">(\d+\.?\d*)</span>\s*([GMK]B)'),
    "usage": re.compile(r'Used Today\s*</span>\s*<span class="counter">(\d+\.?\d*)\s*([GMK]B)')
}

# ####################
# 工具函数
# ####################

def get_current_time():
    """获取格式化的当前时间"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def format_traffic(value, unit):
    """流量单位标准化"""
    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
    unit = unit.upper().replace("B", "")
    return f"{value}{unit}B"

# ####################
# 通知模块
# ####################

class NotificationManager:
    """统一通知处理类"""
    
    def __init__(self):
        self.status = "success"
        self.messages = []
        self.traffic_data = {}
        
    def add_message(self, message):
        """添加状态消息"""
        self.messages.append(message)
        
    def set_traffic(self, today, remaining):
        """设置流量数据"""
        self.traffic_data = {
            "today": today,
            "remaining": remaining
        }
        
    def send(self, status):
        """发送通知"""
        self.status = status
        content = self._build_content()
        
        # 双通道推送
        if SERVER_CHAN_KEY and SERVER_CHAN_KEY != "1":
            self._send_serverchan(content)
        if PUSHPLUS_TOKEN and PUSHPLUS_TOKEN != "1":
            self._send_pushplus(content)
            
    def _build_content(self):
        """构建通知内容模板"""
        time_str = get_current_time()
        status_icon = "✅" if self.status == "success" else "❌"
        
        content = [
            f"## {status_icon} iKuuu 机场状态报告",
            f"**🕒 执行时间**: {time_str}",
            f"**📧 用户账户**: `{EMAIL}`",
            "---"
        ]
        
        # 添加状态消息
        content.extend([f"- {msg}" for msg in self.messages])
        
        # 添加流量详情
        if self.traffic_data:
            content.extend([
                "---",
                "**📊 流量统计**",
                f"- 今日已用: `{self.traffic_data['today']}`",
                f"- 剩余流量: `{self.traffic_data['remaining']}`"
            ])
            
        return "\n".join(content)
        
    def _send_serverchan(self, content):
        """Server酱推送"""
        url = f"https://sctapi.ftqq.com/{SERVER_CHAN_KEY}.send"
        params = {
            "title": "✅ 签到成功" if self.status == "success" else "❌ 签到失败",
            "desp": content,
            "channel": 9  # 微信+邮件同时推送
        }
        try:
            requests.get(url, params=params, timeout=10)
            print("[通知] Server酱推送成功")
        except RequestException as e:
            print(f"[通知] Server酱推送失败: {str(e)}")
            
    def _send_pushplus(self, content):
        """PushPlus推送"""
        url = "http://www.pushplus.plus/send"
        payload = {
            "token": PUSHPLUS_TOKEN,
            "title": "iKuuu每日报告",
            "content": content,
            "template": "markdown"
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.json().get("code") == 200:
                print("[通知] PushPlus推送成功")
            else:
                print(f"[通知] PushPlus推送失败: {response.text}")
        except RequestException as e:
            print(f"[通知] PushPlus推送异常: {str(e)}")

# ####################
# 核心功能模块
# ####################

class IKuuuClient:
    """iKuuu 服务客户端"""
    
    def __init__(self):
        self.session = requests.Session()
        self.notifier = NotificationManager()
        self.session.headers.update(HEADERS)
        
    def login(self):
        """执行登录操作"""
        try:
            response = self.session.post(
                LOGIN_URL,
                data={"email": EMAIL, "passwd": PASSWORD},
                timeout=15
            )
            result = response.json()
            
            if result.get("ret") == 1:
                print("[登录] 成功")
                self.notifier.add_message("登录状态: 成功")
                return True
                
            error_msg = result.get("msg", "未知错误")
            self.notifier.add_message(f"登录失败: {error_msg}")
            return False
            
        except json.JSONDecodeError:
            self.notifier.add_message("登录失败: 接口返回数据异常")
            return False
        except RequestException as e:
            self.notifier.add_message(f"登录失败: 网络错误 ({str(e)})")
            return False
            
    def checkin(self):
        """执行签到操作"""
        try:
            response = self.session.post(CHECKIN_URL, timeout=10)
            result = response.json()
            
            if result.get("ret") == 1:
                msg = result.get("msg", "签到成功")
                print(f"[签到] {msg}")
                self.notifier.add_message(f"签到结果: {msg}")
                return True
                
            error_msg = result.get("msg", "未知错误")
            self.notifier.add_message(f"签到失败: {error_msg}")
            return False
            
        except json.JSONDecodeError:
            self.notifier.add_message("签到失败: 返回数据解析失败")
            return False
        except RequestException as e:
            self.notifier.add_message(f"签到失败: 网络错误 ({str(e)})")
            return False
            
    def get_traffic_usage(self):
        """获取流量使用情况"""
        try:
            response = self.session.get(USER_INFO_URL, timeout=10)
            html = response.text
            
            # 尝试多种匹配模式
            today_match = TRAFFIC_REGEX["today"].search(html) or TRAFFIC_REGEX["usage"].search(html)
            remain_match = TRAFFIC_REGEX["remaining"].search(html)
            
            today_usage = format_traffic(*today_match.groups()) if today_match else "N/A"
            remain_usage = format_traffic(*remain_match.groups()) if remain_match else "N/A"
            
            print(f"[流量] 今日: {today_usage}, 剩余: {remain_usage}")
            self.notifier.set_traffic(today_usage, remain_usage)
            return True
            
        except RequestException as e:
            self.notifier.add_message(f"流量查询失败: {str(e)}")
            return False

# ####################
# 主执行流程
# ####################

def main():
    print(f"\n====== 任务启动 {get_current_time()} ======")
    
    client = IKuuuClient()
    notifier = client.notifier
    
    try:
        # 执行登录
        if not client.login():
            raise Exception("登录流程失败")
            
        # 执行签到
        if not client.checkin():
            raise Exception("签到流程失败")
            
        # 获取流量数据
        client.get_traffic_usage()
        
        # 标记成功状态
        notifier.send("success")
        
    except Exception as e:
        notifier.add_message(f"系统异常: {str(e)}")
        notifier.send("error")
        
    finally:
        print(f"====== 任务结束 {get_current_time()} ======\n")

if __name__ == "__main__":
    # 环境变量检查
    required_vars = ["EMAIL", "PASSWD"]
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print(f"缺少必要环境变量: {', '.join(missing)}")
        exit(1)
        
    main()
