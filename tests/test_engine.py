"""Tests for the core engine."""

import pytest
from src.core.engine import Engine
from src.core.message import Message, MessageRole, MessageType
from src.core.session import SessionManager, SessionState


@pytest.mark.asyncio
async def test_engine_handle_message_creates_session():
    """引擎收到消息后应自动创建会话"""
    mgr = SessionManager()
    engine = Engine(mgr)

    msg = Message(
        session_id="new_session",
        role=MessageRole.BUYER,
        content="你好",
        metadata={"buyer_id": "b1", "seller_id": "s1"},
    )

    async def mock_handler(session, message):
        return []

    engine.register_handler(mock_handler)
    replies = await engine.handle_message(msg)

    # 会话应自动创建
    session = mgr.get_session("new_session")
    assert session is not None
    assert session.buyer_id == "b1"


@pytest.mark.asyncio
async def test_engine_handler_invoked():
    """引擎应调用注册的 handler"""
    mgr = SessionManager()
    engine = Engine(mgr)

    msg = Message(
        session_id="s1",
        role=MessageRole.BUYER,
        content="你好",
        metadata={"buyer_id": "b1", "seller_id": "s1"},
    )

    handler_called = False

    async def mock_handler(session, message):
        nonlocal handler_called
        handler_called = True
        return [
            Message(
                session_id=session.id,
                role=MessageRole.SELLER,
                content="你好呀",
            )
        ]

    engine.register_handler(mock_handler)
    replies = await engine.handle_message(msg)

    assert handler_called is True
    assert len(replies) == 1
    assert replies[0].content == "你好呀"


@pytest.mark.asyncio
async def test_engine_preprocessor():
    """预处理器应按顺序执行"""
    mgr = SessionManager()
    engine = Engine(mgr)

    msg = Message(
        session_id="s1",
        role=MessageRole.BUYER,
        content="hi",
        metadata={"buyer_id": "b1", "seller_id": "s1"},
    )

    processed = []

    def preproc1(m, s):
        processed.append("proc1")
        return m

    def preproc2(m, s):
        processed.append("proc2")
        return m

    async def mock_handler(session, message):
        return []

    engine.register_preprocessor(preproc1)
    engine.register_preprocessor(preproc2)
    engine.register_handler(mock_handler)
    await engine.handle_message(msg)

    assert processed == ["proc1", "proc2"]


@pytest.mark.asyncio
async def test_engine_escalation():
    """引擎应正确处理升级人工"""
    mgr = SessionManager()
    engine = Engine(mgr)

    session = mgr.create_session(buyer_id="b1", seller_id="s1")
    msg = engine.handle_escalation(session)

    assert msg.role == MessageRole.SYSTEM
    assert "转接人工" in msg.content

    updated = mgr.get_session(session.id)
    assert updated.state == SessionState.ESCALATED


@pytest.mark.asyncio
async def test_engine_close_session():
    """引擎应正确关闭会话"""
    mgr = SessionManager()
    engine = Engine(mgr)

    session = mgr.create_session(buyer_id="b1", seller_id="s1")
    msg = engine.close_session(session)

    assert msg.role == MessageRole.SYSTEM
    assert "结束" in msg.content

    updated = mgr.get_session(session.id)
    assert updated.state == SessionState.CLOSED
