"""
上下文记忆管理模块
=========
维护对话的上下文信息，支持短期记忆（本轮对话）和长期记忆（买家画像/历史偏好）。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from src.core.message import Conversation

logger = logging.getLogger(__name__)


class ContextEntry(BaseModel):
    """单条上下文条目"""

    key: str
    value: str
    source: str = "extracted"  # extracted / inferred / explicit
    confidence: float = 0.8
    timestamp: datetime = Field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
        }


class ConversationMemory:
    """
    对话记忆管理器

    短期记忆：当前会话中的上下文（已聊过的内容）
    长期记忆：买家的历史偏好、购买记录等（JSON 持久化）
    """

    def __init__(self, storage_dir: str = "data/memory"):
        self._short_term: dict[str, dict[str, ContextEntry]] = {}
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._long_term: dict[str, dict[str, ContextEntry]] = {}
        self._load_long_term()

    # ---- 短期记忆 ----

    def set_short_term(
        self, session_id: str, key: str, value: str, confidence: float = 0.8
    ) -> None:
        if session_id not in self._short_term:
            self._short_term[session_id] = {}
        self._short_term[session_id][key] = ContextEntry(
            key=key,
            value=value,
            confidence=confidence,
            source="explicit",
        )

    def get_short_term(
        self, session_id: str, key: str
    ) -> Optional[ContextEntry]:
        return self._short_term.get(session_id, {}).get(key)

    def get_all_short_term(self, session_id: str) -> dict[str, ContextEntry]:
        return self._short_term.get(session_id, {})

    def clear_short_term(self, session_id: str) -> None:
        self._short_term.pop(session_id, None)

    # ---- 长期记忆（买家画像） ----

    def set_long_term(
        self,
        buyer_id: str,
        key: str,
        value: str,
        confidence: float = 0.8,
        source: str = "inferred",
    ) -> None:
        if buyer_id not in self._long_term:
            self._long_term[buyer_id] = {}
        self._long_term[buyer_id][key] = ContextEntry(
            key=key,
            value=value,
            confidence=confidence,
            source=source,
        )
        self._save_long_term()

    def get_long_term(
        self, buyer_id: str, key: str
    ) -> Optional[ContextEntry]:
        return self._long_term.get(buyer_id, {}).get(key)

    def get_buyer_profile(self, buyer_id: str) -> dict[str, ContextEntry]:
        return self._long_term.get(buyer_id, {})

    def extract_context_from_conversation(
        self, conversation: Conversation
    ) -> dict[str, str]:
        """从对话中提取关键上下文"""
        context = {}

        # 提取价格敏感度
        price_mentions = sum(
            1
            for m in conversation.messages
            if "钱" in m.content or "价" in m.content or "便宜" in m.content
        )
        if price_mentions > 2:
            context["price_sensitive"] = "high"

        # 提取关心点
        concern_keywords = {
            "quality": ["质量", "正品", "真假", "品质"],
            "shipping": ["发货", "物流", "快递", "包邮"],
            "appearance": ["颜色", "尺寸", "外观", "成色", "新旧"],
            "warranty": ["保修", "售后", "退货"],
        }
        for concern, keywords in concern_keywords.items():
            if any(kw in str(conversation.messages) for kw in keywords):
                context[f"concern_{concern}"] = "yes"

        return context

    def summarize_session(self, conversation: Conversation) -> str:
        """生成当前会话摘要（供 Agent 参考）"""
        if not conversation.messages:
            return ""

        buyer_msgs = [
            m for m in conversation.messages if m.is_from_buyer()
        ]
        agent_msgs = [
            m for m in conversation.messages if m.is_from_agent()
        ]

        lines = [
            f"对话轮数: {conversation.message_count}",
            f"买家消息: {len(buyer_msgs)} 条",
            f"回复: {len(agent_msgs)} 条",
        ]

        if buyer_msgs:
            lines.append(f"买家最新: {buyer_msgs[-1].content[:100]}")

        return "\n".join(lines)

    def _load_long_term(self) -> None:
        """从磁盘加载长期记忆"""
        mem_file = self._storage_dir / "long_term.json"
        if mem_file.exists():
            try:
                data = json.loads(mem_file.read_text())
                for buyer_id, entries in data.items():
                    self._long_term[buyer_id] = {
                        k: ContextEntry(**v) for k, v in entries.items()
                    }
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to load long-term memory: %s", e)

    def _save_long_term(self) -> None:
        """持久化长期记忆到磁盘"""
        data = {}
        for buyer_id, entries in self._long_term.items():
            data[buyer_id] = {
                k: v.to_dict() for k, v in entries.items()
            }
        mem_file = self._storage_dir / "long_term.json"
        mem_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
