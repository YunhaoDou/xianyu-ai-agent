"""
议价 Agent
=========
闲鱼最核心的 AI 能力 —— 智能议价。
立场：**坚定不移维护卖家利益**。
策略：价格锚定、稀缺性施压、三轮让步法、心理博弈。
"""

import logging
import re
from typing import Optional

from src.core.message import Message, MessageRole
from src.core.session import Session, SessionState

from .base import AgentResponse, BaseAgent

logger = logging.getLogger(__name__)

# ============================================================
# 议价模板 — 卖家利益优先话术
# ============================================================
BARGAIN_TEMPLATES = {
    # 首次还价：只退一小步，强调价值
    "counter_first": (
        "亲，这个价格真的很良心了，你看品质在这放着呢～"
        "要不这样，我给你按 {counter_price}，"
        "真的已经是底价了 😊"
    ),
    # 二次还价：更坚定，加稀缺性
    "counter_second": (
        "亲，实话说这个价全网都难找了～"
        "刚才还有别的买家在问呢。"
        "我给你做到 {counter_price}，真的最后一降了 🙏"
    ),
    # 三次还价：最后一次
    "counter_final": (
        "行吧，看你这么有诚意，我咬咬牙给你 {counter_price}。"
        "这真的是我底线了，再低宁愿自己留着 🙏"
    ),
    # 拒绝严重低报
    "reject_lowball": (
        "不好意思，这个价差太多了 😅"
        "你看看市场行情，我们这个品质卖 {counter_price} 已经是亏本出了。"
    ),
    # 拒绝太低，加说服
    "reject_persuade": (
        "亲，我们是 {condition}，{reason}。"
        "{counter_price} 真的是骨折价了，你去哪都找不到这个价～"
    ),
    # 价格锚定说服
    "persuade_value": (
        "亲你想想，原价 {original_price} 的东西，"
        "现在才卖 {current_price}，而且 {reason}。"
        "这个性价比真的没谁了～"
    ),
    # 稀缺性施压
    "scarcity": (
        "亲，不瞒你说，有好几个买家都在问了。"
        "你要是确定要的话尽快，不然可能就被别人拍走了 😅"
    ),
    # 接受（买家出价达到预期）
    "accept": (
        "好，成交！请直接拍下，我马上改价～😊"
    ),
    # 超高溢价（买家出价高于标价）
    "accept_premium": (
        "痛快！马上下单，我这就给你安排发货！🚀"
    ),
    # 僵局
    "deadlock": (
        "亲，实在抱歉，这个价真的做不了。"
        "要不你再看看，有合适的我们再聊 🙏"
    ),
    # 反问锚定
    "anchor_ask": (
        "亲，你觉得这个品质和成色，多少钱合适呢？"
        "实价就是 {price} 了，已经很划算了～"
    ),
}

# ============================================================
# 卖家利益参数
# ============================================================
# 最低成交折扣范围 — 收紧！（原 0.85-0.98 → 0.92-0.99）
MIN_ACCEPTABLE_DISCOUNT = 0.92  # 最多打 92 折
MAX_LISTED_RATIO = 0.99         # 标价上限比例

# 让步幅度 — 极小步（原 0.08 → 0.03）
FIRST_CONCESSION_RATIO = 0.03   # 第一次让步：降 3%
SECOND_CONCESSION_RATIO = 0.05  # 第二次让步：降 5%
THIRD_CONCESSION_RATIO = 0.07   # 第三次让步：降 7%（极限）

# 还价策略：还价时站卖家这边多少
# 0.8 = 还价落在买家出价到标价的 80% 处（靠近卖家）
SELLER_LEAN_RATIO = 0.85

# 直接接受阈值（买家出价 ≥ 标价的多少自动接受）
AUTO_ACCEPT_THRESHOLD = 0.97    # 出价到标价 97% 才自动接

# 最低报价条（低于标价多少 % 直接不还价，请买家走）
LOWBALL_THRESHOLD = 0.60        # 低于标价 60% 视为捣乱

# 议价疲劳轮数
MAX_COUNTER_ROUNDS = 4          # 4 轮还不成交就僵局


