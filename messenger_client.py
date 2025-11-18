"""
Messenger Graph API 客户端
基于Instagram项目的实现，用于Messenger自动回复
"""
import logging
import aiohttp
import hmac
import hashlib
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MessengerMessage:
    """Messenger 消息"""
    sender_id: str
    recipient_id: str
    message_id: str
    text: Optional[str] = None
    attachments: Optional[List[Dict]] = None
    timestamp: Optional[int] = None

@dataclass
class MessengerUser:
    """Messenger 用户信息"""
    id: str
    name: Optional[str] = None

class MessengerClient:
    """
    Messenger Graph API 客户端
    用于接收和发送 Messenger 消息
    """

    def __init__(self, page_access_token: str, app_secret: str, verify_token: str):
        """
        初始化Messenger客户端

        Args:
            page_access_token: Facebook Page Access Token
            app_secret: Facebook App Secret
            verify_token: Webhook验证令牌
        """
        self.access_token = page_access_token
        self.app_secret = app_secret
        self.verify_token = verify_token
        self.base_url = "https://graph.facebook.com/v21.0"

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        验证 webhook 签名

        Args:
            payload: 请求体
            signature: X-Hub-Signature-256 header

        Returns:
            签名是否有效
        """
        try:
            # 计算预期签名
            expected_signature = hmac.new(
                self.app_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()

            # 签名格式: sha256=<signature>
            if signature.startswith('sha256='):
                signature = signature[7:]

            return hmac.compare_digest(expected_signature, signature)

        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False

    async def send_message(
        self,
        recipient_id: str,
        text: Optional[str] = None,
        attachment_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送消息给用户

        Args:
            recipient_id: 接收者 Messenger ID (PSID)
            text: 文本消息
            attachment_url: 附件 URL（图片、视频等）

        Returns:
            API 响应
        """
        url = f"{self.base_url}/me/messages"

        payload = {
            "recipient": {"id": recipient_id},
            "message": {}
        }

        if text:
            payload["message"]["text"] = text

        if attachment_url:
            payload["message"]["attachment"] = {
                "type": "image",
                "payload": {
                    "url": attachment_url,
                    "is_reusable": True
                }
            }

        params = {"access_token": self.access_token}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    result = await response.json()

                    if response.status == 200:
                        logger.info(f"Message sent successfully to {recipient_id}")
                        return {"success": True, "data": result}
                    else:
                        logger.error(f"Failed to send message: {result}")
                        return {"success": False, "error": result}

        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def send_text_message(self, recipient_id: str, text: str) -> Dict[str, Any]:
        """
        发送文本消息

        Args:
            recipient_id: 接收者 ID (PSID)
            text: 文本内容

        Returns:
            API 响应
        """
        return await self.send_message(recipient_id=recipient_id, text=text)

    async def send_typing_indicator(self, recipient_id: str, action: str = "typing_on") -> Dict[str, Any]:
        """
        发送"正在输入"指示器

        Args:
            recipient_id: 接收者 ID (PSID)
            action: "typing_on" 或 "typing_off" 或 "mark_seen"

        Returns:
            API 响应
        """
        url = f"{self.base_url}/me/messages"

        payload = {
            "recipient": {"id": recipient_id},
            "sender_action": action
        }

        params = {"access_token": self.access_token}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    result = await response.json()

                    if response.status == 200:
                        return {"success": True}
                    else:
                        logger.error(f"Failed to send typing indicator: {result}")
                        return {"success": False, "error": result}

        except Exception as e:
            logger.error(f"Error sending typing indicator: {e}")
            return {"success": False, "error": str(e)}

    async def get_user_info(self, user_id: str) -> Optional[MessengerUser]:
        """
        获取用户信息

        Args:
            user_id: 用户 ID (PSID)

        Returns:
            MessengerUser 对象或 None
        """
        url = f"{self.base_url}/{user_id}"
        params = {
            "fields": "name,first_name,last_name,profile_pic",
            "access_token": self.access_token
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return MessengerUser(
                            id=user_id,
                            name=data.get("name")
                        )
                    else:
                        logger.error(f"Failed to get user info: {await response.text()}")
                        return None

        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None

    def parse_webhook_event(self, data: Dict) -> Optional[MessengerMessage]:
        """
        解析webhook事件数据

        Args:
            data: Webhook payload

        Returns:
            MessengerMessage 对象或 None
        """
        try:
            # Messenger webhook结构
            if data.get("object") != "page":
                return None

            entries = data.get("entry", [])
            if not entries:
                return None

            entry = entries[0]
            messaging_events = entry.get("messaging", [])

            if not messaging_events:
                return None

            event = messaging_events[0]

            # 提取消息
            message_data = event.get("message")
            if not message_data:
                return None

            sender = event.get("sender", {})
            recipient = event.get("recipient", {})

            return MessengerMessage(
                sender_id=sender.get("id"),
                recipient_id=recipient.get("id"),
                message_id=message_data.get("mid"),
                text=message_data.get("text"),
                attachments=message_data.get("attachments"),
                timestamp=event.get("timestamp")
            )

        except Exception as e:
            logger.error(f"Error parsing webhook event: {e}", exc_info=True)
            return None
