"""
Messenger自动回复 - 简化版
直接监听当前对话的新消息并回复
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


class SimpleMessengerBot:
    """简化的Messenger自动回复"""

    def __init__(self):
        self.backend_url = "http://localhost:5001"
        self.last_message_text = None

        # 加载cookies
        try:
            with open("messenger_auth.json", 'r') as f:
                config = json.load(f)
            self.cookies = config.get('facebook', {}).get('cookies', {})
            logger.info(f"✅ Loaded {len(self.cookies)} cookies")
        except:
            self.cookies = {}
            logger.warning("⚠️  No cookies found")

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

            return "抱歉，暂时无法回复。"
        except Exception as e:
            logger.error(f"❌ Backend error: {e}")
            return "抱歉，暂时无法回复。"

    def run(self, conversation_url: str):
        """运行自动回复机器人"""

        with sync_playwright() as p:
            # 启动浏览器
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

            page = context.new_page()

            logger.info(f"🚀 Opening: {conversation_url}")
            page.goto(conversation_url)
            time.sleep(5)

            if "login" in page.url:
                logger.error("❌ Not logged in!")
                return

            logger.info("✅ Ready! Monitoring for new messages...")
            logger.info("💬 Send a message from Meta glasses to test!\n")

            # 主循环
            while True:
                try:
                    # 方法1: 获取所有消息气泡
                    # Messenger的消息通常在 div[dir="auto"] 中
                    messages = page.query_selector_all('div[dir="auto"]')

                    if len(messages) > 0:
                        # 获取最后一条消息
                        last_msg_elem = messages[-1]
                        msg_text = last_msg_elem.inner_text().strip()

                        # 检查是否是新消息
                        if msg_text and msg_text != self.last_message_text:
                            # 简单判断：如果消息在页面左侧，可能是对方发的
                            # 更简单的方法：直接检查是否是新的不同的消息就回复

                            # 跳过系统消息
                            if len(msg_text) > 100 or "created" in msg_text.lower() or "removed" in msg_text.lower():
                                time.sleep(2)
                                continue

                            logger.info(f"\n📩 Detected message: {msg_text}")

                            # 获取AI回复
                            logger.info("🤖 Getting AI response...")
                            ai_reply = self.get_ai_reply(msg_text)
                            logger.info(f"💡 AI says: {ai_reply}")

                            # 发送回复
                            logger.info("📤 Sending reply...")

                            # 查找输入框并发送
                            input_box = page.query_selector('div[contenteditable="true"]')
                            if input_box:
                                input_box.click()
                                time.sleep(0.3)
                                input_box.fill(ai_reply)
                                time.sleep(0.5)
                                input_box.press('Enter')

                                logger.info("✅ Reply sent!\n")

                                # 更新最后一条消息
                                self.last_message_text = msg_text
                            else:
                                logger.error("❌ Input box not found")

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
║   Messenger Auto-Reply Bot (Simple Version)        ║
║                                                      ║
║   确保 Flask 后端运行在 http://localhost:5001       ║
╚══════════════════════════════════════════════════════╝
    """)

    # 从截图看，你的对话URL是:
    # https://messenger.com/t/3706975126099243/

    conversation_url = input("输入Messenger对话URL (或直接Enter使用默认): ").strip()

    if not conversation_url:
        # 使用你截图中的URL
        conversation_url = "https://messenger.com/t/3706975126099243/"

    bot = SimpleMessengerBot()
    bot.run(conversation_url)
