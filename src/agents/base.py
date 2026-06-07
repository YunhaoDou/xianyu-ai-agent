"""
基础 Agent 抽象
=========
定义所有专家 Agent 必须实现的接口和共享工具。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from src.core.message import Message, MessageRole, MessageType
from src.core.session import Session


@dataclass
class AgentResponse:
    """Agent 回复封装"""

    content: str
    confidence: float = 0.8  # 置信度 0~1
    should_respond: bool = True
    role: MessageRole = MessageRole.SELLER
    msg_type: MessageType = MessageType.TEXT
    metadata: dict = field(default_factory=dict)
    suggested_state: Optional[str] = None  # 建议会话状态转换


@dataclass
class AgentDecision:
    """
    决策结果
    coordinator 用它来做最终裁决
    """

    action: str  # respond, escalate, close, transfer_to
    content: str = ""
    target_agent: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""


class BaseAgent(ABC):
    """所有 Agent 的基类"""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    @abstractmethod
    async def evaluate(
        self, session: Session, message: Message
    ) -> AgentResponse:
        """
        评估消息并生成回复。
        每个 Agent 从自己的专业领域出发分析消息。
        """
        ...

    @abstractmethod
    def can_handle(self, message: Message, session: Session) -> float:
        """
        判断此 Agent 能否处理该消息。
        返回 0.0~1.0 的匹配度分数，Coordinator 据此分派。
        """
        ...

    def build_reply(
        self,
        session: Session,
        content: str,
        msg_type: MessageType = MessageType.TEXT,
    ) -> Message:
        """构造回复消息"""
        return Message(
            session_id=session.id,
            role=MessageRole.SELLER,
            content=content,
            msg_type=msg_type,
            metadata={"agent": self.name},
        )

    def __repr__(self) -> str:
        return f"<Agent:{self.name}>"
