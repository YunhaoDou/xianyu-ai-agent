#!/usr/bin/env python3
"""
订单管理系统 — 代发订单管理 + 利润核算
"""

import json
import csv
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ORDERS_FILE = BASE_DIR / "data" / "orders.json"
PRODUCTS_FILE = BASE_DIR / "data" / "products.json"


def load_orders():
    if ORDERS_FILE.exists():
        return json.loads(ORDERS_FILE.read_text(encoding="utf-8"))
    return {"orders": [], "total_revenue": 0, "total_cost": 0, "total_profit": 0}


def save_orders(data):
    ORDERS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_products():
    return json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))


def add_order(
    product_name: str,
    customer_name: str,
    selling_price: float,
    cost_price: float,
    quantity: int = 1,
    supplier: str = "",
):
    """记录一笔新订单"""
    data = load_orders()
    order = {
        "id": f"ORD{datetime.now():%Y%m%d%H%M%S}",
        "product": product_name,
        "customer": customer_name,
        "selling_price": selling_price,
        "cost_price": cost_price,
        "quantity": quantity,
        "total_revenue": round(selling_price * quantity, 2),
        "total_cost": round(cost_price * quantity, 2),
        "profit": round((selling_price - cost_price) * quantity, 2),
        "supplier": supplier,
        "status": "pending",  # pending → forwarded → shipped → completed
        "created_at": datetime.now().isoformat(),
        "shipped_at": None,
    }
    data["orders"].append(order)
    data["total_revenue"] = round(
        data["total_revenue"] + order["total_revenue"], 2
    )
    data["total_cost"] = round(data["total_cost"] + order["total_cost"], 2)
    data["total_profit"] = round(data["total_profit"] + order["profit"], 2)
    save_orders(data)
    return order


def mark_shipped(order_id: str, tracking_number: str = ""):
    """标记订单已发货（转发给供应商后）"""
    data = load_orders()
    for order in data["orders"]:
        if order["id"] == order_id:
            order["status"] = "shipped"
            order["shipped_at"] = datetime.now().isoformat()
            order["tracking"] = tracking_number
            save_orders(data)
            return order
    return None


def daily_report():
    """生成每日经营报告"""
    data = load_orders()
    today = datetime.now().strftime("%Y-%m-%d")
    today_orders = [
        o for o in data["orders"] if o["created_at"].startswith(today)
    ]

    print(f"\n{'=' * 50}")
    print(f"  📊 闲鱼店铺日报 — {today}")
    print(f"{'=' * 50}")

    print(f"\n  📦 今日订单: {len(today_orders)} 单")
    today_revenue = sum(o["total_revenue"] for o in today_orders)
    today_profit = sum(o["profit"] for o in today_orders)
    print(f"  💰 今日营收: ¥{today_revenue:.2f}")
    print(f"  💵 今日利润: ¥{today_profit:.2f}")
    print(f"  📈 今日毛利: {today_profit / today_revenue * 100:.1f}%" if today_revenue else "  📈 今日毛利: -")

    print(f"\n  📊 累计数据:")
    print(f"  总订单: {len(data['orders'])} 单")
    print(f"  总营收: ¥{data['total_revenue']:.2f}")
    print(f"  总成本: ¥{data['total_cost']:.2f}")
    print(f"  总利润: ¥{data['total_profit']:.2f}")
    print(f"  总毛利率: {data['total_profit'] / data['total_revenue'] * 100:.1f}%" if data['total_revenue'] else "")

    # 待处理订单
    pending = [o for o in data["orders"] if o["status"] == "pending"]
    if pending:
        print(f"\n  ⚠️  待处理订单 ({len(pending)} 单):")
        for o in pending[:5]:
            print(f"    {o['id']}  {o['product']}  ¥{o['total_revenue']}")

    return data


def export_csv():
    """导出订单数据为 CSV"""
    data = load_orders()
    today = datetime.now().strftime("%Y%m%d")
    csv_path = BASE_DIR / "data" / f"orders_{today}.csv"

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["订单ID", "商品", "客户", "售价", "成本", "数量", "营收", "利润", "状态", "时间"])
        for o in data["orders"]:
            writer.writerow([
                o["id"], o["product"], o["customer"],
                o["selling_price"], o["cost_price"], o["quantity"],
                o["total_revenue"], o["profit"], o["status"],
                o["created_at"],
            ])

    print(f"📄 CSV 已导出: {csv_path}")
    return csv_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "report":
            daily_report()
        elif cmd == "export":
            export_csv()
        elif cmd == "add" and len(sys.argv) >= 5:
            add_order(sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5]))
            print(f"✅ 订单已添加: {sys.argv[2]}")
        else:
            print("用法:")
            print("  python3 orders.py report          # 日报")
            print("  python3 orders.py export          # 导出CSV")
            print("  python3 orders.py add 商品名 客户 售价 成本  # 添加订单")
    else:
        daily_report()
