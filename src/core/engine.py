"""
核心引擎模块
=========
消息处理流水线：接收消息 → 会话管理 → 协调器分发 → Agent 响应 → 回复
"""

import logging
from collections.abc import Callable
from typing import Optional

from .message import Message, MessageRole, MessageType
from .session import Session, SessionManager, SessionState

logger = logging.getLogger(__name__)


class Engine:
    """
    核心消息引擎

    职责：
    1. 接收来自平台的消息
    2. 管理会话生命周期
    3. 调用协调器分发消息给合适的 Agent
    4. 发送回复
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self._preprocessors: list[Callable] = []
        self._message_handler: Optional[Callable] = None

    def register_preprocessor(
        self, fn: Callable[[Message, Session], Message]
    ) -> None:
        """注册消息预处理器"""
        self._preprocessors.append(fn)

    def register_handler(self, fn: Callable) -> None:
        """注册主处理器（通常由 Coordinator 设置）"""
        self._message_handler = fn

    async def handle_message(self, message: Message) -> list[Message]:
        """
        处理单条消息的主入口

        流程：
        1. 获取/创建会话
        2. 执行预处理器链
        3. 调用主处理器
        4. 返回回复列表
        """
        session = self._get_or_create_session(message)
        message = self._run_preprocessors(message, session)
        session = session.add_message(message)
        self.session_manager.update_session(session)

        if self._message_handler is None:
            logger.error("No message handler registered!")
            return []

        replies = await self._message_handler(session, message)
        if not isinstance(replies, list):
            replies = [replies]

        # 将系统回复添加到会话
        for reply in replies:
            if reply is not None:
                session = session.add_message(reply)
        self.session_manager.update_session(session)

        return replies

    def _get_or_create_session(self, message: Message) -> Session:
        session = self.session_manager.get_session(message.session_id)
        if session is None:
            logger.warning(
                "Session %s not found, creating new", message.session_id
            )
            session = self.session_manager.create_session(
                buyer_id=message.metadata.get("buyer_id", "unknown"),
                seller_id=message.metadata.get("seller_id", "unknown"),
            )
            # 使用消息中的 session_id 作为会话 ID
            session = session.model_copy(update={"id": message.session_id})
            self.session_manager.update_session(session)
        return session

    def _run_preprocessors(
        self, message: Message, session: Session
    ) -> Message:
        for proc in self._preprocessors:
            message = proc(message, session)
        return message

    async def send_message(
        self,
        session: Session,
        content: str,
        role: MessageRole = MessageRole.SELLER,
        msg_type: MessageType = MessageType.TEXT,
    ) -> Message:
        """构建并发送消息"""
        return Message(
            session_id=session.id,
            role=role,
            content=content,
            msg_type=msg_type,
        )

    def handle_escalation(self, session: Session) -> Message:
        """升级到人工客服"""
        session = session.transition_to(SessionState.ESCALATED)
        self.session_manager.update_session(session)
        return Message(
            session_id=session.id,
            role=MessageRole.SYSTEM,
            content="【系统通知】已为您转接人工客服，请稍候…",
            msg_type=MessageType.SYSTEM,
        )

    def close_session(self, session: Session) -> Message:
        """关闭会话"""
        session = session.transition_to(SessionState.CLOSED)
        self.session_manager.update_session(session)
        return Message(
            session_id=session.id,
            role=MessageRole.SYSTEM,
            content="会话已结束。如有其他问题，随时联系我们！",
            msg_type=MessageType.SYSTEM,
        )
