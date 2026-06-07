"""
工具函数模块
=========
提供文本处理、价格格式化、关键词提取等通用工具函数。
"""

import re
from difflib import SequenceMatcher
from typing import Optional


def format_price(price: float, include_symbol: bool = True) -> str:
    """格式化价格"""
    symbol = "¥" if include_symbol else ""
    if price == int(price):
        return f"{symbol}{int(price)}"
    return f"{symbol}{price:.2f}"


def truncate_text(text: str, max_length: int = 100) -> str:
    """截断文本并添加省略号"""
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + "..."


def extract_keywords(text: str, max_count: int = 5) -> list[str]:
    """简单文本关键词提取"""
    text = text.lower()

    # 价格提取
    prices = re.findall(r"\d+(?:\.\d+)?", text)
    price_keywords = [f"价格:{p}" for p in prices[:2]]

    # 意图关键词
    intent_keywords = {
        "buy": ["买", "下单", "拍下", "要了", "付款"],
        "bargain": ["便宜", "优惠", "打折", "降价", "砍价", "最低"],
        "question": ["什么", "怎么", "哪里", "请问", "吗", "?"],
        "complaint": ["差评", "投诉", "退货", "退款", "坏了", "破损"],
    }

    found = []
    for intent, keywords in intent_keywords.items():
        for kw in keywords:
            if kw in text:
                found.append(f"{intent}:{kw}")
                break

    return (price_keywords + found)[:max_count]


def sanitize_message(text: str) -> str:
    """清洗消息文本（去除多余空格、特殊字符等）"""
    # 去除首尾空格
    text = text.strip()
    # 合并多个空格/换行
    text = re.sub(r"\s+", " ", text)
    # 去除表情符号中的冗余空格
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    return text


def calculate_similarity(text1: str, text2: str) -> float:
    """计算两个文本的相似度（0~1）"""
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def parse_duration(duration_str: str) -> Optional[int]:
    """解析时间字符串为秒数"""
    duration_str = duration_str.strip().lower()
    patterns = [
        (r"(\d+)\s*秒", 1),
        (r"(\d+)\s*分", 60),
        (r"(\d+)\s*小时?", 3600),
        (r"(\d+)\s*天", 86400),
        (r"(\d+)\s*周", 604800),
    ]
    for pat, multiplier in patterns:
        m = re.search(pat, duration_str)
        if m:
            return int(m.group(1)) * multiplier
    return None
