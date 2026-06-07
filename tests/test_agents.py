"""Tests for all agents."""

import pytest
from src.core.message import Message, MessageRole, MessageType, ProductInfo
from src.core.session import Session, SessionManager, SessionState
from src.agents import (
    GreeterAgent,
    NegotiateAgent,
    ProductExpertAgent,
    AfterSalesAgent,
    CoordinatorAgent,
)


@pytest.fixture
def sample_product():
    return ProductInfo(
        product_id="p001",
        title="精品二手相机",
        price=200.0,
        original_price=350.0,
        description="99新，箱说全",
        condition="99新",
        accept_price_range=(150.0, 200.0),
    )


@pytest.fixture
def sample_session(sample_product):
    from src.core.message import Conversation
    return Session(
        id="test_session",
        buyer_id="buyer1",
        seller_id="seller1",
        product_id="p001",
        conversation=Conversation(product=sample_product),
    )


class TestGreeterAgent:
    @pytest.mark.asyncio
    async def test_greet_new_buyer(self, sample_session):
        agent = GreeterAgent()
        msg = Message(
            session_id="test_session",
            role=MessageRole.BUYER,
            content="你好，这个还在吗？",
        )
        # 在 INITIATED 状态应该回复问候
        response = await agent.evaluate(sample_session, msg)
        assert response.should_respond is True
        assert "想了解" in response.content or "售价" in response.content

    @pytest.mark.asyncio
    async def test_detect_buy_intent(self, sample_session):
        agent = GreeterAgent()
        session = sample_session.transition_to(SessionState.GREETING)

        # 购买意向
        msg = Message(
            session_id="test_session",
            role=MessageRole.BUYER,
            content="150 能出不？",
        )
        response = await agent.evaluate(session, msg)
        assert response.should_respond is False
        assert response.metadata.get("agent_action") == "transfer_to_negotiator"

    def test_can_handle_init(self):
        agent = GreeterAgent()
        session = Session(buyer_id="b1", seller_id="s1")
        msg = Message(session_id="s1", role=MessageRole.BUYER, content="hi")
        assert agent.can_handle(msg, session) == 0.9


class TestNegotiateAgent:
    @pytest.mark.asyncio
    async def test_extract_offer(self):
        agent = NegotiateAgent()
        assert agent._extract_offer("150") == 150.0
        assert agent._extract_offer("150块") == 150.0
        assert agent._extract_offer("¥200") == 200.0
        assert agent._extract_offer("出150") == 150.0
        assert agent._extract_offer("150块钱") == 150.0
        assert agent._extract_offer("最低能出180") == 180.0
        assert agent._extract_offer("你好") is None

    @pytest.mark.asyncio
    async def test_accept_high_offer(self, sample_session):
        agent = NegotiateAgent()
        msg = Message(
            session_id="test_session",
            role=MessageRole.BUYER,
            content="220 我要了",
        )
        response = await agent.evaluate(sample_session, msg)
        assert response.should_respond is True
        assert "220" in response.content
        assert response.metadata["agent_action"] == "accept"

    @pytest.mark.asyncio
    async def test_counter_offer_mid(self, sample_session):
        agent = NegotiateAgent()
        msg = Message(
            session_id="test_session",
            role=MessageRole.BUYER,
            content="160可以吗？",
        )
        response = await agent.evaluate(sample_session, msg)
        assert response.should_respond is True
        assert response.metadata["agent_action"] in (
            "counter_offer", "accept"
        )

    @pytest.mark.asyncio
    async def test_reject_lowball(self, sample_session):
        agent = NegotiateAgent()
        msg = Message(
            session_id="test_session",
            role=MessageRole.BUYER,
            content="50 块卖不卖",
        )
        response = await agent.evaluate(sample_session, msg)
        assert response.should_respond is True
        assert response.metadata["agent_action"] in (
            "reject_lowball", "deadlock"
        )

    def test_can_handle_bargain(self):
        agent = NegotiateAgent()
        session = Session(buyer_id="b1", seller_id="s1")
        bargain_msg = Message(
            session_id="s1",
            role=MessageRole.BUYER,
            content="还能便宜点吗？",
        )
        normal_msg = Message(
            session_id="s1",
            role=MessageRole.BUYER,
            content="你好",
        )
        assert agent.can_handle(bargain_msg, session) > 0.5
        assert agent.can_handle(normal_msg, session) < 0.5


