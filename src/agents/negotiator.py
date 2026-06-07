"""
议价 Agent
=========
闲鱼最核心的 AI 能力 —— 智能议价。
支持多轮价格博弈、情感分析、自动决策。
"""

import logging
import re
from typing import Optional

from src.core.message import Message, MessageRole, MessageType
from src.core.session import Session, SessionState

from .base import AgentResponse, BaseAgent

logger = logging.getLogger(__name__)

# 议价策略模板
BARGAIN_TEMPLATES = {
    "counter_offer": "亲，这个价格确实比较低了，你看 {counter_price} 怎么样？真的已经很划算了～😊",
    "final_offer": "最低给你 {price} 了，再低真的做不到了哦 🙏",
    "reject_lowball": "不好意思，这个价格实在不行，成本都不够 😅 你看看 {counter_price} 可以吗？",
    "accept": "好的亲，就按你说的 {price} 吧！请直接拍下，我改价～😊",
    "persuade": "亲，我们这个是 {condition}，{reason}，{price} 真的很值了！",
    "deadlock": "亲，实在抱歉，这个价格确实做不了… 要不您再看看其他款？",
}

# 砍价比例区间
ACCEPTABLE_DISCOUNT_RANGE = (0.85, 0.98)  # 可接受折扣范围
COUNTER_OFFSET_RATIO = 0.08  # 还价时主动降价比例


