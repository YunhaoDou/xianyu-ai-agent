"""
商品专家 Agent
=========
负责解答商品详情、规格参数、发货物流等专业知识。
"""

import logging
from difflib import SequenceMatcher

from src.core.message import Message
from src.core.session import Session, SessionState

from .base import AgentResponse, BaseAgent

logger = logging.getLogger(__name__)

PRODUCT_FAQ = {
    "发货": "一般下单后 24 小时内发货，快递默认中通/圆通，如需顺丰可以补差价哦～",
    "物流": "发货后通常 2-4 天到货，可以提供快递单号方便您查询～",
    "退货": "支持 7 天无理由退货（不影响二次销售的前提下），非质量问题退回运费自理哦～",
    "保修": "本商品享受 {warranty} 保修服务，具体细则可查看商品详情页～",
    "尺寸": "亲，具体尺寸信息可以参考商品详情页哦，如果还有疑问可以告诉我具体部位帮你确认～",
    "颜色": "这款有 {colors} 可选，您喜欢哪个颜色呢？😊",
    "质量": "亲放心，我们所有商品都是实物拍摄，保证正品，支持验货～",
    "现货": "目前有现货的，拍下即可发货～",
    "包邮": "满 {free_shipping_threshold} 包邮哦！不够的话也可以和别的商品一起凑单～",
    "发票": "可以提供电子发票，下单时备注一下发票抬头就行～",
}


class ProductExpertAgent(BaseAgent):
    """商品专家 Agent"""

    def __init__(self):
        super().__init__(
            name="product_expert",
            description="商品专家：解答商品详情、规格、物流、售后政策等问题",
        )

    async def evaluate(
        self, session: Session, message: Message
    ) -> AgentResponse:
        content = message.content.lower()
        product = session.conversation.product

        # 找到最匹配的 FAQ 主题
        reply = self._match_faq(content, product)
        if reply:
            return AgentResponse(
                content=reply,
                confidence=0.85,
                should_respond=True,
                suggested_state=SessionState.INQUIRING.value,
                metadata={"agent_action": "answer_faq"},
            )

        # 通用商品介绍 - 仅当消息包含商品相关问题
        if product and self._is_product_inquiry(content):
            reply = (
                f"关于【{product.title}】的更多信息："
                f"原价 ¥{product.original_price or '未知'}，"
                f"现价 ¥{product.price}，{product.description[:100]}"
            )
            return AgentResponse(
                content=reply,
                confidence=0.6,
                should_respond=True,
                metadata={"agent_action": "product_intro"},
            )

        return AgentResponse(
            content="", should_respond=False, confidence=0.1
        )

    def can_handle(self, message: Message, session: Session) -> float:
        content = message.content.lower()
        product_keywords = [
            "尺寸", "颜色", "多大", "多重", "材质", "保修", "发票",
            "发货", "物流", "快递", "包邮", "退货", "退款", "质量",
            "正品", "真假", "实物", "细节", "参数", "规格", "版本",
            "什么情况", "怎么用", "能用吗", "好不好", "怎么样",
            "哪里", "产地", "生产", "日期", "保质期", "全新",
        ]
        score = sum(1 for kw in product_keywords if kw in content)
        if score >= 2:
            return 0.85
        if score == 1:
            return 0.5
        return 0.1

    def _match_faq(self, content: str, product=None) -> str:
        """匹配 FAQ 并返回回复"""
        best_match = None
        best_score = 0.0

        for keyword, template in PRODUCT_FAQ.items():
            if keyword in content:
                # 直接包含关键词
                best_score = 1.0
                best_match = keyword
                break
            # 模糊匹配
            score = SequenceMatcher(None, keyword, content).ratio()
            if score > best_score and score > 0.3:
                best_score = score
                best_match = keyword

        if best_match:
            reply = PRODUCT_FAQ[best_match]
            # 填充模板变量
            if "{warranty}" in reply:
                reply = reply.replace(
                    "{warranty}", getattr(product, "warranty", "一年")
                )
            if "{colors}" in reply:
                reply = reply.replace(
                    "{colors}", getattr(product, "colors", "多色可选")
                )
            if "{free_shipping_threshold}" in reply:
                reply = reply.replace(
                    "{free_shipping_threshold}",
                    str(getattr(product, "free_shipping_threshold", 99)),
                )
            return reply
        return ""

    def _is_product_inquiry(self, content: str) -> bool:
        """判断消息是否包含商品相关咨询"""
        inquiry_keywords = [
            "什么", "怎么", "哪里", "吗", "?", "？",
            "介绍", "详情", "看看", "描述", "参数",
            "尺寸", "颜色", "多大", "多重",
            "发货", "物流", "快递", "包邮",
            "退货", "退款", "保修", "售后",
            "质量", "正品", "真假",
        ]
        return any(kw in content for kw in inquiry_keywords)
