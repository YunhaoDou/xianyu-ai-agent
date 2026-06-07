"""Core module: message processing pipeline and session management."""

from .message import (
    Conversation,
    Message,
    MessageRole,
    MessageType,
    Participant,
    ProductInfo,
)
from .session import Session, SessionManager, SessionState

__all__ = [
    "Message",
    "MessageRole",
    "MessageType",
    "Conversation",
    "Participant",
    "ProductInfo",
    "Session",
    "SessionManager",
    "SessionState",
]
