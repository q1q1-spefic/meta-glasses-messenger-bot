"""
Messenger自动回复 - 改进版
更稳定的消息检测和回复机制
"""

import json
import time
import logging
import requests
from playwright.sync_api import sync_playwright

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MessengerAutoReply:
    """稳定的Messenger自动回复机器人"""

    def __init__(self):
        self.backend_url = "http://localhost:5001"
        self.last_message_text = None
        self.processed_messages = set()  # 记录已处理的消息

        # 加载cookies
        try:
            with open("messenger_auth.json", 'r') as f:
                config = json.load(f)
            self.cookies = config.get('facebook', {}).get('cookies', {})
            logger.info(f"✅ Loaded {len(self.cookies)} cookies")
        except:
            self.cookies = {}
            logger.warning("⚠️  No cookies found, will need to login")

    def get_ai_reply(self, message: str) -> str:
        """获取AI回复"""
        try:
            response = requests.post(
                f"{self.backend_url}/api/conversation-suggest",
                json={"message": message, "context": {"scenario": "general"}},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return data['data']['suggestion']

            logger.error(f"❌ Backend error: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"❌ Backend error: {e}")
            return None

    def run(self, conversation_url: str = None):
        """运行自动回复机器人"""

        with sync_playwright() as p:
            # 启动浏览器
            logger.info("🚀 Starting browser...")
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )

            # 加载cookies
            if self.cookies:
                cookies_list = []
                for name, value in self.cookies.items():
                    cookies_list.append({'name': name, 'value': value, 'domain': '.facebook.com', 'path': '/'})
                    cookies_list.append({'name': name, 'value': value, 'domain': '.messenger.com', 'path': '/'})
                context.add_cookies(cookies_list)
                logger.info("✅ Cookies loaded")

            page = context.new_page()

            # 打开Messenger
            if conversation_url:
                logger.info(f"📱 Opening conversation: {conversation_url}")
                page.goto(conversation_url)
            else:
                logger.info("📱 Opening Messenger home")
                page.goto("https://www.messenger.com/")

            time.sleep(5)

            # 检查是否需要登录
            if "login" in page.url or "checkpoint" in page.url:
                logger.error("❌ Not logged in! Please run messenger_login.py first")
                browser.close()
                return

            logger.info("✅ Logged in to Messenger")
            logger.info("🎯 Monitoring for new messages...")
            logger.info("💬 Send a message from another account or Meta glasses to test!")
            logger.info("")

            # 主循环
            while True:
                try:
                    # 获取所有消息气泡 - 使用更可靠的选择器
                    messages = page.query_selector_all('div[dir="auto"]')

                    if len(messages) > 0:
                        # 获取最后一条消息
                        last_msg_elem = messages[-1]
                        msg_text = last_msg_elem.inner_text().strip()

                        # 过滤掉无效消息
                        if not msg_text or len(msg_text) > 500:
                            time.sleep(2)
                            continue

                        # 过滤系统消息
                        skip_keywords = ['created', 'removed', 'added', 'left', 'joined', 'changed']
                        if any(keyword in msg_text.lower() for keyword in skip_keywords):
                            time.sleep(2)
                            continue

                        # 检查是否是新消息
                        if msg_text != self.last_message_text and msg_text not in self.processed_messages:
                            logger.info(f"\n📩 New message: {msg_text}")

                            # 获取AI回复
                            logger.info("🤖 Generating AI response...")
                            ai_reply = self.get_ai_reply(msg_text)

                            if ai_reply:
                                logger.info(f"💡 AI reply: {ai_reply}")

                                # 发送回复
                                logger.info("📤 Sending reply...")
                                input_box = page.query_selector('div[contenteditable="true"]')

                                if input_box:
                                    input_box.click()
                                    time.sleep(0.3)
                                    input_box.fill(ai_reply)
                                    time.sleep(0.5)
                                    input_box.press('Enter')

                                    logger.info("✅ Reply sent!\n")

                                    # 记录已处理的消息
                                    self.processed_messages.add(msg_text)
                                    self.last_message_text = msg_text

                                    # 限制processed_messages大小，避免内存泄漏
                                    if len(self.processed_messages) > 100:
                                        self.processed_messages.clear()
                                else:
                                    logger.error("❌ Input box not found")
                            else:
                                logger.error("❌ Failed to get AI reply")

                    time.sleep(2)  # 每2秒检查一次

                except KeyboardInterrupt:
                    logger.info("\n⏹️  Stopping...")
                    break
                except Exception as e:
                    logger.error(f"❌ Error: {e}")
                    time.sleep(2)

            browser.close()


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════╗
║   Messenger Auto-Reply Bot for Meta Glasses V2     ║
║                                                      ║
║   ✅ 更稳定的消息检测                                ║
║   ✅ 自动过滤系统消息                                ║
║   ✅ 不会重复回复相同消息                            ║
║                                                      ║
║   确保 Flask 后端运行在 http://localhost:5001       ║
╚══════════════════════════════════════════════════════╝
    """)

    # 可以指定对话URL，或留空监听所有对话
    conversation_url = input("输入Messenger对话URL (直接回车监听所有对话): ").strip()

    if not conversation_url:
        conversation_url = None

    bot = MessengerAutoReply()
    bot.run(conversation_url)
