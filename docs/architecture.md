# 架构文档

## 总体架构

系统采用 **管道-过滤器** + **多智能体协作** 架构风格。

### 分层设计

```
┌─────────────────────────────────────────────┐
│                Interface Layer               │
│       CLI · HTTP API · WebSocket Gateway      │
├─────────────────────────────────────────────┤
│              Application Layer               │
│      Engine · Coordinator · State Machine    │
├─────────────────────────────────────────────┤
│               Agent Layer                    │
│   Greeter │ Negotiator │ Product │ AfterSales│
├─────────────────────────────────────────────┤
│               Memory Layer                   │
│       Short-term · Long-term · Vector        │
├─────────────────────────────────────────────┤
│               Platform Layer                 │
│        Adapter · Xianyu API · WebSocket      │
└─────────────────────────────────────────────┘
```

## 核心数据流

```
平台消息 → Adapter.parse() → Engine.handle()
  → SessionManager.get_or_create()
  → Preprocessors (spam filter, etc.)
  → Coordinator.evaluate()
    → All Agents: can_handle() → score
    → Top-2 Agents: evaluate() → response
    → Coordinator 裁决 → 最终回复
  → Adapter.send() → 平台回复
```

## 状态机

```
INITIATED → GREETING → NEGOTIATING → ORDERING → COMPLETED
                    ↘ INQUIRING ↗              ↘ AFTER_SALES
                                                 ↘ ESCALATED → CLOSED
                    ↘ CLOSED (直接关闭)
                    ↘ BLOCKED → CLOSED
```

## 议价算法

1. 提取买家出价（支持 ¥100/100块/出100 等多种格式）
2. 获取商品可接受价格范围 [min_price, listed_price]
3. 决策树：
   - 出价 >= 标价 → 接受
   - 出价 >= min_price → 还价或接受（看轮数）
   - 出价 < min_price → 拒绝还价或僵局
4. 多轮容忍度：3 轮以上低价 → 僵局状态
