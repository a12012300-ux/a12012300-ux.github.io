"""
Pipeline 文章生成器（GitHub Actions 版本）
- 從商品資料庫選取今天要寫的商品（避免重複）
- 用 Claude Haiku 生成 SEO 評測文章
- 儲存 HTML + 摘要 JSON，供 build.py 使用
"""
import sys, os, json, re, hashlib
from datetime import datetime
from urllib.parse import quote
from pathlib import Path

# 確保可以 import pipeline.config
sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.config import (
    ANTHROPIC_API_KEY, ARTICLES_PER_DAY,
    SHOPEE_AFFILIATE_LINKS, MOMO_AFFILIATE_LINKS, PRODUCT_DATABASE,
    ARTICLES_DIR, DATA_DIR
)


def get_todays_products(n: int) -> list:
    """
    根據今天的日期決定今天寫哪些商品。
    用 date 的 hash 決定起始 index，確保每次執行相同、但每天不同。
    """
    today = datetime.now().strftime("%Y%m%d")
    offset = int(hashlib.md5(today.encode()).hexdigest(), 16) % len(PRODUCT_DATABASE)
    products = []
    seen_keywords = set()
    i = 0
    while len(products) < n and i < len(PRODUCT_DATABASE):
        product = PRODUCT_DATABASE[(offset + i) % len(PRODUCT_DATABASE)]
        # 每個關鍵字每天最多 1 篇，避免同類文章重複
        if product["keyword"] not in seen_keywords:
            products.append(product)
            seen_keywords.add(product["keyword"])
        i += 1
    return products


def build_product_url(product_name: str) -> str:
    return f"https://shopee.tw/search?keyword={quote(product_name)}"


def get_cta_link(keyword: str, index: int) -> tuple:
    """
    雙平台輪流：奇數篇用蝦皮，偶數篇用 momo
    回傳 (affiliate_url, platform_name)
    """
    if index % 2 == 0:
        # momo：用最接近的分類
        if "貓" in keyword:
            return MOMO_AFFILIATE_LINKS.get("貓咪用品", MOMO_AFFILIATE_LINKS["寵物用品"]), "momo"
        elif "狗" in keyword:
            return MOMO_AFFILIATE_LINKS.get("狗狗用品", MOMO_AFFILIATE_LINKS["寵物用品"]), "momo"
        elif "保健" in keyword or "維他命" in keyword or "益生菌" in keyword:
            return MOMO_AFFILIATE_LINKS.get("寵物保健品", MOMO_AFFILIATE_LINKS["寵物用品"]), "momo"
        else:
            return MOMO_AFFILIATE_LINKS["寵物用品"], "momo"
    else:
        return SHOPEE_AFFILIATE_LINKS.get(keyword, "https://shopee.tw"), "蝦皮"


def generate_article(product: dict, client, index: int = 1) -> dict:
    article_link = build_product_url(product["name"])
    cta_link, platform = get_cta_link(product["keyword"], index)

    prompt = f"""你是一位台灣的寵物部落客，請用繁體中文寫一篇 SEO 優化的商品評測文章。

商品資訊：
- 商品名稱：{product['name']}
- 價格：NT${product['price_twd']}
- 月銷量：{product['sold_monthly']} 件
- 買家評分：{product['rating']} / 5
- 購買連結：{article_link}
- 搜尋關鍵字：{product['keyword']}

文章需求：
1. 標題：包含主關鍵字「{product['keyword']}」，吸引人點擊，50字以內
2. 開頭：用飼主的痛點切入（100字）
3. 商品介紹：重點功能、材質、規格（200字）
4. 使用心得：模擬真實飼主角度，提到優缺點（200字）
5. 適合對象：什麼樣的寵物/飼主最適合（100字）
6. 購買建議：包含價格分析和購買連結，用 <a href="{article_link}">👉 蝦皮優惠價查看</a> 這個格式（100字）
7. 文末：常見問題 FAQ（3題，每題50字）

格式要求：
- 使用 HTML 格式，包含 h1, h2, p, ul 標籤
- 在文章中自然地出現關鍵字 5~8 次
- 語氣親切自然，像真人部落客
- 不要有AI感、不要有明顯廣告感

只輸出 HTML 內容本身，不要包含 ```html 標記。"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    html_content = message.content[0].text

    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html_content, re.IGNORECASE)
    title = title_match.group(1) if title_match else product["name"]
    title = re.sub(r"<[^>]+>", "", title).strip()

    return {
        "title": title,
        "html": html_content,
        "product": product,
        "affiliate_url": cta_link,
        "article_link": article_link,
        "keyword": product["keyword"],
        "price": str(product["price_twd"]),
        "rating": str(product["rating"]),
    }


def run_writer(top_n: int = None):
    if top_n is None:
        top_n = ARTICLES_PER_DAY

    os.makedirs(ARTICLES_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    if not ANTHROPIC_API_KEY:
        print("[!] 請設定 ANTHROPIC_API_KEY 環境變數")
        sys.exit(1)

    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    products = get_todays_products(top_n)
    date_str = datetime.now().strftime("%Y%m%d")

    print(f"\n{'='*50}")
    print(f"  今日選品 ({date_str})：{top_n} 篇")
    print(f"{'='*50}")

    generated = []
    for i, product in enumerate(products, 1):
        print(f"\n  [{i}/{top_n}] 生成：{product['name'][:35]}...")
        try:
            article = generate_article(product, client, index=i)
            generated.append(article)

            safe_name = re.sub(r'[\\/*?:"<>|]', "", product["name"][:30])
            html_path = f"{ARTICLES_DIR}/{date_str}_{i:02d}_{safe_name}.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<title>{article['title']}</title>
<meta name="description" content="{product['name']} 評測推薦，NT${product['price_twd']}，月銷{product['sold_monthly']}件">
</head>
<body>
{article['html']}
</body>
</html>""")
            print(f"  ✓ {html_path}")
        except Exception as e:
            print(f"  [!] 失敗：{e}")

    # 儲存摘要 JSON（build.py 讀取這個）
    summary_path = f"{DATA_DIR}/articles_summary_{date_str}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump([{
            "title": a["title"],
            "keyword": a["keyword"],
            "affiliate_url": a["affiliate_url"],
            "article_link": a["article_link"],
            "price": a["price"],
            "rating": a["rating"],
            "html_path": f"{ARTICLES_DIR}/{date_str}_{i+1:02d}_*.html",
        } for i, a in enumerate(generated)], f, ensure_ascii=False, indent=2)

    print(f"\n  共生成 {len(generated)} 篇，摘要：{summary_path}")
    return generated


if __name__ == "__main__":
    run_writer()
