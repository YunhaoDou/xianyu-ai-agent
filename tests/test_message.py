"""Tests for message and session models."""

import pytest

from src.core.message import (
    Conversation,
    Message,
    MessageRole,
    MessageType,
    ProductInfo,
)
from src.core.session import Session, SessionManager, SessionState


class TestMessage:
    def test_create_text_message(self):
        msg = Message(
            session_id="s1",
            role=MessageRole.BUYER,
            content="你好，这个还在吗？",
        )
        assert msg.session_id == "s1"
        assert msg.role == MessageRole.BUYER
        assert msg.msg_type == MessageType.TEXT
        assert msg.id and len(msg.id) == 12

    def test_message_immutable(self):
        msg = Message(
            session_id="s1",
            role=MessageRole.BUYER,
            content="测试",
        )
        with pytest.raises(Exception):
            msg.content = "modified"

    def test_is_from_buyer(self):
        buyer_msg = Message(session_id="s1", role=MessageRole.BUYER, content="hi")
        seller_msg = Message(session_id="s1", role=MessageRole.SELLER, content="hi")
        assert buyer_msg.is_from_buyer() is True
        assert seller_msg.is_from_buyer() is False

    def test_is_from_agent(self):
        agent_msg = Message(
            session_id="s1", role=MessageRole.AGENT_NEGOTIATOR, content="议价"
        )
        buyer_msg = Message(session_id="s1", role=MessageRole.BUYER, content="hi")
        assert agent_msg.is_from_agent() is True
        assert buyer_msg.is_from_agent() is False

    def test_to_dict(self):
        msg = Message(
            session_id="s1",
            role=MessageRole.SYSTEM,
            content="system message",
            msg_type=MessageType.SYSTEM,
        )
        d = msg.to_dict()
        assert d["role"] == "system"
        assert d["msg_type"] == "system"
        assert d["content"] == "system message"


class TestConversation:
    def test_empty_conversation(self):
        conv = Conversation()
        assert conv.message_count == 0
        assert conv.last_message is None

    def test_add_message(self):
        conv = Conversation()
        msg = Message(session_id="s1", role=MessageRole.BUYER, content="test")
        conv = conv.add_message(msg)
        assert conv.message_count == 1
        assert conv.last_message == msg

    def test_buyer_messages(self):
        conv = Conversation()
        conv = conv.add_message(
            Message(session_id="s1", role=MessageRole.BUYER, content="你好")
        )
        conv = conv.add_message(
            Message(session_id="s1", role=MessageRole.SELLER, content="你好呀")
        )
        conv = conv.add_message(
            Message(session_id="s1", role=MessageRole.BUYER, content="多少钱")
        )
        assert len(conv.buyer_messages) == 2
        assert len(conv.agent_messages) == 1

    def test_summary(self):
        conv = Conversation()
        conv = conv.add_message(
            Message(
                session_id="s1", role=MessageRole.BUYER, content="你好，这个多少钱？"
            )
        )
        summary = conv.summary()
        assert "buyer" in summary
        assert "多少钱" in summary


class TestProductInfo:
    def test_create_product(self):
        product = ProductInfo(
            product_id="p001",
            title="测试商品",
            price=100.0,
            condition="九成新",
            accept_price_range=(75.0, 100.0),
        )
        assert product.title == "测试商品"
        assert product.accept_price_range == (75.0, 100.0)

    def test_product_immutable(self):
        product = ProductInfo(product_id="p1", title="test", price=50.0)
        with pytest.raises(Exception):
            product.price = 60.0


class TestSession:
    def test_create_session(self):
        session = Session(buyer_id="buyer1", seller_id="seller1")
        assert session.state == SessionState.INITIATED
        assert session.is_active is True
        assert session.message_count == 0

    def test_state_transition_valid(self):
        session = Session(buyer_id="b1", seller_id="s1")
        session = session.transition_to(SessionState.GREETING)
        assert session.state == SessionState.GREETING

        session = session.transition_to(SessionState.NEGOTIATING)
        assert session.state == SessionState.NEGOTIATING

        session = session.transition_to(SessionState.COMPLETED)
        assert session.state == SessionState.COMPLETED

    def test_state_transition_invalid(self):
        session = Session(buyer_id="b1", seller_id="s1")
        with pytest.raises(ValueError, match="Invalid transition"):
            session.transition_to(SessionState.COMPLETED)

    def test_session_is_active(self):
        active = Session(buyer_id="b1", seller_id="s1")
        assert active.is_active is True

        closed = Session(buyer_id="b1", seller_id="s1", state=SessionState.CLOSED)
        assert closed.is_active is False

    def test_session_add_message(self):
        session = Session(buyer_id="b1", seller_id="s1")
        msg = Message(session_id=session.id, role=MessageRole.BUYER, content="hi")
        session = session.add_message(msg)
        assert session.message_count == 1

    def test_should_escalate_long_conversation(self):
        session = Session(
            buyer_id="b1",
            seller_id="s1",
            state=SessionState.NEGOTIATING,
        )
        # 添加超过 20 条消息
        for i in range(21):
            msg = Message(
                session_id=session.id,
                role=MessageRole.BUYER if i % 2 == 0 else MessageRole.SELLER,
                content=f"msg {i}",
            )
            session = session.add_message(msg)
        assert session.should_escalate() is True


class TestSessionManager:
    def test_create_and_get_session(self):
        mgr = SessionManager()
        session = mgr.create_session(
            buyer_id="b1",
            seller_id="s1",
        )
        assert mgr.get_session(session.id) == session
        assert mgr.active_count == 1

    def test_get_or_create_existing(self):
        mgr = SessionManager()
        s1 = mgr.create_session(buyer_id="b1", seller_id="s1")
        s2 = mgr.get_or_create(s1.id, "b1", "s1")
        assert s1.id == s2.id

    def test_list_active_sessions(self):
        mgr = SessionManager()
        s1 = mgr.create_session(buyer_id="b1", seller_id="s1")
        s2 = mgr.create_session(buyer_id="b1", seller_id="s1")
        s3 = mgr.create_session(buyer_id="b2", seller_id="s1")

        s1 = s1.transition_to(SessionState.CLOSED)
        mgr.update_session(s1)

        active = mgr.list_active_sessions()
        assert len(active) == 2
        assert s2 in active
        assert s3 in active

    def test_list_by_state(self):
        mgr = SessionManager()
        s1 = mgr.create_session(buyer_id="b1", seller_id="s1")
        s1 = s1.transition_to(SessionState.GREETING)
        mgr.update_session(s1)
        mgr.create_session(buyer_id="b2", seller_id="s1")

        assert len(mgr.list_sessions_by_state(SessionState.GREETING)) == 1
        assert len(mgr.list_sessions_by_state(SessionState.INITIATED)) == 1

    def test_remove_session(self):
        mgr = SessionManager()
        s1 = mgr.create_session(buyer_id="b1", seller_id="s1")
        mgr.remove_session(s1.id)
        assert mgr.get_session(s1.id) is None
        assert mgr.total_count == 0
