"""
迎宾 Agent
=========
负责初次接触时的问候、商品简介，以及基本信息收集。
"""

import logging

from src.core.message import Message
from src.core.session import Session, SessionState

from .base import AgentResponse, BaseAgent

logger = logging.getLogger(__name__)

# 迎宾模板
GREETING_TEMPLATES = {
    "welcome": "你好！欢迎光临～😊 有什么想了解的随时问我哦！",
    "product_intro": "这件【{title}】当前售价 ¥{price}，{condition}。请问您有什么想了解的吗？^_^",
    "need_info": "你好！请问想了解哪方面呢？我可以帮你解答商品详情、价格、发货等任何问题～",
    "follow_up": "亲，还在吗？有什么可以帮你的吗？😊",
    "auto_reply_away": "店主暂时不在，我是 AI 客服小助手，有什么问题可以先问我哦！",
}

# 关键词 → 是否购买意向
BUY_INTENT_KEYWORDS = [
    "怎么买",
    "多少钱",
    "下单",
    "链接",
    "价格",
    "还能便宜",
    "包邮",
    "在吗",
    "有货",
    "什么时候",
    "还能少",
    "最低",
    "看看实物",
    "拍下",
    "直接买",
    "要了",
    "我要了",
    "尺寸",
    "多长",
    "多高",
    "多重",
    "颜色",
    "能出不",
    "卖不",
    "出吗",
    "便宜点",
    "优惠",
    "价",
    "砍价",
    "少点",
    "包邮吗",
]

WASTE_KEYWORDS = [
    "你好",
    "在吗",
    "在不在",
    "hi",
    "hello",
    "您好",
    "你好呀",
]


class GreeterAgent(BaseAgent):
    """迎宾与初始客服 Agent"""

    def __init__(self):
        super().__init__(
            name="greeter",
            description="迎宾客服：负责初次问候、商品介绍和基本信息引导",
        )

    async def evaluate(self, session: Session, message: Message) -> AgentResponse:
        """根据会话阶段生成合适的迎宾回复"""
        if session.state == SessionState.INITIATED:
            return self._handle_init(session, message)
        elif session.state == SessionState.GREETING:
            return self._handle_greeting(session, message)
        else:
            # 非迎宾阶段，不会主动回复（除非刚好匹配迎宾场景）
            return AgentResponse(content="", should_respond=False, confidence=0.1)

    def _handle_init(self, session: Session, message: Message) -> AgentResponse:
        """初始消息处理"""
        product = session.conversation.product
        if product and product.title:
            content = GREETING_TEMPLATES["product_intro"].format(
                title=product.title,
                price=product.price,
                condition=product.condition or "具体成色见图",
            )
        else:
            content = GREETING_TEMPLATES["welcome"]

        return AgentResponse(
            content=content,
            confidence=0.9,
            should_respond=True,
            suggested_state=SessionState.GREETING.value,
            metadata={"agent_action": "greet_new_buyer"},
        )

    def _handle_greeting(self, session: Session, message: Message) -> AgentResponse:
        """迎宾阶段的消息处理"""
        content = message.content.lower()

        # 检测购买意向 → 转交议价或商品专家
        if any(kw in content for kw in BUY_INTENT_KEYWORDS):
            return AgentResponse(
                content="",
                should_respond=False,
                confidence=0.3,
                metadata={"agent_action": "transfer_to_negotiator"},
            )

        # 纯寒暄
        if any(kw in content for kw in WASTE_KEYWORDS) and len(content) < 10:
            return AgentResponse(
                content=GREETING_TEMPLATES["need_info"],
                confidence=0.7,
                should_respond=True,
            )

        # 默认继续倾听
        return AgentResponse(
            content="",
            should_respond=False,
            confidence=0.2,
        )

    def can_handle(self, message: Message, session: Session) -> float:
        """迎宾 Agent 只在会话初期活跃"""
        if session.state in (SessionState.INITIATED, SessionState.GREETING):
            return 0.9
        if session.message_count <= 3:
            return 0.5
        return 0.1
