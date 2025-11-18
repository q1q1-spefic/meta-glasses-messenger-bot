"""
Messenger自动回复 - 调试版
包含测试模式，可以回复所有消息（包括自己的）
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


class MessengerAutoReplyDebug:
    """调试版Messenger自动回复"""

    def __init__(self, test_mode=True):
        self.backend_url = "http://localhost:5001"
        self.last_message_text = None
        self.processed_messages = set()
        self.own_sent_messages = set()  # Track messages sent by this bot
        self.test_mode = test_mode  # 测试模式下回复所有消息
        self.message_count = 0

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
            logger.info(f"🔄 Calling backend at {self.backend_url}/api/conversation-suggest")
            response = requests.post(
                f"{self.backend_url}/api/conversation-suggest",
                json={"message": message, "context": {"scenario": "general"}},
                timeout=10
            )

            logger.info(f"📡 Backend response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                logger.info(f"📦 Backend response data: {data}")
                return data['data']['suggestion']

            logger.error(f"❌ Backend error: {response.status_code} - {response.text}")
            return None
        except Exception as e:
            logger.error(f"❌ Backend exception: {e}")
            return None

    def run(self, conversation_url: str = None):
        """运行自动回复机器人"""

        logger.info(f"🔧 Test mode: {'ENABLED' if self.test_mode else 'DISABLED'}")
        logger.info(f"   (Will {'reply to ALL messages including own' if self.test_mode else 'only reply to others messages'})")

        with sync_playwright() as p:
            logger.info("🚀 Launching browser...")
            browser = p.chromium.launch(
                headless=False,
                args=['--window-size=1200,800']
            )
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
                page.goto(conversation_url, wait_until='domcontentloaded', timeout=60000)
            else:
                logger.info("📱 Opening Messenger home")
                page.goto("https://www.messenger.com/", wait_until='domcontentloaded', timeout=60000)

            time.sleep(5)

            # 检查是否需要登录
            if "login" in page.url or "checkpoint" in page.url:
                logger.error(f"❌ Not logged in! Current URL: {page.url}")
                logger.error("   Please run messenger_login.py first")
                browser.close()
                return

            logger.info(f"✅ Logged in! Current URL: {page.url}")
            logger.info("🎯 Starting to monitor messages...")
            logger.info("")

            # 主循环
            check_count = 0
            while True:
                try:
                    check_count += 1
                    logger.info(f"🔍 Check #{check_count} - Looking for messages...")

                    # 获取所有消息气泡
                    messages = page.query_selector_all('div[dir="auto"]')
                    logger.info(f"   Found {len(messages)} div[dir=\"auto\"] elements")

                    if len(messages) > 0:
                        # 显示最后几条消息用于调试
                        logger.info(f"   Last 3 messages:")
                        for i, msg in enumerate(messages[-3:]):
                            text = msg.inner_text().strip()[:50]
                            logger.info(f"      [{i}] {text}...")

                        # 获取最后一条消息
                        last_msg_elem = messages[-1]
                        msg_text = last_msg_elem.inner_text().strip()

                        logger.info(f"   📝 Last message: '{msg_text}'")

                        # 过滤掉无效消息
                        if not msg_text:
                            logger.info("   ⏭️  Skipped: Empty message")
                            time.sleep(3)
                            continue

                        if len(msg_text) > 500:
                            logger.info("   ⏭️  Skipped: Message too long (>500 chars)")
                            time.sleep(3)
                            continue

                        # 过滤系统消息
                        skip_keywords = ['created', 'removed', 'added', 'left', 'joined', 'changed']
                        if any(keyword in msg_text.lower() for keyword in skip_keywords):
                            logger.info(f"   ⏭️  Skipped: System message")
                            time.sleep(3)
                            continue

                        # 检查是否已处理
                        if msg_text in self.processed_messages:
                            logger.info(f"   ⏭️  Skipped: Already processed")
                            time.sleep(3)
                            continue

                        # 检查是否是新消息
                        if msg_text == self.last_message_text:
                            logger.info(f"   ⏭️  Skipped: Same as last message")
                            time.sleep(3)
                            continue

                        # 在非测试模式下，跳过自己发送的消息
                        if not self.test_mode:
                            # 检查消息是否是刚刚由bot发送的
                            if msg_text in self.own_sent_messages:
                                logger.info(f"   ⏭️  Skipped: Own message (sent by bot)")
                                self.last_message_text = msg_text
                                self.processed_messages.add(msg_text)
                                time.sleep(3)
                                continue

                        # 新消息！开始处理
                        self.message_count += 1
                        logger.info(f"\n{'='*60}")
                        logger.info(f"📩 NEW MESSAGE #{self.message_count}: {msg_text}")
                        logger.info(f"{'='*60}")

                        # 获取AI回复
                        logger.info("🤖 Requesting AI response from backend...")
                        ai_reply = self.get_ai_reply(msg_text)

                        if ai_reply:
                            logger.info(f"💡 Got AI reply: {ai_reply}")

                            # 发送回复
                            logger.info("📤 Finding input box...")
                            input_box = page.query_selector('div[contenteditable="true"]')

                            if input_box:
                                logger.info("✅ Input box found, sending reply...")
                                # 滚动到输入框位置
                                input_box.scroll_into_view_if_needed()
                                time.sleep(0.5)
                                # 使用JavaScript强制聚焦
                                page.evaluate('document.querySelector(\'div[contenteditable="true"]\').focus()')
                                time.sleep(0.3)
                                # 使用type instead of fill for contenteditable
                                page.keyboard.type(ai_reply)
                                time.sleep(0.5)
                                page.keyboard.press('Enter')
                                time.sleep(1)

                                logger.info("✅ REPLY SENT!")
                                logger.info(f"{'='*60}\n")

                                # 记录已处理
                                self.processed_messages.add(msg_text)
                                self.own_sent_messages.add(ai_reply)  # Track the message we just sent
                                self.last_message_text = msg_text

                                # 限制内存
                                if len(self.processed_messages) > 50:
                                    self.processed_messages.clear()
                                if len(self.own_sent_messages) > 50:
                                    self.own_sent_messages.clear()
                            else:
                                logger.error("❌ Input box not found!")
                                # 打印页面HTML用于调试
                                logger.info("📄 Page HTML sample:")
                                logger.info(page.content()[:500])
                        else:
                            logger.error("❌ Failed to get AI reply from backend")
                    else:
                        logger.info("   ℹ️  No messages found yet")

                    time.sleep(3)  # 每3秒检查一次

                except KeyboardInterrupt:
                    logger.info("\n⏹️  Stopping...")
                    break
                except Exception as e:
                    logger.error(f"❌ Error: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    time.sleep(3)

            browser.close()


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════╗
║   Messenger Auto-Reply Bot - DEBUG VERSION         ║
║                                                      ║
║   ✅ 详细日志输出                                    ║
║   ✅ 测试模式：回复所有消息（包括自己的）            ║
║   ✅ 实时显示检测到的消息                            ║
║                                                      ║
║   确保 Flask 后端运行在 http://localhost:5001       ║
╚══════════════════════════════════════════════════════╝
    """)

    # 可以指定对话URL
    conversation_url = input("输入Messenger对话URL (直接回车监听所有对话): ").strip()

    if not conversation_url:
        conversation_url = None

    # 测试模式关闭，只回复别人的消息
    bot = MessengerAutoReplyDebug(test_mode=False)
    bot.run(conversation_url)
