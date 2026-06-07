"""
闲鱼平台适配器
=========
对接闲鱼开放平台 API，实现消息收发、商品管理、订单操作。

注意：当前为适配器骨架，对接真实 API 需填入闲鱼开放平台的 AppKey/AppSecret。
"""

import hashlib
import hmac
import json
import logging
import time
from typing import Optional
from urllib.parse import urlencode

import aiohttp

from src.core.message import Message, MessageRole, MessageType, ProductInfo

from .adapter import PlatformAdapter, PlatformEvent

logger = logging.getLogger(__name__)

# 闲鱼开放平台 API 端点（沙箱环境）
XIANYU_API_BASE = "https://open-api.idlefish.com"  # 生产环境请使用正式域名
XIANYU_SESSION_ENDPOINT = f"{XIANYU_API_BASE}/rest/api/msg/send"
XIANYU_PRODUCT_ENDPOINT = f"{XIANYU_API_BASE}/rest/api/item/query"
XIANYU_PRICE_ENDPOINT = f"{XIANYU_API_BASE}/rest/api/item/update/price"
XIANYU_ORDER_ENDPOINT = f"{XIANYU_API_BASE}/rest/api/order/detail"


class XianyuAdapter(PlatformAdapter):
    """
    闲鱼平台适配器

    对接闲鱼开放平台 REST API，需要：
    - app_key: 应用 key
    - app_secret: 应用密钥
    - seller_id: 卖家用户 ID
    """

    def __init__(
        self,
        app_key: str = "",
        app_secret: str = "",
        seller_id: str = "",
        session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(platform_name="xianyu")
        self._app_key = app_key
        self._app_secret = app_secret
        self._seller_id = seller_id
        self._session = session

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _sign_request(self, params: dict) -> str:
        """闲鱼 API 签名"""
        sorted_items = sorted(params.items())
        query_string = urlencode(sorted_items)
        sign_string = f"{query_string}&app_secret={self._app_secret}"
        return hashlib.md5(sign_string.encode()).hexdigest().upper()

    async def fetch_new_messages(self) -> list[PlatformEvent]:
        """
        获取新消息。

        实际对接时调用闲鱼的消息拉取 API。
        """
        # 模拟返回一条新消息用于测试
        logger.debug("XianyuAdapter.fetch_new_messages called")
        return []

    async def send_reply(self, session_id: str, message: Message) -> bool:
        """
        发送回复到闲鱼。

        实际对接时调用闲鱼消息发送 API。
        """
        if not self._app_key or not self._app_secret:
            logger.warning(
                "Xianyu API credentials not configured. "
                "Message would be sent: [%s] %s",
                message.role.value,
                message.content[:50],
            )
            return True

        session = await self._get_session()
        params = {
            "app_key": self._app_key,
            "session_id": session_id,
            "content": message.content,
            "msg_type": message.msg_type.value,
            "timestamp": int(time.time()),
        }
        params["sign"] = self._sign_request(params)

        try:
            async with session.post(
                XIANYU_SESSION_ENDPOINT, data=params, timeout=10
            ) as resp:
                result = await resp.json()
                if result.get("success"):
                    logger.info(
                        "Message sent to Xianyu session %s", session_id
                    )
                    return True
                logger.error(
                    "Failed to send Xianyu message: %s", result
                )
                return False
        except Exception as e:
            logger.error("Xianyu API error: %s", e)
            return False

    async def mark_read(self, session_id: str) -> None:
        """标记会话已读"""
        logger.debug("Mark session %s as read", session_id)

    async def get_product_info(self, product_id: str) -> Optional[ProductInfo]:
        """
        获取商品信息。

        实际对接时调用闲鱼商品查询 API。
        """
        if not product_id:
            return None

        if not self._app_key or not self._app_secret:
            logger.warning(
                "Xianyu API credentials not configured. "
                "Returning stub for product %s",
                product_id,
            )
            return ProductInfo(
                product_id=product_id,
                title="示例商品（请配置闲鱼 API）",
                price=100.0,
                condition="九成新",
            )

        session = await self._get_session()
        params = {
            "app_key": self._app_key,
            "item_id": product_id,
            "timestamp": int(time.time()),
        }
        params["sign"] = self._sign_request(params)

        try:
            async with session.get(
                XIANYU_PRODUCT_ENDPOINT, params=params, timeout=10
            ) as resp:
                data = await resp.json()
                if data.get("success"):
                    item = data.get("data", {})
                    return ProductInfo(
                        product_id=product_id,
                        title=item.get("title", ""),
                        price=float(item.get("price", 0)),
                        original_price=(
                            float(item["origin_price"])
                            if item.get("origin_price")
                            else None
                        ),
                        description=item.get("description", ""),
                        condition=item.get("condition", ""),
                        images=item.get("images", []),
                        tags=item.get("tags", []),
                    )
                return None
        except Exception as e:
            logger.error("Failed to get product info: %s", e)
            return None

    async def update_price(self, product_id: str, price: float) -> bool:
        """
        修改商品价格（议价成功后调用）。

        实际对接时调用闲鱼改价 API。
        """
        if not self._app_key or not self._app_secret:
            logger.warning(
                "Xianyu API not configured. "
                "Would update price: %s -> %.2f",
                product_id,
                price,
            )
            return True

        session = await self._get_session()
        params = {
            "app_key": self._app_key,
            "item_id": product_id,
            "price": str(price),
            "timestamp": int(time.time()),
        }
        params["sign"] = self._sign_request(params)

        try:
            async with session.post(
                XIANYU_PRICE_ENDPOINT, data=params, timeout=10
            ) as resp:
                result = await resp.json()
                success = result.get("success", False)
                if success:
                    logger.info(
                        "Price updated for %s -> %.2f", product_id, price
                    )
                else:
                    logger.error("Price update failed: %s", result)
                return success
        except Exception as e:
            logger.error("Price update error: %s", e)
            return False

    async def health_check(self) -> bool:
        """检查 API 连通性"""
        return bool(self._app_key)  # 有凭证即认为可用（实际应发心跳）

    async def close(self) -> None:
        """关闭 HTTP 会话"""
        if self._session and not self._session.closed:
            await self._session.close()
