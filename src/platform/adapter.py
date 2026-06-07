"""
平台适配器抽象层
=========
提供统一的平台接口，使得核心引擎可以对接不同平台（闲鱼、微信、淘宝等）。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from src.core.message import Message, ProductInfo


@dataclass
class PlatformEvent:
    """平台事件 —— 来自平台的消息和通知的统一包装"""

    event_type: str  # new_message, order_update, system_notification
    platform: str  # xianyu, wechat, taobao
    raw_data: dict = field(default_factory=dict)
    message: Optional[Message] = None
    product: Optional[ProductInfo] = None


class PlatformAdapter(ABC):
    """
    平台适配器抽象基类

    每个平台（闲鱼、微信等）需实现此接口。
    """

    def __init__(self, platform_name: str):
        self.platform_name = platform_name

    @abstractmethod
    async def fetch_new_messages(self) -> list[PlatformEvent]:
        """拉取新的平台消息"""
        ...

    @abstractmethod
    async def send_reply(self, session_id: str, message: Message) -> bool:
        """发送回复到平台"""
        ...

    @abstractmethod
    async def mark_read(self, session_id: str) -> None:
        """标记会话已读"""
        ...

    @abstractmethod
    async def get_product_info(self, product_id: str) -> Optional[ProductInfo]:
        """获取商品信息"""
        ...

    @abstractmethod
    async def update_price(self, product_id: str, price: float) -> bool:
        """修改商品价格（议价成功后）"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """检查平台连接是否正常"""
        ...

    async def listen(self, callback):
        """
        持续监听平台消息（WebSocket 或轮询）。

        推荐子类通过 WebSocket 实现真正的实时。
        """
        while True:
            events = await self.fetch_new_messages()
            for event in events:
                await callback(event)
            import asyncio

            await asyncio.sleep(2)  # 2 秒轮询间隔，子类可覆盖
