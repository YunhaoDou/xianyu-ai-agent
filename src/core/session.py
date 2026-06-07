"""
会话管理模块
=========
管理买卖双方的会话生命周期、状态机转换和持久化。
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field
from strenum import StrEnum

from .message import Conversation, Message, ProductInfo


class SessionState(StrEnum):
    """会话状态机"""

    INITIATED = "initiated"  # 初始创建
    GREETING = "greeting"  # 迎宾阶段
    NEGOTIATING = "negotiating"  # 议价阶段
    INQUIRING = "inquiring"  # 商品咨询
    ORDERING = "ordering"  # 下单中
    AFTER_SALES = "after_sales"  # 售后
    COMPLETED = "completed"  # 已完成
    CLOSED = "closed"  # 已关闭
    ESCALATED = "escalated"  # 升级人工
    BLOCKED = "blocked"  # 黑名单


# 状态转换规则
STATE_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.INITIATED: {SessionState.GREETING, SessionState.ESCALATED, SessionState.CLOSED},
    SessionState.GREETING: {
        SessionState.NEGOTIATING,
        SessionState.INQUIRING,
        SessionState.CLOSED,
    },
    SessionState.NEGOTIATING: {
        SessionState.INQUIRING,
        SessionState.ORDERING,
        SessionState.COMPLETED,
        SessionState.CLOSED,
        SessionState.ESCALATED,
    },
    SessionState.INQUIRING: {
        SessionState.NEGOTIATING,
        SessionState.ORDERING,
        SessionState.CLOSED,
    },
    SessionState.ORDERING: {
        SessionState.AFTER_SALES,
        SessionState.COMPLETED,
        SessionState.CLOSED,
    },
    SessionState.AFTER_SALES: {
        SessionState.COMPLETED,
        SessionState.ESCALATED,
        SessionState.CLOSED,
    },
    SessionState.COMPLETED: {SessionState.AFTER_SALES, SessionState.CLOSED},
    SessionState.CLOSED: set(),
    SessionState.ESCALATED: {SessionState.CLOSED},
    SessionState.BLOCKED: {SessionState.CLOSED},
}


class Session(BaseModel):
    """会话实体"""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    buyer_id: str
    seller_id: str
    product_id: str = ""
    state: SessionState = SessionState.INITIATED
    conversation: Conversation = Field(default_factory=Conversation)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    priority: int = 0  # 优先级（用于队列调度）
    context: dict = Field(default_factory=dict)  # 扩展上下文

    def transition_to(self, new_state: SessionState) -> "Session":
        """执行状态转换"""
        if new_state not in STATE_TRANSITIONS.get(self.state, set()):
            raise ValueError(
                f"Invalid transition: {self.state} -> {new_state}. "
                f"Allowed: {STATE_TRANSITIONS.get(self.state, set())}"
            )
        return self.model_copy(
            update={
                "state": new_state,
                "updated_at": datetime.now(),
            }
        )

    def add_message(self, message: Message) -> "Session":
        return self.model_copy(
            update={
                "conversation": self.conversation.add_message(message),
                "updated_at": datetime.now(),
            }
        )

    @property
    def message_count(self) -> int:
        return self.conversation.message_count

    @property
    def is_active(self) -> bool:
        return self.state not in (SessionState.CLOSED, SessionState.COMPLETED)

    @property
    def duration_minutes(self) -> float:
        delta = datetime.now() - self.created_at
        return delta.total_seconds() / 60

    def should_escalate(self) -> bool:
        """判断是否应升级人工"""
        if self.state == SessionState.ESCALATED:
            return True
        # 超过 20 轮对话仍未成交
        if self.message_count > 20 and self.state in (
            SessionState.NEGOTIATING,
            SessionState.INQUIRING,
        ):
            return True
        return False


class SessionManager:
    """会话管理器（内存存储，可扩展为 Redis/DB）"""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create_session(
        self,
        buyer_id: str,
        seller_id: str,
        product: Optional[ProductInfo] = None,
    ) -> Session:
        """创建新会话"""
        session = Session(
            buyer_id=buyer_id,
            seller_id=seller_id,
            product_id=product.product_id if product else "",
            conversation=Conversation(product=product),
            state=SessionState.INITIATED,
        )
        self._sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def update_session(self, session: Session) -> None:
        self._sessions[session.id] = session

    def get_or_create(
        self,
        session_id: str,
        buyer_id: str,
        seller_id: str,
        product: Optional[ProductInfo] = None,
    ) -> Session:
        """获取或创建会话"""
        session = self.get_session(session_id)
        if session is None:
            session = self.create_session(buyer_id, seller_id, product)
        return session

    def list_active_sessions(self) -> list[Session]:
        return [s for s in self._sessions.values() if s.is_active]

    def list_sessions_by_buyer(self, buyer_id: str) -> list[Session]:
        return [
            s for s in self._sessions.values() if s.buyer_id == buyer_id
        ]

    def list_sessions_by_state(self, state: SessionState) -> list[Session]:
        return [s for s in self._sessions.values() if s.state == state]

    def remove_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    @property
    def total_count(self) -> int:
        return len(self._sessions)

    @property
    def active_count(self) -> int:
        return len(self.list_active_sessions())
