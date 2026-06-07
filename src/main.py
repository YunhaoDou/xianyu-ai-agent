"""
智能闲鱼客服机器人系统 - 主入口
==============================
启动整个系统，包括引擎、Agent、平台适配器和监控。

用法:
    python -m src.main run          # 运行客服机器人
    python -m src.main simulate     # 运行模拟对话（测试用）
    python -m src.main --help       # 查看帮助
"""

import asyncio
import logging
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from src.agents import (
    AfterSalesAgent,
    CoordinatorAgent,
    GreeterAgent,
    NegotiateAgent,
    ProductExpertAgent,
)
from src.core.engine import Engine
from src.core.message import Message, MessageRole, MessageType, ProductInfo
from src.core.session import SessionManager
from src.memory.context import ConversationMemory
from src.platform.xianyu import XianyuAdapter

console = Console()
app = typer.Typer(
    name="xianyu-ai-agent",
    help="智能闲鱼客服机器人系统 - 7×24 小时 AI 值守",
    add_completion=False,
)

# 全局组件
_session_manager = SessionManager()
_memory = ConversationMemory()
_engine = Engine(_session_manager)
_coordinator = CoordinatorAgent()
_adapter: Optional[XianyuAdapter] = None


def setup_logging(verbose: bool = False) -> None:
    """配置日志（美化输出）"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )


def setup_agents() -> None:
    """注册所有 Agent"""
    greeter = GreeterAgent()
    negotiator = NegotiateAgent()
    product_expert = ProductExpertAgent()
    after_sales = AfterSalesAgent()

    _coordinator.register_agents([
        greeter,
        negotiator,
        product_expert,
        after_sales,
    ])
    _engine.register_handler(_coordinator.evaluate)
    console.print(
        "[green]✓[/green] 已注册 4 个专家 Agent: "
        "迎宾 · 议价 · 商品 · 售后"
    )


@app.command()
def run(
    app_key: str = typer.Option("", "--app-key", "-k", help="闲鱼开放平台 AppKey"),
    app_secret: str = typer.Option(
        "", "--app-secret", "-s", help="闲鱼开放平台 AppSecret"
    ),
    seller_id: str = typer.Option(
        "", "--seller-id", "-u", help="卖家用户 ID"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="详细日志"
    ),
):
    """启动闲鱼 AI 客服机器人"""
    setup_logging(verbose)
    console.print(
        Panel.fit(
            "[bold cyan]🤖 智能闲鱼客服机器人[/bold cyan]\n"
            "[dim]7×24 小时 AI 值守 · 多专家协同决策 · 智能议价[/dim]",
        )
    )

    # 配置平台适配器
    global _adapter
    _adapter = XianyuAdapter(
        app_key=app_key,
        app_secret=app_secret,
        seller_id=seller_id,
    )

    # 初始化 Agent
    setup_agents()

    console.print("\n[bold yellow]🔄 正在启动消息监听...[/bold yellow]")

    if not app_key:
        console.print(
            "[yellow]⚠ 未配置闲鱼 API 凭证，运行在模拟模式。[/yellow]\n"
            "[yellow]  请使用 --app-key / --app-secret 传入凭证。[/yellow]"
        )
        console.print("[cyan]  提示: 运行 [bold]simulate[/bold] 可体验模拟对话[/cyan]")

    # 启动监听循环
    try:
        asyncio.run(_run_loop())
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 已停止服务[/yellow]")


async def _run_loop():
    """持续监听消息的主循环"""
    while True:
        events = await _adapter.fetch_new_messages()
        if events:
            console.print(f"[dim]收到 {len(events)} 条新消息[/dim]")

        await asyncio.sleep(2)


@app.command()
def simulate(
    rounds: int = typer.Option(
        5, "--rounds", "-n", help="模拟对话轮数", min=1, max=20
    ),
    product_price: float = typer.Option(
        200, "--price", "-p", help="商品标价", min=1
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细日志"),
):
    """运行模拟对话（测试多 Agent 协同效果）"""
    setup_logging(verbose)
    setup_agents()

    console.print(
        Panel.fit(
            "[bold cyan]🧪 模拟对话测试[/bold cyan]\n"
            f"[dim]模拟轮数: {rounds}  |  商品标价: ¥{product_price}[/dim]"
        )
    )

    # 创建模拟商品
    product = ProductInfo(
        product_id="demo_001",
        title="精品二手相机",
        price=product_price,
        original_price=350.0,
        description="99新，箱说全，快门次数 < 5000",
        condition="99新",
        accept_price_range=(product_price * 0.75, product_price),
    )

    # 创建会话
    session = _session_manager.create_session(
        buyer_id="buyer_demo",
        seller_id="seller_demo",
        product=product,
    )
    _memory.set_long_term(
        buyer_id="buyer_demo", key="name", value="小王", source="explicit"
    )

    # 模拟买家消息序列
    buyer_messages = [
        "你好，这个相机还在吗？",
        "成色怎么样？快门次数多少？",
        "150 能出不？",
        "那 160 呢？我学生党预算有限",
        "180 行不行？我现在就可以拍",
        "能包邮吗？",
        "好吧，就按你说的价，怎么下单？",
        "什么时候发货？",
    ]

    console.print(
        "\n[bold]📋 模拟对话开始:[/bold]\n"
        f"{'你(AI)':<40} | {'买家':<30}"
    )
    console.print("─" * 75)

    asyncio.run(_simulate_conversation(session, buyer_messages, rounds))


async def _simulate_conversation(session, messages, max_rounds):
    """异步模拟对话流程"""
    for i, msg_text in enumerate(messages[:max_rounds]):
        # 构建买家消息
        buyer_msg = Message(
            session_id=session.id,
            role=MessageRole.BUYER,
            content=msg_text,
            msg_type=MessageType.TEXT,
            metadata={"buyer_id": "buyer_demo"},
        )

        # 引擎处理
        replies = await _engine.handle_message(buyer_msg)

        # 显示结果
        for reply in replies:
            agent_name = reply.metadata.get("agent", "coordinator")
            console.print(
                f"[green]{reply.content[:80]:<40}[/green] | "
                f"[cyan]{msg_text:<30}[/cyan]"
            )
            if reply.content:
                console.print(f"  [dim](回复来自: {agent_name})[/dim]")
            console.print("─" * 75)

    # 摘要
    table = Table(title="📊 会话摘要")
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="green")
    table.add_row("消息总数", str(session.message_count))
    table.add_row("最终状态", session.state.value)
    table.add_row("对话时长", f"{session.duration_minutes:.1f} 分钟")
    console.print(table)


@app.command()
def version():
    """显示版本信息"""
    from src import __version__
    console.print(f"[bold cyan]xianyu-ai-agent[/bold cyan] v{__version__}")


if __name__ == "__main__":
    app()