class NegotiateAgent(BaseAgent):
    """议价专家 Agent — 卖家利益至上"""

    def __init__(self):
        super().__init__(
            name="negotiator",
            description="议价专家：坚守卖家底线，智能价格博弈，拒绝恶意砍价",
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
                "listed_price": product.price,
                "bargain_round": result.get("round", 0),
            },
        )

    def can_handle(self, message: Message, session: Session) -> float:
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

    # ---------------------------------------------------------------
    # 出价提取 — 同前
    # ---------------------------------------------------------------
    def _extract_offer(self, content: str) -> Optional[float]:
        patterns = [
            r"(?:出|报|给|开|说|还)(?:价|到)?[¥￥]?\s*(\d+(?:\.\d+)?)",
            r"(?:最低|最多)(?:能出|给)[¥￥]?\s*(\d+(?:\.\d+)?)",
        ]
        for pat in patterns:
            m = re.search(pat, content)
            if m:
                val = float(m.group(1))
                if 1 < val < 999999:
                    return val

        for pat in [
            r"(\d+(?:\.\d+)?)\s*(?:块|元|钱|米)\s*(?:吧|呗|行不行|可以吗|卖不卖|行吗)?",
        ]:
            m = re.search(pat, content)
            if m:
                val = float(m.group(1))
                if 1 < val < 999999:
                    return val

        m = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:吧|呗|行不行|可以吗|卖不卖|行吗|我要了|要了|能出不|卖不)",
            content,
        )
        if m:
            val = float(m.group(1))
            if 1 < val < 999999:
                return val

        m = re.search(r"[¥￥](\d+(?:\.\d+)?)", content)
        if m:
            val = float(m.group(1))
            if 1 < val < 999999:
                return val

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

        content_stripped = content.strip()
        m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*", content_stripped)
        if m:
            val = float(m.group(1))
            if 1 < val < 999999:
                return val

        return None

    # ---------------------------------------------------------------
    # 核心议价 — 卖家利益版
    # ---------------------------------------------------------------
    def _handle_bargain(
        self,
        session: Session,
        product,
        buyer_offer: float,
    ) -> dict:
        listed_price = product.price
        min_acceptable = product.accept_price_range[0] if (
            product.accept_price_range
        ) else listed_price * MIN_ACCEPTABLE_DISCOUNT

        bargain_round = self._count_bargain_rounds(session)
        round_num = bargain_round + 1  # 当前是第几轮

        logger.info(
            "[议价] 标价=%.0f 买家出价=%.0f 底价=%.0f 第%d轮",
            listed_price, buyer_offer, min_acceptable, round_num,
        )

        # ============================================================
        # 情景 0：恶意低报 — 直接不还价
        # ============================================================
        if buyer_offer < listed_price * LOWBALL_THRESHOLD:
            return {
                "reply": (
                    "不好意思，这个价差太远了，完全没法做 😅"
                    "要不你先看看市场行情？"
                ),
                "confidence": 0.95,
                "action": "reject_lowball",
                "counter_price": None,
                "round": round_num,
            }

        # ============================================================
        # 情景 1：超高溢价 — 秒接！
        # ============================================================
        if buyer_offer >= listed_price:
            return {
                "reply": BARGAIN_TEMPLATES["accept_premium"],
                "confidence": 1.0,
                "action": "accept_premium",
                "counter_price": buyer_offer,
                "round": round_num,
            }

        # ============================================================
        # 情景 2：出价接近标价（>= 97%）— 说两句就接
        # ============================================================
        if buyer_offer >= listed_price * AUTO_ACCEPT_THRESHOLD:
            return {
                "reply": BARGAIN_TEMPLATES["accept"],
                "confidence": 1.0,
                "action": "accept",
                "counter_price": buyer_offer,
                "round": round_num,
            }

        # ============================================================
        # 情景 3：出价在可接受范围 — 三轮让步法
        # ============================================================
        if buyer_offer >= min_acceptable:
            return self._seller_counter(
                listed_price, buyer_offer, min_acceptable, round_num, product
            )

        # ============================================================
        # 情景 4：出价低于底价 — 先说服，再考虑松动
        # ============================================================
        return self._handle_below_floor(
            listed_price, buyer_offer, min_acceptable, round_num, product
        )

    # ---------------------------------------------------------------
    # 卖家还价 — 三轮让步法
    # ---------------------------------------------------------------
    def _seller_counter(
        self,
        listed_price: float,
        buyer_offer: float,
        min_acceptable: float,
        round_num: int,
        product,
    ) -> dict:
        """
        三轮让步法（卖家版）：
          第一轮：降 3%，说服品质
          第二轮：降 5%，加稀缺性施压
          第三轮：降 7%，最终底价
          第四轮及以上：咬死不动
        """
        gap = listed_price - buyer_offer

        if round_num == 1:
            # 第一轮：退极小一步
            concession = gap * FIRST_CONCESSION_RATIO  # 只退差价的 3%
            counter = round(listed_price - concession)
            counter = max(counter, min_acceptable)

            return {
                "reply": BARGAIN_TEMPLATES["counter_first"].format(
                    counter_price=int(counter),
                ),
                "confidence": 0.95,
                "action": "counter_first",
                "counter_price": counter,
                "round": round_num,
            }

        elif round_num == 2:
            # 第二轮：退一小步 + 稀缺性
            concession = gap * SECOND_CONCESSION_RATIO
            counter = round(listed_price - concession)
            counter = max(counter, min_acceptable)

            scarcity_msg = BARGAIN_TEMPLATES["scarcity"]
            return {
                "reply": (
                    BARGAIN_TEMPLATES["counter_second"].format(
                        counter_price=int(counter),
                    )
                    + "\n"
                    + scarcity_msg
                ),
                "confidence": 0.9,
                "action": "counter_second",
                "counter_price": counter,
                "round": round_num,
            }

        elif round_num == 3:
            # 第三轮：最后一次让步，到底价
            counter = round(min_acceptable)
            return {
                "reply": BARGAIN_TEMPLATES["counter_final"].format(
                    counter_price=int(counter),
                ),
                "confidence": 0.85,
                "action": "counter_final",
                "counter_price": counter,
                "round": round_num,
            }

        else:
            # 四轮以上：咬死底价不动
            return {
                "reply": (
                    f"亲，真的到底了 {int(min_acceptable)} 就是最低价，"
                    "再低真的做不到了 🙏 你再考虑考虑？"
                ),
                "confidence": 0.8,
                "action": "hold_line",
                "counter_price": min_acceptable,
                "round": round_num,
            }

    # ---------------------------------------------------------------
    # 低于底价处理 — 先说服，后考虑松动
    # ---------------------------------------------------------------
    def _handle_below_floor(
        self,
        listed_price: float,
        buyer_offer: float,
        min_acceptable: float,
        round_num: int,
        product,
    ) -> dict:
        """
        低于底价策略：
          第一轮：拒绝 + 价格锚定
          第二轮：拒绝 + 品质说服
          第三轮、四轮：极小步松动 + 稀缺性
          五轮以上：僵局
        """

        # 价格锚定说服
        if round_num <= 2:
            reason = self._pick_reason(product)
            return {
                "reply": BARGAIN_TEMPLATES["reject_persuade"].format(
                    condition=product.condition or "这个成色",
                    reason=reason,
                    counter_price=int(min_acceptable),
                ),
                "confidence": 0.9,
                "action": "reject_persuade",
                "counter_price": min_acceptable,
                "round": round_num,
            }

        elif round_num <= 4:
            # 第 3-4 轮：极小松动 + 稀缺性
            counter = round(min_acceptable - (min_acceptable - buyer_offer) * 0.15)
            counter = max(counter, listed_price * (MIN_ACCEPTABLE_DISCOUNT - 0.03))

            return {
                "reply": (
                    f"唉，看你真的喜欢，我帮你争取一下。"
                    f"{int(counter)} 真的破例了，"
                    f"你不要跟别人说这个价哈 🙏"
                ),
                "confidence": 0.75,
                "action": "reluctant_concession",
                "counter_price": counter,
                "round": round_num,
            }

        else:
            return {
                "reply": BARGAIN_TEMPLATES["deadlock"],
                "confidence": 0.7,
                "action": "deadlock",
                "counter_price": None,
                "round": round_num,
            }

    # ---------------------------------------------------------------
    # 品质说服理由选择
    # ---------------------------------------------------------------
    def _pick_reason(self, product) -> str:
        reasons = [
            "这个品质真的没话说",
            "全网都找不到这个价了",
            "实物比照片还新",
            "买回去绝对不后悔",
            "这个价真的是亏本出了",
            "同款里面这个成色算最好的了",
        ]

        if product.condition and "新" in product.condition:
            return f"{product.condition}，跟新的没什么区别"
        return reasons[hash(str(product)) % len(reasons)]

    # ---------------------------------------------------------------
    # 统计已发生的议价轮数
    # ---------------------------------------------------------------
    def _count_bargain_rounds(self, session: Session) -> int:
        """统计 seller 侧已回应的议价轮次"""
        count = 0
        for m in session.conversation.messages:
            if m.role in (
                MessageRole.SELLER,
                MessageRole.AGENT_NEGOTIATOR,
            ):
                content = m.content
                # 检测是否为还价类回复
                if any(kw in content for kw in [
                    "价", "便宜", "优惠", "给你", "底价",
                    "最低", "成交", "降价",
                ]):
                    count += 1
        return count
