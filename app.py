#!/usr/bin/env python3
"""
Meta Glasses 实时对话助手后端服务器
提供AI驱动的对话建议生成API
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
from messenger_client import MessengerClient

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 初始化Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
CORS(app)  # 允许跨域请求

# 初始化OpenAI客户端
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# 初始化Messenger客户端（可选，如果设置了相关环境变量）
messenger_client = None
if os.getenv('MESSENGER_PAGE_ACCESS_TOKEN'):
    messenger_client = MessengerClient(
        page_access_token=os.getenv('MESSENGER_PAGE_ACCESS_TOKEN'),
        app_secret=os.getenv('MESSENGER_APP_SECRET', ''),
        verify_token=os.getenv('MESSENGER_VERIFY_TOKEN', 'meta-glasses-verify-token')
    )
    logger.info("Messenger client initialized")

# 对话历史存储（生产环境应使用数据库）
conversation_history = []


class ConversationAssistant:
    """对话助手核心类"""

    def __init__(self):
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.max_history = 10  # 保留最近10轮对话

    def generate_suggestion(self, user_message: str, context: dict = None) -> dict:
        """
        生成对话建议

        Args:
            user_message: 对方说的话或问题
            context: 额外上下文信息（可选）
                - scenario: 场景类型（interview, social, business）
                - user_background: 用户背景信息
                - conversation_goal: 对话目标

        Returns:
            {
                'suggestion': str,  # AI建议的回答
                'analysis': str,    # 对问题的分析
                'tips': list,       # 回答技巧
                'confidence': float # 建议可信度
            }
        """
        try:
            logger.info(f"Received message: {user_message}")

            # 构建系统提示词
            system_prompt = self._build_system_prompt(context)

            # 构建对话历史
            messages = [{"role": "system", "content": system_prompt}]

            # 添加最近的对话历史
            if conversation_history:
                recent_history = conversation_history[-self.max_history:]
                messages.extend(recent_history)

            # 添加当前问题
            messages.append({
                "role": "user",
                "content": f"对方说：「{user_message}」\n\n请提供简洁、自然的回答建议。"
            })

            # 调用OpenAI API
            response = openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=500,
                response_format={"type": "json_object"}
            )

            # 解析响应
            result = json.loads(response.choices[0].message.content)

            # 保存到历史
            conversation_history.append({
                "role": "user",
                "content": user_message
            })
            conversation_history.append({
                "role": "assistant",
                "content": result.get('suggestion', '')
            })

            logger.info(f"Generated suggestion: {result.get('suggestion', '')[:100]}")

            return {
                'suggestion': result.get('suggestion', ''),
                'analysis': result.get('analysis', ''),
                'tips': result.get('tips', []),
                'confidence': result.get('confidence', 0.8),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating suggestion: {e}")
            raise

    def _build_system_prompt(self, context: dict = None) -> str:
        """构建系统提示词"""

        scenario = context.get('scenario', 'general') if context else 'general'

        base_prompt = """你是一个专业的实时对话助手。你的任务是帮助用户在对话中给出合适的回答建议。

核心原则：
1. 回答要简洁、自然、不做作
2. 根据场景调整语气和风格
3. 提供1-3句话的建议，不要太长
4. 考虑文化和社交礼仪
5. 避免过于正式或学术化的表达

输出格式（JSON）：
{
    "suggestion": "建议的回答内容（1-3句话）",
    "analysis": "对问题的简短分析（1句话）",
    "tips": ["回答技巧1", "回答技巧2"],
    "confidence": 0.85
}
"""

        # 根据场景添加特定指导
        scenario_prompts = {
            'interview': """
场景：面试
- 突出个人优势和相关经验
- 使用STAR法则（情境-任务-行动-结果）
- 保持自信但不傲慢
- 提问时展现对公司的了解
""",
            'social': """
场景：社交场合
- 保持轻松友好的语气
- 展现真诚和兴趣
- 适当使用幽默
- 避免敏感话题
""",
            'business': """
场景：商务沟通
- 专业且高效
- 突出价值和成果
- 使用数据和事实
- 保持礼貌和尊重
""",
            'general': """