class TestProductExpertAgent:
    @pytest.mark.asyncio
    async def test_question_about_shipping(self, sample_session):
        agent = ProductExpertAgent()
        msg = Message(
            session_id="test_session",
            role=MessageRole.BUYER,
            content="什么时候发货？",
        )
        response = await agent.evaluate(sample_session, msg)
        assert response.should_respond is True
        assert "发货" in response.content

    @pytest.mark.asyncio
    async def test_no_product_question(self, sample_session):
        agent = ProductExpertAgent()
        msg = Message(
            session_id="test_session",
            role=MessageRole.BUYER,
            content="今天天气真好",
        )
        response = await agent.evaluate(sample_session, msg)
        # 非商品问题，不回复
        assert response.should_respond is False


class TestAfterSalesAgent:
    @pytest.mark.asyncio
    async def test_complaint_response(self, sample_session):
        agent = AfterSalesAgent()
        msg = Message(
            session_id="test_session",
            role=MessageRole.BUYER,
            content="商品有问题，我要退货",
        )
        response = await agent.evaluate(sample_session, msg)
        assert response.should_respond is True
        assert "退货" in response.content or "退款" in response.content

    @pytest.mark.asyncio
    async def test_escalation_detection(self, sample_session):
        agent = AfterSalesAgent()
        msg = Message(
            session_id="test_session",
            role=MessageRole.BUYER,
            content="我要打12315投诉你！",
        )
        response = await agent.evaluate(sample_session, msg)
        assert response.metadata.get("agent_action") == "escalate"

    @pytest.mark.asyncio
    async def test_normal_message_no_reply(self, sample_session):
        agent = AfterSalesAgent()
        msg = Message(
            session_id="test_session",
            role=MessageRole.BUYER,
            content="你好",
        )
        response = await agent.evaluate(sample_session, msg)
        # 普通消息，售后不回复
        assert response.should_respond is False or response.confidence < 0.3


class TestCoordinatorAgent:
    @pytest.mark.asyncio
    async def test_coordinator_routes_bargain(self, sample_session):
        coordinator = CoordinatorAgent()
        coordinator.register_agents([
            GreeterAgent(),
            NegotiateAgent(),
            ProductExpertAgent(),
            AfterSalesAgent(),
        ])

        msg = Message(
            session_id="test_session",
            role=MessageRole.BUYER,
            content="150 卖不卖？",
        )
        response = await coordinator.evaluate(sample_session, msg)
        # 议价消息应该产生回复
        assert response is not None

    @pytest.mark.asyncio
    async def test_coordinator_closed_session(self):
        coordinator = CoordinatorAgent()
        session = Session(
            buyer_id="b1",
            seller_id="s1",
            state=SessionState.CLOSED,
        )
        msg = Message(
            session_id=session.id,
            role=MessageRole.BUYER,
            content="在吗？",
        )
        response = await coordinator.evaluate(session, msg)
        assert response.should_respond is True
        assert "关闭" in response.content

    @pytest.mark.asyncio
    async def test_coordinator_blocked_session(self):
        coordinator = CoordinatorAgent()
        session = Session(
            buyer_id="b1",
            seller_id="s1",
            state=SessionState.BLOCKED,
        )
        msg = Message(
            session_id=session.id,
            role=MessageRole.BUYER,
            content="在吗？",
        )
        response = await coordinator.evaluate(session, msg)
        assert response.should_respond is False
