"""
Messenger自动回复 - 使用Playwright爬虫
参考MarketingMind AI的Instagram/Facebook DM实现
"""

import json
import time
import logging
import requests
from typing import Set
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MessengerAutoReplier:
    """Messenger自动回复机器人"""

    def __init__(self, auth_file: str = "messenger_auth.json", backend_url: str = "http://localhost:5001"):
        """
        初始化Messenger自动回复器

        Args:
            auth_file: 认证文件路径（包含Facebook cookies）
            backend_url: Flask后端地址
        """
        self.backend_url = backend_url
        self.processed_messages: Set[str] = set()  # 已处理的消息ID

        # 加载Facebook cookies
        try:
            with open(auth_file, 'r') as f:
                config = json.load(f)
            self.cookies = config.get('facebook', {}).get('cookies', {})
            logger.info("✅ Loaded Facebook cookies")
        except FileNotFoundError:
            logger.error(f"❌ Auth file {auth_file} not found")
            self.cookies = {}

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def _setup_browser(self):
        """设置Playwright浏览器"""
        if not self.playwright:
            logger.info("🌐 Setting up browser...")
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=False,  # 设为True可后台运行
                args=['--disable-blink-features=AutomationControlled']
            )
            self.context = self.browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                viewport={'width': 1920, 'height': 1080}
            )

            # 加载cookies - 同时添加到facebook.com和messenger.com
            if self.cookies:
                cookies_list = []
                for name, value in self.cookies.items():
                    # 添加到 .facebook.com
                    cookies_list.append({
                        'name': name,
                        'value': value,
                        'domain': '.facebook.com',
                        'path': '/'
                    })
                    # 添加到 .messenger.com
                    cookies_list.append({
                        'name': name,
                        'value': value,
                        'domain': '.messenger.com',
                        'path': '/'
                    })
                self.context.add_cookies(cookies_list)
                logger.info(f"✅ Loaded {len(self.cookies)} cookies to Facebook & Messenger")

            self.page = self.context.new_page()

    def _get_ai_reply(self, message: str) -> str:
        """
        调用Flask后端获取AI回复

        Args:
            message: 收到的消息

        Returns:
            AI生成的回复
        """
        try:
            response = requests.post(
                f"{self.backend_url}/api/conversation-suggest",
                json={
                    "message": message,
                    "context": {"scenario": "general"}
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data['data']['suggestion']

            logger.error(f"❌ Backend error: {response.status_code}")
            return "抱歉，暂时无法回复。"

        except Exception as e:
            logger.error(f"❌ Error calling backend: {e}")
            return "抱歉，暂时无法回复。"

    def _get_latest_message(self):
        """
        获取当前对话的最新消息

        Returns:
            (sender_name, message_text, message_id) 或 (None, None, None)
        """
        try:
            # Messenger消息的选择器
            message_selectors = [
                'div[role="row"] div[dir="auto"]',  # 消息文本
                'div[data-scope="messages_table"] div[dir="auto"]',
            ]

            # 获取所有消息元素
            messages = self.page.query_selector_all('div[role="row"]')

            if not messages:
                return None, None, None

            # 获取最后一条消息
            last_message = messages[-1]

            # 检查是否是对方发送的（不是自己发的）
            # Messenger中，对方的消息通常在左侧，自己的在右侧
            # 可以通过检查CSS class或者位置来判断
            message_text_elem = last_message.query_selector('div[dir="auto"]')

            if not message_text_elem:
                return None, None, None

            message_text = message_text_elem.inner_text().strip()

            # 生成消息ID（使用消息文本 + 时间戳的组合）
            message_id = f"{message_text[:50]}_{int(time.time() / 60)}"  # 按分钟粒度

            # 检查是否已处理过
            if message_id in self.processed_messages:
                return None, None, None

            # 简单判断：如果消息元素在左侧区域，说明是对方发的
            # 获取消息元素的bounding box来判断位置
            box = last_message.bounding_box()
            if box and box['x'] < 500:  # 左侧消息（阈值可调整）
                return "User", message_text, message_id

            return None, None, None

        except Exception as e:
            logger.error(f"❌ Error getting message: {e}")
            return None, None, None

    def _send_reply(self, reply_text: str) -> bool:
        """
        发送回复消息

        Args:
            reply_text: 回复内容

        Returns:
            是否成功
        """
        try:
            # 查找消息输入框
            input_selectors = [
                'div[contenteditable="true"][aria-label*="message"]',
                'div[contenteditable="true"][aria-label*="消息"]',
                'div[contenteditable="true"][role="textbox"]',
                'div[contenteditable="true"]',
            ]

            message_input = None
            for selector in input_selectors:
                try:
                    message_input = self.page.wait_for_selector(selector, timeout=2000)
                    if message_input and message_input.is_visible():
                        break
                except:
                    continue

            if not message_input:
                logger.error("❌ Message input not found")
                return False

            # 输入回复
            message_input.click()
            time.sleep(0.3)
            message_input.fill(reply_text)
            time.sleep(0.5)

            # 发送（按Enter键）
            message_input.press('Enter')
            time.sleep(1)

            logger.info(f"✅ Sent reply: {reply_text[:50]}...")
            return True

        except Exception as e:
            logger.error(f"❌ Error sending reply: {e}")
            return False

    def start_monitoring(self, conversation_url: str = "https://www.messenger.com/"):
        """
        开始监听Messenger消息并自动回复

        Args:
            conversation_url: Messenger对话链接（可以是特定对话或主页）
        """
        try:
            self._setup_browser()

            logger.info(f"🚀 Starting Messenger auto-reply bot...")
            logger.info(f"📱 Opening: {conversation_url}")

            self.page.goto(conversation_url, wait_until='domcontentloaded', timeout=60000)
            time.sleep(5)

            # 检查是否需要登录
            if "login" in self.page.url:
                logger.error("❌ Not logged in to Facebook. Please login first.")
                logger.info("💡 Run: python messenger_login.py to save cookies")
                return

            logger.info("✅ Logged in to Messenger")
            logger.info("🎯 Monitoring for new messages...")
            logger.info("💬 Send a message to test auto-reply!")

            # 主循环：监听新消息
            while True:
                try:
                    sender, message, message_id = self._get_latest_message()

                    if message and message_id:
                        logger.info(f"\n📩 New message received: {message}")

                        # 获取AI回复
                        logger.info("🤖 Generating AI reply...")
                        ai_reply = self._get_ai_reply(message)

                        # 发送回复
                        if self._send_reply(ai_reply):
                            # 标记为已处理
                            self.processed_messages.add(message_id)
                            logger.info("✅ Auto-reply sent successfully\n")
                        else:
                            logger.error("❌ Failed to send reply\n")

                    # 等待一段时间再检查（避免过于频繁）
                    time.sleep(2)

                except KeyboardInterrupt:
                    logger.info("\n⏹️  Stopping bot...")
                    break
                except Exception as e:
                    logger.error(f"❌ Error in monitoring loop: {e}")
                    time.sleep(5)

        except Exception as e:
            logger.error(f"❌ Error starting monitor: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """清理资源"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        logger.info("👋 Browser closed")


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════╗
    ║   Messenger Auto-Reply Bot for Meta Glasses        ║
    ║                                                      ║
    ║   1. 确保Flask后端运行在 http://localhost:5001      ║
    ║   2. 使用 messenger_login.py 保存Facebook cookies   ║
    ║   3. 运行此脚本开始自动回复                          ║
    ╚══════════════════════════════════════════════════════╝
    """)

    bot = MessengerAutoReplier()

    # 可以指定具体对话链接，或使用主页
    # conversation_url = "https://www.messenger.com/t/100000000000000"
    conversation_url = "https://www.messenger.com/"

    bot.start_monitoring(conversation_url)
