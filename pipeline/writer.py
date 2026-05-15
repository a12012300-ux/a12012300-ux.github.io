"""
Pipeline 文章生成器（GitHub Actions 版本）
- 從商品資料庫選取今天要寫的商品（避免重複）
- 用 Claude Haiku 生成 SEO 評測文章
- 儲存 HTML + 摘要 JSON，供 build.py 使用
"""
import sys, os, json, re, hashlib
# 確保 GitHub Actions 環境中 Unicode 輸出正常
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime
from urllib.parse import quote
from pathlib import Path

# 確保可以 import pipeline.config
sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.config import (
    ANTHROPIC_API_KEY, ARTICLES_PER_DAY,
    SHOPEE_AFFILIATE_LINKS, MOMO_AFFILIATE_LINKS, PCHOME_AFFILIATE_LINKS,
    PRODUCT_DATABASE, ARTICLES_DIR, DATA_DIR
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
    三平台輪流：1,4,7...蝦皮 / 2,5,8...momo / 3,6,9...PChome
    回傳 (affiliate_url, platform_name)
    """
    platform = index % 3

    if platform == 1:
        # 蝦皮
        return SHOPEE_AFFILIATE_LINKS.get(keyword, "https://shopee.tw"), "蝦皮"

    elif platform == 2:
        # momo
        if "貓" in keyword:
            return MOMO_AFFILIATE_LINKS.get("貓咪用品", MOMO_AFFILIATE_LINKS["寵物用品"]), "momo"
        elif "狗" in keyword:
            return MOMO_AFFILIATE_LINKS.get("狗狗用品", MOMO_AFFILIATE_LINKS["寵物用品"]), "momo"
        elif "保健" in keyword or "維他命" in keyword or "益生菌" in keyword:
            return MOMO_AFFILIATE_LINKS.get("寵物保健品", MOMO_AFFILIATE_LINKS["寵物用品"]), "momo"
        else:
            return MOMO_AFFILIATE_LINKS["寵物用品"], "momo"

    else:
        # PChome
        if "貓" in keyword:
            return PCHOME_AFFILIATE_LINKS.get("貓咪用品", PCHOME_AFFILIATE_LINKS["寵物用品"]), "PChome"
        elif "狗" in keyword:
            return PCHOME_AFFILIATE_LINKS.get("狗狗用品", PCHOME_AFFILIATE_LINKS["寵物用品"]), "PChome"
        else:
            return PCHOME_AFFILIATE_LINKS["寵物用品"], "PChome"


def generate_article(product: dict, client, index: int = 1) -> dict:
    article_link = build_product_url(product["name"])
    cta_link, platform = get_cta_link(product["keyword"], index)

    prompt = f"""你是台灣知名寵物部落客，請用繁體中文寫一篇高品質 SEO 評測文章。

商品資訊：
- 商品名稱：{product['name']}
- 價格：NT${product['price_twd']}
- 月銷量：{product['sold_monthly']} 件
- 買家評分：{product['rating']} / 5
- 搜尋關鍵字：{product['keyword']}

請生成完整 HTML 文章，結構如下（順序不變）：

<h1>吸引人的標題（含關鍵字「{product['keyword']}」，50字以內）</h1>

<p>開場 150 字：以真實飼主痛點切入，建立共鳴，自然帶出商品</p>

<div class="spec-box">
<h3>商品快速規格</h3>
<table class="spec-table">
<tr><td>商品名稱</td><td>{product['name']}</td></tr>
<tr><td>售價</td><td>NT$ {product['price_twd']}</td></tr>
<tr><td>月銷量</td><td>{product['sold_monthly']} 件</td></tr>
<tr><td>買家評分</td><td>{product['rating']} / 5</td></tr>
<tr><td>適合對象</td><td>（填入適合的寵物種類和飼主類型）</td></tr>
<tr><td>主要材質</td><td>（填入材質說明）</td></tr>
</table>
</div>

<h2>外觀與材質評測</h2>
<p>180 字，描述外觀、材質質感、做工細節，真實測試者角度</p>

<h2>實際使用心得</h2>
<p>200 字，毛孩實際使用反應，測試過程，與其他商品比較</p>

<div class="pros-cons">
<div class="pros">
<h3>優點</h3>
<ul>
<li>（具體優點 1）</li>
<li>（具體優點 2）</li>
<li>（具體優點 3，含CP值分析）</li>
</ul>
</div>
<div class="cons">
<h3>缺點</h3>
<ul>
<li>（需注意的缺點 1）</li>
<li>（需注意的缺點 2）</li>
</ul>
</div>
</div>

<h2>適合哪種飼主？</h2>
<p>100 字，具體描述最適合的使用情境</p>

<h2>購買價格分析</h2>
<p>120 字，與同類商品比較，分析CP值，提到蝦皮現有優惠。<br>
👉 <a href="{cta_link}">點這裡查看蝦皮最新優惠價</a></p>

<h2>常見問題 FAQ</h2>
<h3>（問題一，含關鍵字）？</h3>
<p>（50字解答）</p>
<h3>（問題二，使用方式）？</h3>
<p>（50字解答）</p>
<h3>（問題三，選購疑問）？</h3>
<p>（50字解答）</p>

格式要求：
- 只輸出 HTML body 內容，不要加 ```html 標記
- 關鍵字「{product['keyword']}」自然出現 6~9 次
- 語氣親切真實，像認真的飼主部落客，不要AI感
- 優缺點要具體、誠實，不要全都是優點"""

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
            print(f"  [OK] 第 {i} 篇完成：{article['title'][:40]}")

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
            import traceback
            print(f"  [ERROR] Article {i} failed: {type(e).__name__}: {str(e)[:200]}")
            traceback.print_exc()

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
