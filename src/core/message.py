"""
消息模型模块
=========
定义系统中流转的核心数据模型，包括消息、会话、商品信息等。
使用 Pydantic 确保类型安全和数据校验。
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(str, Enum):
    """消息角色枚举"""

    BUYER = "buyer"  # 买家
    SELLER = "seller"  # 卖家（我方）
    SYSTEM = "system"  # 系统消息
    AGENT_GREETER = "agent_greeter"  # 迎宾专家
    AGENT_NEGOTIATOR = "agent_negotiator"  # 议价专家
    AGENT_PRODUCT = "agent_product"  # 商品专家
    AGENT_AFTER_SALES = "agent_after_sales"  # 售后专家
    COORDINATOR = "coordinator"  # 协调器决策


class MessageType(str, Enum):
    """消息类型枚举"""

    TEXT = "text"
    IMAGE = "image"
    SYSTEM = "system"
    OFFER = "offer"  # 出价/议价
    ORDER = "order"  # 订单相关
    QUESTION = "question"  # 提问
    COMPLAINT = "complaint"  # 投诉/纠纷


class Message(BaseModel):
    """统一消息模型"""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    session_id: str
    role: MessageRole
    content: str
    msg_type: MessageType = MessageType.TEXT
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)

    def is_from_buyer(self) -> bool:
        return self.role == MessageRole.BUYER

    def is_from_agent(self) -> bool:
        return (
            self.role.value.startswith("agent_")
            or self.role == MessageRole.SELLER
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role.value,
            "content": self.content,
            "msg_type": self.msg_type.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class ProductInfo(BaseModel):
    """商品信息模型"""

    product_id: str = ""
    title: str = ""
    price: float = 0.0
    original_price: Optional[float] = None
    description: str = ""
    condition: str = ""  # 新旧程度
    images: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    accept_price_range: Optional[tuple[float, float]] = None  # (最低接受价, 标价)
    stock: int = 1

    model_config = ConfigDict(frozen=True)


class Participant(BaseModel):
    """参与者信息"""

    user_id: str
    nickname: str = ""
    avatar: str = ""
    credit_score: int = 0  # 信用分
    is_buyer: bool = True
    metadata: dict = Field(default_factory=dict)


class Conversation(BaseModel):
    """对话（一组有序消息）"""

    messages: list[Message] = Field(default_factory=list)
    product: Optional[ProductInfo] = None
    buyer: Optional[Participant] = None
    seller: Optional[Participant] = None

    def add_message(self, message: Message) -> "Conversation":
        return Conversation(
            messages=[*self.messages, message],
            product=self.product,
            buyer=self.buyer,
            seller=self.seller,
        )

    @property
    def last_message(self) -> Optional[Message]:
        return self.messages[-1] if self.messages else None

    @property
    def buyer_messages(self) -> list[Message]:
        return [m for m in self.messages if m.is_from_buyer()]

    @property
    def agent_messages(self) -> list[Message]:
        return [m for m in self.messages if m.is_from_agent()]

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def summary(self) -> str:
        """生成对话摘要"""
        if not self.messages:
            return "[空对话]"
        lines = []
        for m in self.messages:
            role_tag = m.role.value
            content_preview = m.content[:80] + ("..." if len(m.content) > 80 else "")
            lines.append(f"[{role_tag}] {content_preview}")
        return "\n".join(lines)
