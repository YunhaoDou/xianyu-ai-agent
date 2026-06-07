"""
协调器 Agent
=========
多专家协同决策的核心编排器。
负责分析买家意图、分派给最合适的 Agent、汇总决策结果。
"""

import logging
from typing import Optional

from src.core.message import Message, MessageRole, MessageType
from src.core.session import Session, SessionState

from .base import AgentDecision, AgentResponse, BaseAgent

logger = logging.getLogger(__name__)


class CoordinatorAgent(BaseAgent):
    """
    协调器 / Orchestrator

    职责：
    1. 接收引擎传来的消息和会话
    2. 并行评估所有 Agent 的匹配度和回复
    3. 根据置信度和会话状态做最终决策
    4. 处理状态转换和升级逻辑
    """

    def __init__(self):
        super().__init__(
            name="coordinator",
            description="协调器：多 Agent 协同决策，分发消息给最合适的专家",
        )
        self._agents: list[BaseAgent] = []

    def register_agent(self, agent: BaseAgent) -> None:
        """注册一个专家 Agent"""
        self._agents.append(agent)
        logger.info("Registered agent: %s", agent.name)

    def register_agents(self, agents: list[BaseAgent]) -> None:
        """批量注册 Agent"""
        for agent in agents:
            self.register_agent(agent)

    @property
    def registered_agents(self) -> list[BaseAgent]:
        return list(self._agents)

    async def evaluate(
        self, session: Session, message: Message
    ) -> AgentResponse:
        """
        主入口：分析消息，决定如何处理。

        返回最终回复（可能为空，表示不回复）。
        """
        # 特殊状态处理
        if session.state == SessionState.CLOSED:
            return AgentResponse(
                content="该会话已关闭。如有新问题请重新发起对话～",
                confidence=0.95,
                should_respond=True,
            )

        if session.state == SessionState.ESCALATED:
            return AgentResponse(
                content="【系统】您的问题已转人工处理，请稍候…",
                confidence=1.0,
                should_respond=True,
            )

        if session.state == SessionState.BLOCKED:
            return AgentResponse(
                content="", should_respond=False, confidence=1.0
            )

        # 多 Agent 评估 + 汇总决策
        decision = await self._orchestrate(session, message)

        # 执行决策
        if decision.action == "respond" and decision.content:
            return AgentResponse(
                content=decision.content,
                confidence=decision.confidence,
                should_respond=True,
                metadata={"agent_action": "coordinator_decided"},
            )

        if decision.action == "escalate":
            return AgentResponse(
                content="",
                confidence=decision.confidence,
                should_respond=False,
                metadata={"agent_action": "escalate", "reason": decision.reasoning},
            )

        if decision.action == "transfer_to":
            # 转交给另一个 agent
            return AgentResponse(
                content="",
                confidence=0.5,
                should_respond=False,
                metadata={
                    "agent_action": "transfer",
                    "target": decision.target_agent,
                },
            )

        if decision.action == "close":
            return AgentResponse(
                content="感谢您的咨询！如需帮助随时再来找我哦～😊",
                confidence=0.9,
                should_respond=True,
                suggested_state=SessionState.CLOSED.value,
            )

        # 默认不回复
        return AgentResponse(
            content="", should_respond=False, confidence=0.0
        )

    async def _orchestrate(
        self, session: Session, message: Message
    ) -> AgentDecision:
        """
        核心编排逻辑：

        1. 获取所有 Agent 的匹配度
        2. 选择 Top-K 匹配的 Agent
        3. 获取这些 Agent 的回复建议
        4. 做最终决策
        """
        # --- 步骤 1: 评分 ---
        scores = []
        for agent in self._agents:
            score = agent.can_handle(message, session)
            if score > 0:
                scores.append((agent, score))
                logger.debug(
                    "%s can_handle score: %.2f", agent.name, score
                )

        if not scores:
            logger.info("No agent can handle message")
            return AgentDecision(
                action="respond",
                content="收到您的消息了，让我看看能不能帮到您～😊",
                confidence=0.3,
                reasoning="no_agent_matched",
            )

        scores.sort(key=lambda x: x[1], reverse=True)

        # --- 步骤 2: 选 Top-2 ---
        top_agents = scores[:2]

        # --- 步骤 3: 评估 ---
        candidates: list[AgentResponse] = []
        for agent, _ in top_agents:
            try:
                response = await agent.evaluate(session, message)
                candidates.append(response)
                logger.debug(
                    "%s evaluated: confidence=%.2f, should_respond=%s",
                    agent.name,
                    response.confidence,
                    response.should_respond,
                )
            except Exception as e:
                logger.error("Agent %s evaluation error: %s", agent.name, e)

        if not candidates:
            return AgentDecision(
                action="respond",
                content="好的，我了解了～请问还有什么可以帮您的吗？😊",
                confidence=0.3,
                reasoning="agents_evaluation_empty",
            )

        # --- 步骤 4: 选择最佳回复 ---
        best = max(candidates, key=lambda r: r.confidence)

        if not best.should_respond or best.confidence < 0.3:
            # 没有 Agent 认为需要回复
            return AgentDecision(
                action="respond",
                content="",
                confidence=0.0,
                reasoning="no_agent_wants_to_respond",
            )

        return AgentDecision(
            action="respond",
            content=best.content,
            confidence=best.confidence,
            reasoning=f"best_agent_decision: {best.metadata}",
        )

    def can_handle(self, message: Message, session: Session) -> float:
        """协调器始终可用（作为兜底）"""
        return 0.5  # 中等优先级，有更专业的 Agent 优先使用

    def get_state_suggestion(self, response: AgentResponse) -> str:
        """从 Agent 回复中提取状态转换建议"""
        return response.suggested_state or ""
