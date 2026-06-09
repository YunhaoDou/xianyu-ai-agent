#!/usr/bin/env python3
"""
商品上架工具 — 生成闲鱼文案 + 利润计算
"""

import json
import random
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "products.json"


def load_products():
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


# 商品文案模板
TITLE_TEMPLATES = [
    "{emoji} {name} 宠物{category} 超可爱",
    "{emoji} {name} 养宠必备 平价好物",
    "{emoji} {name} 自用推荐 宠物{category}",
    "{emoji} {name} 毛孩子超爱 宠物用品",
]

DESC_TEMPLATES = {
    "宠物玩具": "🐱🐶 毛孩子的新玩具来啦！\n\n"
               "✅ {name}，材质安全无毒\n"
               "✅ 耐咬耐玩，主子超喜欢\n"
               "✅ 轻巧便携，随时随地玩起来\n\n"
               "💡 小贴士：定期更换玩具可以保持宠物的新鲜感哦~\n\n"
               "🚚 下单后24小时内发货\n"
               "💬 有任何问题随时私聊我~",

    "宠物餐具": "🍽️ 吃饭也要有仪式感！\n\n"
               "✅ {name}，食品级材质\n"
               "✅ 易清洗，不滋生细菌\n"
               "✅ 防滑设计，吃饭不打滑\n\n"
               "🐾 保护毛孩子的颈椎健康~\n\n"
               "🚚 24小时发货\n"
               "💬 欢迎咨询~",

    "宠物出行": "🎒 带毛孩子出门浪！\n\n"
               "✅ {name}，安全舒适\n"
               "✅ 透气设计，夏天不闷热\n"
               "✅ 可调节，适合各种体型的毛孩子\n\n"
               "🐾 出门必备，安全第一~\n\n"
               "🚚 下单即发\n"
               "💬 尺码问题私聊我~",

    "宠物窝垫": "🛏️ 给毛孩子一个舒服的窝！\n\n"
               "✅ {name}，柔软舒适\n"
               "✅ 可拆洗，干净卫生\n"
               "✅ 四季通用，恒温舒适\n\n"
               "🐾 毛孩子一睡就不想起来~\n\n"
               "🚚 24小时发货\n"
               "💬 有疑问随时找我~",

    "宠物清洁": "🧹 养宠家庭必备清洁好物！\n\n"
               "✅ {name}，轻松打理\n"
               "✅ 宠物专用，温和不刺激\n"
               "✅ 性价比超高，养宠人必囤\n\n"
               "🐾 干净卫生，毛孩子更健康~\n\n"
               "🚚 现货秒发\n"
               "💬 赶紧下单吧~",

    "宠物饰品": "💎 打扮毛孩子，可爱翻倍！\n\n"
               "✅ {name}，颜值在线\n"
               "✅ 做工精细，不伤皮肤\n"
               "✅ 拍照上镜，朋友圈获赞神器\n\n"
               "🐾 戴上就是小区最靓的仔~\n\n"
               "🚚 24小时发货\n"
               "💬 多种颜色可选~",
}


def generate_listing(category_name, product):
    """生成一条闲鱼上架文案"""
    cat_name = category_name
    title_tpl = random.choice(TITLE_TEMPLATES)
    title = title_tpl.format(
        emoji=product.get("tags", [""])[0] if product.get("tags") else "🐾",
        name=product["name"],
        category=cat_name,
    )
    # 限制标题长度（闲鱼限制30字）
    title = title[:30]

    desc = DESC_TEMPLATES.get(
        cat_name,
        "✅ {name}\n品质保证，放心购买~\n🚚 24小时发货".format(name=product["name"]),
    ).format(name=product["name"])

    profit = product["suggest_price"] - product["cost"]
    margin = profit / product["suggest_price"] * 100

    return {
        "title": title,
        "description": desc,
        "price": product["suggest_price"],
        "cost": product["cost"],
        "profit": round(profit, 2),
        "margin": round(margin, 1),
        "unit": product.get("unit", "个"),
        "tags": product.get("tags", []),
    }


def main():
    data = load_products()
    print("=" * 65)
    print("  📋 宠物用品 上架清单 & 利润分析")
    print("=" * 65)

    total_products = 0
    total_categories = len(data["categories"])

    for cat in data["categories"]:
        cat_name = cat["name"]
        cat_emoji = cat.get("emoji", "📦")
        products = cat["products"]
        total_products += len(products)

        print(f"\n{'─' * 65}")
        print(f"  {cat_emoji}  {cat_name}（{len(products)} 款）")
        print(f"{'─' * 65}")
        print(f"  {'商品名称':<20} {'进价':>6} {'售价':>7} {'利润':>7} {'毛利率':>7}")
        print(f"  {'─' * 50}")

        for p in products:
            listing = generate_listing(cat_name, p)
            print(
                f"  {p['name']:<20} "
                f"¥{p['cost']:>5.1f} "
                f"¥{listing['price']:>5.1f} "
                f"¥{listing['profit']:>5.1f} "
                f"{listing['margin']:>6.1f}%"
            )

    print(f"\n{'=' * 65}")
    print(f"  📊 汇总: {total_categories} 个分类 × {total_products} 款商品")
    print(f"  💰 平均毛利率: ~65%")
    print(f"  📦 建议首批上架: 10-15 款"
          "\n    选品策略: 玩具2款 + 餐具2款 + 出行2款 + 窝垫2款 + 清洁3款 + 饰品2款")
    print(f"{'=' * 65}")

    # 生成闲鱼上架标题范例
    print(f"\n📌 闲鱼标题范例（前5款）:")
    count = 0
    for cat in data["categories"]:
        for p in cat["products"]:
            if count >= 5:
                break
            listing = generate_listing(cat["name"], p)
            print(f"  {listing['title']}  ¥{listing['price']}")
            count += 1


if __name__ == "__main__":
    main()
