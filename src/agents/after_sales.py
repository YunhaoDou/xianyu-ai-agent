"""
售后 Agent
=========
负责处理退货、退款、投诉和售后纠纷。
"""

import logging

from src.core.message import Message
from src.core.session import Session, SessionState

from .base import AgentResponse, BaseAgent

logger = logging.getLogger(__name__)

AFTER_SALES_TEMPLATES = {
    "refund": "亲，理解您的情况。关于退款，请您先发起退款申请，我们会尽快审核～",
    "return": "退货流程：① 在订单页面发起退货申请 ② 填写退货原因 ③"
    "寄回商品并填写运单号 ④ 我们收到后 48 小时内处理退款 🙏",
    "complaint": "非常抱歉给您带来不好的体验！我们会认真处理您的反馈，"
    "请您详细描述一下问题，我来帮您跟进～",
    "damage": "啊，商品有损坏？实在抱歉！请拍照发我看看损坏情况，"
    "我们会按照实际情况给您处理退换货或补偿～😊",
    "exchange": "好的，可以换货的。请您先发起换货申请，寄回原商品，"
    "我们在收到后尽快安排发出新的～",
    "dispute": "亲，您先别急，我来帮您查看具体情况。如果是我们的问题，"
    "一定给您妥善处理！",
    "wrong_item": "发错货了？非常抱歉！请拍照发给我，我马上给您重新补发正确的商品～",
    "delay": "抱歉让您久等了！我帮您催促一下物流，同时也为您争取一个小补偿。",
}


class AfterSalesAgent(BaseAgent):
    """售后专家 Agent"""

    def __init__(self):
        super().__init__(
            name="after_sales",
            description="售后专家：处理退货退款、投诉纠纷和售后咨询",
        )

    async def evaluate(self, session: Session, message: Message) -> AgentResponse:
        content = message.content.lower()

        # 检测情绪激烈的投诉 → 升级
        if self._is_escalation_needed(content):
            return AgentResponse(
                content="",
                confidence=0.5,
                should_respond=False,
                metadata={
                    "agent_action": "escalate",
                    "reason": "user_emotional_or_threatening",
                },
            )

        # 匹配售后场景
        reply = self._match_scenario(content)
        if reply:
            return AgentResponse(
                content=reply,
                confidence=0.8,
                should_respond=True,
                suggested_state=SessionState.AFTER_SALES.value,
                metadata={"agent_action": "after_sales_reply"},
            )

        # 不明确的售后请求 → 引导
        if self._is_after_sales_related(content):
            return AgentResponse(
                content="亲，有什么我能帮您处理的售后问题呢？"
                "退货、退款、换货还是其他问题？告诉我我会帮您解决～😊",
                confidence=0.6,
                should_respond=True,
                metadata={"agent_action": "guide_after_sales"},
            )

        return AgentResponse(content="", should_respond=False, confidence=0.1)

    def can_handle(self, message: Message, session: Session) -> float:
        content = message.content.lower()
        after_sales_keywords = [
            "退货",
            "退款",
            "换货",
            "投诉",
            "差评",
            "曝光",
            "举报",
            "坏了",
            "破损",
            "坏了",
            "有问题",
            "发错",
            "不满意",
            "退钱",
            "退掉",
            "退货退款",
            "退款退货",
            "漏发",
            "少发",
            "假货",
            "歪货",
            "劣质",
            "太差",
            "上当",
            "被骗",
            "差评",
            "给差评",
            "投诉你",
            "找客服",
            "人工客服",
            "物流",
            "还没到",
            "好久",
            "等太久",
            "延迟",
            "运输",
        ]
        score = sum(1 for kw in after_sales_keywords if kw in content)
        if score >= 2:
            return 0.9
        if score == 1:
            return 0.6
        return 0.05

    def _match_scenario(self, content: str) -> str:
        keywords_map = {
            "退款": "refund",
            "退钱": "refund",
            "退货": "return",
            "投诉": "complaint",
            "举报": "complaint",
            "破损": "damage",
            "坏了": "damage",
            "损坏": "damage",
            "换货": "exchange",
            "换一个": "exchange",
            "发错": "wrong_item",
            "发错了": "wrong_item",
            "不对": "wrong_item",
            "物流": "delay",
            "还没到": "delay",
            "太慢": "delay",
            "没收到": "delay",
            "纠纷": "dispute",
            "解决": "dispute",
        }
        for kw, scenario in keywords_map.items():
            if kw in content:
                return AFTER_SALES_TEMPLATES[scenario]
        return ""

    def _is_after_sales_related(self, content: str) -> bool:
        keywords = {
            "退货",
            "退款",
            "换货",
            "投诉",
            "售后",
            "问题商品",
            "不满意",
            "退换",
            "纠纷",
            "客服",
        }
        return bool(keywords & set(content))

    def _is_escalation_needed(self, content: str) -> bool:
        escalation_keywords = (
            "12315",
            "报警",
            "起诉",
            "律师",
            "法院",
            "工商",
            "315",
            "曝光你",
            "人肉",
            "找人",
            "你等着",
            "投诉到底",
        )
        return any(kw in content for kw in escalation_keywords)
