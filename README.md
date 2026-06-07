
# 🤖 智能闲鱼客服机器人系统

> **闲鱼平台 AI 值守解决方案 — 7×24 小时自动化智能客服**

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 🎯 核心能力

| 能力 | 说明 |
|------|------|
| **🤖 多专家协同决策** | 4 位 AI 专家（迎宾/议价/商品/售后）分工合作，协调器统一调度 |
| **💰 智能议价系统** | 自动识别买家出价，进行多轮价格博弈，支持智能还价和自动成交 |
| **🧠 上下文感知对话** | 全程记录对话上下文，短期记忆 + 长期买家画像 |
| **🔄 会话状态管理** | 完善的状态机：问候→咨询→议价→下单→售后，自动流转 |
| **🗣 情感识别** | 识别买家情绪，自动升级高风险投诉，避免差评 |
| **🔌 平台解耦** | 抽象平台适配层，可对接闲鱼/微信/淘宝等任意平台 |

## 🏗 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   Platform Adapter                   │
│       (闲鱼 / 微信 / 淘宝 / 自定义)                    │
└──────────────────┬──────────────────────────────────┘
                   │ 消息
┌──────────────────▼──────────────────────────────────┐
│                   Core Engine                        │
│          消息处理流水线 · 会话管理 · 调度                │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│               Coordinator (协调器)                    │
│          意图分析 · Agent 分派 · 决策裁决               │
└──────┬──────┬──────┬──────┬─────────────────────────┘
       │      │      │      │
┌──────▼┐ ┌──▼───┐ ┌▼─────┐ ┌▼──────────┐
│ Greeter│ │Negoti│ │Product│ │After-Sales │
│ 迎宾   │ │议价   │ │ 商品  │ │ 售后       │
└───────┘ └──────┘ └──────┘ └───────────┘
       │      │      │      │
┌──────┴──────┴──────┴──────┴─────────────────────────┐
│                   Memory Layer                       │
│      短期记忆 · 长期画像 · 上下文管理                   │
└─────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/douyunhao/xianyu-ai-agent.git
cd xianyu-ai-agent

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

### 运行模拟对话

```bash
python -m src.main simulate --rounds 5 --price 200
```

输出示例：
```
🧪 模拟对话测试
模拟轮数: 5  |  商品标价: ¥200

📋 模拟对话开始:
───────────────────────────────────────────────────────────
你(AI)                                    | 买家
───────────────────────────────────────────────────────────
你好！欢迎光临～😊                         | 你好，这个相机还在吗？
请问想了解哪方面呢？                      | 成色怎么样？快门次...
这件【精品二手相机】当前售价 ¥200...        | 150 能出不？
亲，这个价格确实比较低了，你看 180 怎么... | 那 160 呢？我学生党...
好的亲，就按你说的 180 吧！               | 180 行不行？
```

### 启动生产模式

```bash
# 配置闲鱼 API 凭证后
python -m src.main run \
  --app-key "your_app_key" \
  --app-secret "your_app_secret" \
  --seller-id "your_seller_id"
```

## 📁 项目结构

```
xianyu-ai-agent/
├── src/
│   ├── main.py              # CLI 入口 & 应用启动
│   ├── core/
│   │   ├── engine.py         # 消息处理引擎
│   │   ├── message.py        # 数据模型（Message/Conversation/ProductInfo）
│   │   └── session.py        # 会话管理 & 状态机
│   ├── agents/
│   │   ├── base.py           # Agent 基类
│   │   ├── coordinator.py    # 协调器（Orchestrator）
│   │   ├── greeter.py        # 迎宾专家
│   │   ├── negotiator.py     # 议价专家
│   │   ├── product_expert.py # 商品专家
│   │   └── after_sales.py    # 售后专家
│   ├── memory/
│   │   └── context.py        # 上下文记忆管理
│   ├── platform/
│   │   ├── adapter.py        # 平台适配器抽象
│   │   └── xianyu.py         # 闲鱼 API 适配器
│   └── utils/
│       ├── logger.py         # 日志配置
│       └── helpers.py        # 工具函数
├── config/
│   ├── config.yaml           # 主配置
│   └── prompts.yaml          # Prompt 模板
├── tests/
│   ├── test_message.py
│   ├── test_session.py
│   ├── test_agents.py
│   └── test_engine.py
└── docs/
    └── architecture.md       # 架构文档
```

## 🧠 多 Agent 协同机制

```
买家发消息
    │
    ▼
┌─────────────┐
│  Coordinator │  ← 分析买家意图
│   (协调器)    │
└──────┬──────┘
       │ 并行调用所有 Agent 评分
       │
       ▼
┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐
│迎宾 0.2│ │议价 0.9│ │商品 0.3│ │售后 0.1│  ← Agent 自评分
└─────┘ └─────┘ └─────┘ └─────┘
       │
       │ 选择 Top-2 获取详细回复
       ▼
┌─────────────────────────────┐
│ Coordinator 汇总决策         │
│ → 选置信度最高的回复         │
│ → 处理状态转换               │
└─────────────────────────────┘
```

## ⚙️ 配置说明

### 议价策略 (`config/config.yaml`)

```yaml
bargaining:
  default_discount_range: [0.75, 0.98]  # 可接受折扣范围
  counter_offset_ratio: 0.08            # 还价让步比例
  max_bargain_rounds: 5                 # 最大议价轮数
```

### 自定义回复模板 (`config/prompts.yaml`)

可覆盖所有场景的回复文案和风格。

## 🧪 测试

```bash
# 运行所有测试
pytest tests/ -v

# 带覆盖率
pytest tests/ --cov=src --cov-report=term-missing

# 特定测试
pytest tests/test_agents.py -v -k "bargain"
```

## 🔮 路线图

- [x] 多 Agent 协同框架
- [x] 智能议价引擎
- [x] 会话状态管理
- [x] 平台适配器抽象
- [ ] 闲鱼 WebSocket 实时连接
- [ ] LLM 驱动的深度对话理解（接入 OpenAI/Claude API）
- [ ] 数据分析看板（成交率/转化率统计）
- [ ] Docker 部署
- [ ] 多店铺管理
- [ ] 自动上下架 / 智能定价

## 🤝 贡献

欢迎 Issue 和 PR！详情见 [CONTRIBUTING.md](CONTRIBUTING.md)（TODO）。

## 📄 许可

MIT License