场景：日常对话
- 自然真诚
- 根据对方语气调整
- 保持友好开放
"""
        }

        prompt = base_prompt + scenario_prompts.get(scenario, scenario_prompts['general'])

        # 添加用户背景信息
        if context and context.get('user_background'):
            prompt += f"\n\n用户背景：{context['user_background']}"

        # 添加对话目标
        if context and context.get('conversation_goal'):
            prompt += f"\n对话目标：{context['conversation_goal']}"

        return prompt.strip()


# 初始化助手
assistant = ConversationAssistant()


@app.route('/', methods=['GET'])
def index():
    """健康检查端点"""
    return jsonify({
        'status': 'running',
        'service': 'Meta Glasses Conversation Assistant',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/conversation-suggest', methods=['POST'])
def conversation_suggest():
    """
    对话建议生成端点

    请求格式：
    {
        "message": "对方说的话",
        "context": {
            "scenario": "interview",
            "user_background": "5年Python开发经验",
            "conversation_goal": "获得offer"
        }
    }

    响应格式：
    {
        "success": true,
        "data": {
            "suggestion": "...",
            "analysis": "...",
            "tips": [...],
            "confidence": 0.85
        }
    }
    """
    try:
        # 获取请求数据
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': '无效的请求数据'
            }), 400

        message = data.get('message', '')

        if not message:
            return jsonify({
                'success': False,
                'error': '消息内容不能为空'
            }), 400

        # 获取上下文（可选）
        context = data.get('context', {})

        # 生成建议
        result = assistant.generate_suggestion(message, context)

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"Error in conversation_suggest endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/conversation-history', methods=['GET'])
def get_conversation_history():
    """获取对话历史"""
    return jsonify({
        'success': True,
        'data': conversation_history[-20:]  # 返回最近20条
    })


@app.route('/api/conversation-history', methods=['DELETE'])
def clear_conversation_history():
    """清空对话历史"""
    global conversation_history
    conversation_history = []
    return jsonify({
        'success': True,
        'message': '对话历史已清空'
    })


@app.route('/api/scenarios', methods=['GET'])
def get_scenarios():
    """获取支持的场景类型"""
    return jsonify({
        'success': True,
        'data': [
            {
                'id': 'interview',
                'name': '面试',
                'description': '求职面试场景，提供专业建议'
            },
            {
                'id': 'social',
                'name': '社交',
                'description': '社交场合，保持轻松友好'
            },
            {
                'id': 'business',
                'name': '商务',
                'description': '商务沟通，专业高效'
            },
            {
                'id': 'general',
                'name': '日常',
                'description': '日常对话，自然真诚'
            }
        ]
    })


@app.route('/api/test', methods=['POST'])
def test_endpoint():
    """测试端点 - 用于验证集成"""
    data = request.get_json()
    logger.info(f"Test endpoint received: {data}")

    return jsonify({
        'success': True,
        'message': 'Test successful',
        'echo': data,
        'timestamp': datetime.now().isoformat()
    })


# ==================== Messenger Webhook ====================

@app.route('/webhook', methods=['GET'])
def webhook_verify():
    """
    Messenger Webhook验证端点
    Facebook会发送GET请求来验证webhook
    """
    verify_token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    mode = request.args.get('hub.mode')

    expected_token = os.getenv('MESSENGER_VERIFY_TOKEN', 'meta-glasses-verify-token')

    if mode == 'subscribe' and verify_token == expected_token:
        logger.info("Webhook verified successfully")
        return challenge, 200
    else:
        logger.warning(f"Webhook verification failed. Token: {verify_token}")
        return 'Verification failed', 403


@app.route('/webhook', methods=['POST'])
def webhook_receive():
    """
    Messenger Webhook接收端点
    接收来自Messenger的消息事件
    """
    if not messenger_client:
        logger.error("Messenger client not initialized")
        return jsonify({'success': False, 'error': 'Messenger not configured'}), 500

    try:
        # 获取请求数据
        data = request.get_json()

        logger.info(f"Received webhook event: {json.dumps(data, indent=2)}")

        # 验证签名（生产环境必须）
        signature = request.headers.get('X-Hub-Signature-256', '')
        if signature and messenger_client.app_secret:
            if not messenger_client.verify_webhook_signature(request.data, signature):
                logger.warning("Invalid webhook signature")
                return jsonify({'success': False, 'error': 'Invalid signature'}), 403

        # 解析消息
        message = messenger_client.parse_webhook_event(data)

        if message and message.text:
            # 异步处理消息（不阻塞webhook响应）
            asyncio.run(process_messenger_message(message))

        # 立即返回200，告诉Facebook我们收到了
        return jsonify({'success': True}), 200

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


async def process_messenger_message(message):
    """
    异步处理Messenger消息并自动回复

    Args:
        message: MessengerMessage对象
    """
    try:
        logger.info(f"Processing message from {message.sender_id}: {message.text}")

        # 发送"正在输入"指示器
        await messenger_client.send_typing_indicator(message.sender_id, "typing_on")

        # 调用AI生成回复
        assistant = ConversationAssistant()
        result = assistant.generate_suggestion(message.text, context={'scenario': 'general'})

        # 发送AI回复
        suggestion = result.get('suggestion', '抱歉，我暂时无法回答。')
        await messenger_client.send_text_message(message.sender_id, suggestion)

        logger.info(f"Sent reply to {message.sender_id}: {suggestion}")

    except Exception as e:
        logger.error(f"Error processing Messenger message: {e}", exc_info=True)
        # 发送错误提示
        try:
            await messenger_client.send_text_message(
                message.sender_id,
                "抱歉，处理您的消息时出现问题。"
            )
        except:
            pass


if __name__ == '__main__':
    # 检查API密钥
    if not os.getenv('OPENAI_API_KEY'):
        logger.error("OPENAI_API_KEY not found in environment variables!")
        print("⚠️  请在 .env 文件中设置 OPENAI_API_KEY")
        exit(1)

    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    logger.info(f"Starting Conversation Assistant Backend on port {port}")
    logger.info(f"Debug mode: {debug}")

    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
