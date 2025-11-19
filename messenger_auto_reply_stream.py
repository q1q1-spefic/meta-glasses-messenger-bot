"""
Messenger自动回复 - 流式生成版本 + 图片识别解题
- 支持OpenAI streaming
- 实时发送：第一个词立即发送，然后逐步发送
- 自动语言检测：中文用中文答，英文用英文答
- 图片识别：使用GPT-4o Vision自动解题
"""

import json
import time
import logging
import re
import base64
import requests
from playwright.sync_api import sync_playwright
from openai import OpenAI
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)


def detect_language(text: str) -> str:
    """检测文本语言"""
    # 检测中文字符
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    # 检测英文字母
    english_chars = re.findall(r'[a-zA-Z]', text)

    chinese_count = len(chinese_chars)
    english_count = len(english_chars)

    if chinese_count > english_count:
        return 'chinese'
    elif english_count > 0:
        return 'english'
    else:
        return 'chinese'  # 默认中文


class MessengerAutoReplyStream:
    """流式生成的Messenger自动回复"""

    def __init__(self, test_mode=False):
        self.backend_url = "http://localhost:5001"
        self.last_message_text = None
        self.processed_messages = set()
        self.own_sent_messages = set()
        self.test_mode = test_mode
        self.message_count = 0

        # 初始化OpenAI客户端
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.vision_model = 'gpt-4o'  # 使用gpt-4o进行图片识别

        # 创建图片存储目录
        self.image_dir = Path("downloaded_images")
        self.image_dir.mkdir(exist_ok=True)

        # 加载cookies
        try:
            with open("messenger_auth.json", 'r') as f:
                config = json.load(f)
            self.cookies = config.get('facebook', {}).get('cookies', {})
            logger.info(f"✅ Loaded {len(self.cookies)} cookies")
        except:
            self.cookies = {}
            logger.warning("⚠️  No cookies found")

    def get_ai_reply_stream(self, message: str):
        """使用OpenAI streaming API生成回复"""
        try:
            # 检测语言
            language = detect_language(message)
            logger.info(f"🌐 Detected language: {language}")

            # 构建system prompt
            if language == 'chinese':
                system_prompt = """你是一个友好的对话助手。请用中文简洁、自然地回复。
要求：
- 1-2句话，简洁明了
- 语气自然、不做作
- 根据对方的话题继续对话
- 全部用中文回复"""
            else:
                system_prompt = """You are a friendly conversation assistant. Reply concisely and naturally in English.
Requirements:
- 1-2 sentences, clear and concise
- Natural tone, not artificial
- Continue the conversation based on their topic
- Reply entirely in English"""

            # 调用OpenAI streaming API
            stream = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"对方说：{message}\n\n请简洁回复："}
                ],
                temperature=0.7,
                max_tokens=150,
                stream=True  # 启用流式生成
            )

            return stream

        except Exception as e:
            logger.error(f"❌ OpenAI API error: {e}")
            return None

    def encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为base64"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def solve_image_problem(self, image_path: str, text_context: str = "") -> str:
        """使用GPT-4 Vision识别图片并解题"""
        try:
            logger.info(f"🖼️  Analyzing image: {image_path}")

            # 读取图片并转换为base64
            base64_image = self.encode_image_to_base64(image_path)

            # 默认使用英文，简洁回答
            prompt = """Analyze the problem in this image and provide the answer.

Rules:
1. For multiple choice or true/false questions: ONLY give the answer (e.g., "A", "True", "42")
2. For calculation/proof problems: Show brief steps + final answer
3. Be concise - no explanations unless necessary
4. Reply in ENGLISH by default
5. IMPORTANT: Use plain text for math - avoid LaTeX symbols like \\int, \\sqrt, etc.
   Instead use: integral, sqrt(), ^2, /, etc.

Format:
- Multiple choice: "Answer: A"
- True/False: "Answer: True"
- Calculation: "Steps: integral(x^2) from 0 to 1 = [x^3/3] = 1/3
Answer: 1/3"
"""

            # 如果有文本上下文，添加到提示中
            if text_context:
                prompt = f"Context: {text_context}\n\n{prompt}"

            # 调用GPT-4 Vision API
            response = self.openai_client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"  # 使用高质量分析
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.3  # 较低温度以获得更准确的答案
            )

            solution = response.choices[0].message.content
            logger.info(f"✅ Solution generated: {solution[:100]}...")
            return solution

        except Exception as e:
            logger.error(f"❌ Vision API error: {e}")
            return None

    def download_image(self, page, img_element) -> str:
        """下载图片到本地并返回路径"""
        try:
            # 获取图片URL
            img_url = img_element.get_attribute('src')

            if not img_url:
                logger.error("❌ No image URL found")
                return None

            # 如果是data URL,直接保存
            if img_url.startswith('data:image'):
                # 解析data URL
                header, encoded = img_url.split(',', 1)
                img_data = base64.b64decode(encoded)

                # 保存图片
                timestamp = int(time.time() * 1000)
                image_path = self.image_dir / f"image_{timestamp}.jpg"
                with open(image_path, 'wb') as f:
                    f.write(img_data)

                logger.info(f"✅ Image saved from data URL: {image_path}")
                return str(image_path)

            # 否则通过HTTP下载
            logger.info(f"📥 Downloading image from: {img_url[:100]}")

            # 使用cookies下载
            cookies_dict = self.cookies
            response = requests.get(img_url, cookies=cookies_dict, timeout=10)

            if response.status_code == 200:
                # 保存图片
                timestamp = int(time.time() * 1000)
                image_path = self.image_dir / f"image_{timestamp}.jpg"
                with open(image_path, 'wb') as f:
                    f.write(response.content)

                logger.info(f"✅ Image downloaded: {image_path}")
                return str(image_path)
            else:
                logger.error(f"❌ Failed to download image: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"❌ Download error: {e}")
            return None

    def send_text_gradually(self, page, text: str):
        """
        逐步发送文本到输入框
        - 按词或短语分段
        - 每发送一段就按Enter发送
        - 返回所有发送的段落列表
        """
        # 找到输入框
        input_box = page.query_selector('div[contenteditable="true"]')
        if not input_box:
            logger.error("❌ Input box not found")
            return None

        # 滚动到输入框
        input_box.scroll_into_view_if_needed()
        time.sleep(0.3)

        # 使用JavaScript聚焦
        page.evaluate('document.querySelector(\'div[contenteditable="true"]\').focus()')
        time.sleep(0.2)

        # 分段逻辑：
        # 中文：按标点或每3-5个字分段
        # 英文：按单词分段

        language = detect_language(text)

        if language == 'chinese':
            # 中文：按标点符号或固定长度分段
            segments = []
            current_segment = ""

            for char in text:
                current_segment += char
                # 遇到标点或达到5个字就分段
                if char in '，。！？、' or len(current_segment) >= 5:
                    segments.append(current_segment)
                    current_segment = ""

            if current_segment:  # 添加剩余部分
                segments.append(current_segment)

        else:
            # 英文：按单词分段，每2-3个单词一组
            words = text.split()
            segments = []
            current_segment = []

            for i, word in enumerate(words):
                current_segment.append(word)
                # 每3个单词或遇到句号就发送
                if len(current_segment) >= 3 or word.endswith('.') or word.endswith(','):
                    segments.append(' '.join(current_segment))
                    current_segment = []

            if current_segment:
                segments.append(' '.join(current_segment))

        logger.info(f"📤 Sending in {len(segments)} segments...")

        # 逐段发送
        for i, segment in enumerate(segments):
            logger.info(f"   Segment {i+1}/{len(segments)}: {segment}")

            # 清空输入框
            page.evaluate('document.querySelector(\'div[contenteditable="true"]\').innerText = ""')
            time.sleep(0.1)

            # 输入当前段
            page.keyboard.type(segment)
            time.sleep(0.2)

            # 按Enter发送
            page.keyboard.press('Enter')
            time.sleep(0.5)  # 等待消息发送

        logger.info("✅ All segments sent!")
        return segments  # 返回所有段落

    def run(self, conversation_url: str = None):
        """运行自动回复机器人"""

        logger.info(f"🔧 Stream mode: ENABLED")
        logger.info(f"🔧 Test mode: {'ENABLED' if self.test_mode else 'DISABLED'}")

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

                    # 获取所有消息气泡和图片
                    messages = page.query_selector_all('div[dir="auto"]')
                    all_images = page.query_selector_all('img[src]')  # 查找所有图片
                    logger.info(f"   Found {len(messages)} div[dir=\"auto\"] elements, {len(all_images)} images")

                    # 优先检查是否有新图片（过滤掉小图片如头像、emoji等）
                    has_new_image = False
                    latest_image = None
                    if len(all_images) > 0:
                        # 反向遍历图片，找到第一个满足条件的大图片
                        for img in reversed(all_images):
                            try:
                                # 获取图片尺寸
                                bounding_box = img.bounding_box()
                                if bounding_box:
                                    width = bounding_box['width']
                                    height = bounding_box['height']

                                    # 过滤掉小图片（头像、表情、图标）
                                    # 消息图片通常宽度>100px
                                    if width > 100 and height > 100:
                                        img_src = img.get_attribute('src')
                                        if img_src:
                                            # 进一步过滤：排除头像URL (t39.30808-1, t39.30808-6 通常是头像)
                                            if 't39.30808-1' not in img_src and 't39.30808-6' not in img_src:
                                                img_id = f"[IMG]{img_src[:100]}"
                                                # 检查这张图片是否已处理
                                                if img_id not in self.processed_messages:
                                                    has_new_image = True
                                                    latest_image = img
                                                    logger.info(f"   🖼️  Found NEW large image ({int(width)}x{int(height)}): {img_src[:80]}...")
                                                    break  # 找到第一个就停止
                            except Exception as e:
                                continue

                    if has_new_image and latest_image:
                        # 处理新图片
                        img_src = latest_image.get_attribute('src')
                        message_id = f"[IMG]{img_src[:100]}"
                        msg_text = ""  # 图片消息可能没有文本

                        # 标记为已处理
                        self.processed_messages.add(message_id)
                        self.last_message_text = message_id

                        self.message_count += 1
                        logger.info(f"\n{'='*60}")
                        logger.info(f"📩 NEW MESSAGE #{self.message_count}: [Image]")
                        logger.info(f"🖼️  Image detected! Processing with Vision API...")
                        logger.info(f"{'='*60}")

                        # 下载图片
                        try:
                            image_path = self.download_image(page, latest_image)
                            if image_path:
                                logger.info(f"✅ Image downloaded: {image_path}")

                                # 使用Vision API解析图片
                                solution = self.solve_image_problem(image_path, msg_text)

                                if solution:
                                    logger.info(f"💡 Vision API solution generated")
                                    full_response = solution

                                    # 直接发送解答
                                    sent_segments = self.send_text_gradually(page, full_response)

                                    if sent_segments:
                                        logger.info(f"{'='*60}\n")
                                        self.own_sent_messages.add(full_response)
                                        for segment in sent_segments:
                                            self.own_sent_messages.add(segment.strip())
                                        logger.info(f"📝 Tracked {len(sent_segments)} segments to prevent self-reply")
                                    else:
                                        logger.error("❌ Failed to send image solution")
                                else:
                                    logger.error("❌ Failed to get solution from Vision API")
                            else:
                                logger.error("❌ Failed to download image")
                        except Exception as e:
                            logger.error(f"❌ Error processing image: {e}")
                            import traceback
                            logger.error(traceback.format_exc())

                        # 限制内存
                        if len(self.processed_messages) > 50:
                            self.processed_messages.clear()
                        if len(self.own_sent_messages) > 100:
                            self.own_sent_messages = set(list(self.own_sent_messages)[-50:])

                        time.sleep(3)
                        continue

                    if len(messages) > 0:
                        # 显示最后几条消息
                        if check_count % 5 == 1:  # 每5次检查显示一次
                            logger.info(f"   Last 3 messages:")
                            for i, msg in enumerate(messages[-3:]):
                                text = msg.inner_text().strip()[:50]
                                logger.info(f"      [{i}] {text}...")

                        # 获取最后一条消息
                        last_msg_elem = messages[-1]
                        msg_text = last_msg_elem.inner_text().strip()

                        logger.info(f"   📝 Last message: '{msg_text[:100]}'")

                        # 检查是否包含图片（即使文本为空也要处理）
                        img_element = last_msg_elem.query_selector('img')
                        has_image = img_element is not None

                        # 过滤掉无效消息（但如果有图片，即使文本为空也处理）
                        if not msg_text and not has_image:
                            logger.info("   ⏭️  Skipped: Empty message without image")
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

                        # 为图片消息创建唯一标识（使用图片URL或时间戳）
                        message_id = msg_text
                        if has_image and img_element:
                            img_src = img_element.get_attribute('src')
                            if img_src:
                                message_id = f"[IMG]{img_src[:100]}"  # 使用图片URL作为ID

                        # 检查是否已处理
                        if message_id in self.processed_messages:
                            logger.info(f"   ⏭️  Skipped: Already processed")
                            time.sleep(3)
                            continue

                        # 检查是否是新消息
                        if message_id == self.last_message_text:
                            logger.info(f"   ⏭️  Skipped: Same as last message")
                            time.sleep(3)
                            continue

                        # 检查是否是自己发送的消息
                        if not self.test_mode:
                            if msg_text in self.own_sent_messages:
                                logger.info(f"   ⏭️  Skipped: Own message (sent by bot)")
                                self.last_message_text = msg_text
                                self.processed_messages.add(msg_text)
                                time.sleep(3)
                                continue

                        # 新消息！开始处理
                        self.message_count += 1
                        logger.info(f"\n{'='*60}")
                        logger.info(f"📩 NEW MESSAGE #{self.message_count}: {msg_text if msg_text else '[Image]'}")
                        logger.info(f"{'='*60}")

                        if has_image:
                            logger.info("🖼️  Image detected! Processing with Vision API...")

                            # 下载图片
                            image_path = self.download_image(page, img_element)

                            if image_path:
                                # 使用Vision API解题
                                solution = self.solve_image_problem(image_path, msg_text)

                                if solution:
                                    full_response = solution
                                else:
                                    full_response = "抱歉，无法识别图片内容。请尝试上传更清晰的图片。" if detect_language(msg_text) == 'chinese' else "Sorry, couldn't analyze the image. Please try uploading a clearer image."
                            else:
                                full_response = "抱歉，无法下载图片。请重新发送。" if detect_language(msg_text) == 'chinese' else "Sorry, couldn't download the image. Please resend it."

                            # 直接发送解答，不使用stream
                            sent_segments = self.send_text_gradually(page, full_response)

                            if sent_segments:
                                logger.info(f"{'='*60}\n")

                                # 记录已处理
                                self.processed_messages.add(message_id)
                                self.last_message_text = message_id
                                self.own_sent_messages.add(full_response)
                                for segment in sent_segments:
                                    self.own_sent_messages.add(segment.strip())

                                logger.info(f"📝 Tracked {len(sent_segments)} segments to prevent self-reply")

                                # 限制内存
                                if len(self.processed_messages) > 50:
                                    self.processed_messages.clear()
                                if len(self.own_sent_messages) > 100:
                                    self.own_sent_messages = set(list(self.own_sent_messages)[-50:])
                            else:
                                logger.error("❌ Failed to send reply")

                            # 跳过后续文本处理
                            time.sleep(3)
                            continue

                        # 使用流式生成获取AI回复（纯文本消息）
                        logger.info("🤖 Streaming AI response...")
                        stream = self.get_ai_reply_stream(msg_text)

                        if stream:
                            # 收集流式响应
                            full_response = ""
                            chunks = []

                            for chunk in stream:
                                if chunk.choices[0].delta.content:
                                    content = chunk.choices[0].delta.content
                                    full_response += content
                                    chunks.append(content)
                                    print(content, end='', flush=True)  # 实时显示

                            print()  # 换行
                            logger.info(f"💡 Full AI reply: {full_response}")

                            if full_response:
                                # 使用分段发送
                                sent_segments = self.send_text_gradually(page, full_response)

                                if sent_segments:
                                    logger.info(f"{'='*60}\n")

                                    # 记录已处理的原始消息
                                    self.processed_messages.add(message_id)
                                    self.last_message_text = message_id

                                    # 记录完整回复和所有分段，防止回复自己的消息
                                    self.own_sent_messages.add(full_response)
                                    for segment in sent_segments:
                                        self.own_sent_messages.add(segment.strip())

                                    logger.info(f"📝 Tracked {len(sent_segments)} segments to prevent self-reply")

                                    # 限制内存
                                    if len(self.processed_messages) > 50:
                                        self.processed_messages.clear()
                                    if len(self.own_sent_messages) > 100:
                                        # 清理一半，保留最新的
                                        self.own_sent_messages = set(list(self.own_sent_messages)[-50:])
                                else:
                                    logger.error("❌ Failed to send reply")
                        else:
                            logger.error("❌ Failed to get AI reply")
                    else:
                        if check_count == 1:
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
║   Messenger Auto-Reply - STREAMING VERSION         ║
║                                                      ║
║   ✅ OpenAI Streaming - 第一个词立即发送            ║
║   ✅ 语言检测 - 中文用中文答，英文用英文答          ║
║   ✅ 分段发送 - 逐步发送完整回复                    ║
║                                                      ║
║   需要设置环境变量：OPENAI_API_KEY                  ║
╚══════════════════════════════════════════════════════╝
    """)

    # 可以指定对话URL
    conversation_url = input("输入Messenger对话URL (直接回车监听所有对话): ").strip()

    if not conversation_url:
        conversation_url = None

    # 启动流式版本
    bot = MessengerAutoReplyStream(test_mode=False)
    bot.run(conversation_url)