class NegotiateAgent(BaseAgent):
    """议价专家 Agent"""

    def __init__(self):
        super().__init__(
            name="negotiator",
            description="议价专家：负责价格谈判、优惠策略和多轮议价",
        )

    async def evaluate(
        self, session: Session, message: Message
    ) -> AgentResponse:
        product = session.conversation.product
        if not product:
            return AgentResponse(
                content="", should_respond=False, confidence=0.1
            )

        buyer_offer = self._extract_offer(message.content)
        if buyer_offer is None:
            # 不是议价消息
            return AgentResponse(
                content="", should_respond=False, confidence=0.2
            )

        result = self._handle_bargain(session, product, buyer_offer)
        return AgentResponse(
            content=result["reply"],
            confidence=result["confidence"],
            should_respond=True,
            suggested_state=SessionState.NEGOTIATING.value,
            metadata={
                "agent_action": result["action"],
                "buyer_offer": buyer_offer,
                "counter_price": result.get("counter_price"),
                "bargain_round": len(
                    [m for m in session.conversation.messages
                     if m.role.value.startswith("agent_")]
                ),
            },
        )

    def can_handle(self, message: Message, session: Session) -> float:
        """检测是否为议价相关消息"""
        content = message.content.lower()

        if self._extract_offer(content) is not None:
            return 0.95

        bargain_keywords = [
            "便宜", "优惠", "打折", "降价", "少点", "抹零",
            "还能少", "最低价", "折扣", "砍价", "议价",
            "给个价", "多少钱卖", "性价比",
        ]
        score = sum(1 for kw in bargain_keywords if kw in content)
        if score >= 2:
            return 0.85
        if score == 1:
            return 0.6
        return 0.1

    def _extract_offer(self, content: str) -> Optional[float]:
        """
        从消息中提取买家出价。
        支持格式："100", "100块", "100元", "¥100", "出150", "220我要了" 等。
        """
        # 先尝试 "出/报/给 150" 模式（最精确）
        for pat in [
            r"(?:出|报|给|开|说|还)(?:价|到)?[¥￥]?\s*(\d+(?:\.\d+)?)",
            r"(?:最低|最多)(?:能出|给)[¥￥]?\s*(\d+(?:\.\d+)?)",
        ]:
            m = re.search(pat, content)
            if m:
                val = float(m.group(1))
                if 1 < val < 999999:
                    return val

        # 然后尝试 "150块", "150元", "150块钱" 等
        for pat in [
            r"(\d+(?:\.\d+)?)\s*(?:块|元|钱|米)\s*(?:吧|呗|行不行|可以吗|卖不卖|行吗)?",
        ]:
            m = re.search(pat, content)
            if m:
                val = float(m.group(1))
                if 1 < val < 999999:
                    return val

        # 宽松匹配：数字后面跟着常见议价后缀
        m = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:吧|呗|行不行|可以吗|卖不卖|行吗|我要了|要了|能出不|卖不)",
            content,
        )
        if m:
            val = float(m.group(1))
            if 1 < val < 999999:
                return val

        # 匹配行内裸数字 + 议价上下文
        m = re.search(r"[¥￥](\d+(?:\.\d+)?)", content)
        if m:
            val = float(m.group(1))
            if 1 < val < 999999:
                return val

        # 最后：行内独立数字（如果周围有议价关键词）
        bargain_context = any(
            kw in content
            for kw in [
                "钱", "价", "便宜", "优惠", "卖", "出", "砍",
                "少", "低", "多少",
            ]
        )
        if bargain_context:
            numbers = re.findall(r"\b(\d+(?:\.\d+)?)\b", content)
            for num in numbers:
                val = float(num)
                if 1 < val < 999999:
                    return val

        # 纯数字匹配（消息主要部分为数字）
        content_stripped = content.strip()
        m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*", content_stripped)
        if m:
            val = float(m.group(1))
            if 1 < val < 999999:
                return val

        return None

    def _handle_bargain(
        self,
        session: Session,
        product,
        buyer_offer: float,
    ) -> dict:
        """核心议价逻辑"""
        listed_price = product.price
        min_price, max_price = product.accept_price_range or (
            listed_price * ACCEPTABLE_DISCOUNT_RANGE[0],
            listed_price,
        )

        bargain_count = self._count_bargain_rounds(session)

        # --- 情景 1：买家出价 >= 标价 → 直接接受 ---
        if buyer_offer >= listed_price:
            return {
                "reply": BARGAIN_TEMPLATES["accept"].format(price=buyer_offer),
                "confidence": 1.0,
                "action": "accept",
                "counter_price": buyer_offer,
            }

        # --- 情景 2：买家出价在可接受范围 → 还价或接受 ---
        if buyer_offer >= min_price:
            if bargain_count >= 2:
                # 已议价多轮，接受
                return {
                    "reply": BARGAIN_TEMPLATES["accept"].format(
                        price=buyer_offer
                    ),
                    "confidence": 0.95,
                    "action": "accept",
                    "counter_price": buyer_offer,
                }
            else:
                # 还一个中间的价
                diff = listed_price - buyer_offer
                counter = buyer_offer + diff * 0.6
                counter = max(counter, min_price)
                counter = round(counter, 0)
                return {
                    "reply": BARGAIN_TEMPLATES["counter_offer"].format(
                        counter_price=int(counter),
                    ),
                    "confidence": 0.9,
                    "action": "counter_offer",
                    "counter_price": counter,
                }

        # --- 情景 3：出价太低，但可以还价 ---
        if bargain_count < 3:
            counter = min_price + (buyer_offer - min_price) * 0.3
            counter = max(counter, min_price)
            counter = round(counter, 0)
            return {
                "reply": BARGAIN_TEMPLATES["reject_lowball"].format(
                    counter_price=int(counter),
                ),
                "confidence": 0.8,
                "action": "reject_lowball",
                "counter_price": counter,
            }

        # --- 情景 4：多轮低价 → 僵局 ---
        return {
            "reply": BARGAIN_TEMPLATES["deadlock"],
            "confidence": 0.7,
            "action": "deadlock",
            "counter_price": None,
        }

    def _count_bargain_rounds(self, session: Session) -> int:
        """统计已发生的议价轮数"""
        count = 0
        for m in session.conversation.messages:
            if m.role == MessageRole.SELLER and "价钱" in m.content:
                count += 1
        return count
