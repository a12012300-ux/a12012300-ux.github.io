"""
run_pipeline.py  —  毛孩研究室 每日自動發文管線
=========================================================
完整流程：
  1. 搜尋高傭金寵物商品（commission_finder）
     - 按「傭金率 × 單價 × 評分」排序
     - 下載商品主圖存至 posts/images/
  2. 用 Claude Haiku 生成 SEO 評測文章（writer）
     - Prompt 含真實商品名、價格、圖片
     - 每篇 2000+ 字，含 FAQ、優缺點表格
  3. 套用 HTML 模板、更新首頁（build.py）
     - TOC 目錄、相關文章、Schema.org
  4. 生成 IG/Threads 社群貼文 + 圖文卡
  5. 推送 GitHub Pages
  6. 寄 Email 通知（含圖文卡附件）
"""

import sys, os, re, json, hashlib
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ── 環境準備 ─────────────────────────────────────────────────────
def _check_env():
    missing = []
    for key in ['ANTHROPIC_API_KEY']:
        if not os.environ.get(key):
            missing.append(key)
    if missing:
        print(f"[!] 缺少環境變數：{', '.join(missing)}")
        sys.exit(1)


# ── 1. 找商品 ────────────────────────────────────────────────────
def step1_find_products(n_products: int = 10) -> list:
    print("\n" + "="*55)
    print("  STEP 1：搜尋高傭金商品")
    print("="*55)
    from pipeline.commission_finder import find_top_commission_products
    products = find_top_commission_products(top_n=n_products * 2)
    # 去重（按affiliate_keyword每類最多取2篇）
    seen_kw = {}
    selected = []
    for p in products:
        kw = p.get("affiliate_keyword", "")
        if seen_kw.get(kw, 0) < 2:
            selected.append(p)
            seen_kw[kw] = seen_kw.get(kw, 0) + 1
        if len(selected) >= n_products:
            break
    print(f"\n  → 選定 {len(selected)} 件商品")
    return selected


# ── 2. 生成文章 ──────────────────────────────────────────────────
KEYWORD_LABELS = {
    "貓砂": "貓咪日常", "貓糧": "貓咪飲食", "貓零食": "貓咪零食",
    "貓咪罐頭": "貓咪飲食", "貓抓板": "貓咪日常", "貓窩": "貓咪日常",
    "狗糧": "狗狗飲食", "狗零食": "狗狗零食", "狗罐頭": "狗狗飲食",
    "狗狗牽繩": "狗狗用品", "狗窩": "狗狗日常", "梳毛刷": "清潔保養",
    "寵物玩具": "玩具用品", "寵物外出包": "外出用品", "寵物推車": "外出用品",
    "寵物洗毛精": "清潔保養", "寵物保健": "保健食品", "寵物益生菌": "保健食品",
    "寵物碗": "飲食用具", "自動餵食器": "智能用品", "寵物飲水機": "智能用品",
}

KEYWORD_SLUG = {
    "貓砂":"cat-litter", "貓糧":"cat-food", "貓零食":"cat-snack",
    "貓咪罐頭":"cat-can", "貓抓板":"cat-scratcher", "貓窩":"cat-bed",
    "狗糧":"dog-food", "狗零食":"dog-snack", "狗罐頭":"dog-can",
    "狗狗牽繩":"dog-leash", "狗窩":"dog-bed", "寵物玩具":"pet-toy",
    "寵物外出包":"pet-carrier", "寵物推車":"pet-carrier",
    "寵物洗毛精":"pet-shampoo", "梳毛刷":"pet-brush",
    "寵物保健":"pet-health", "寵物益生菌":"pet-health",
    "寵物碗":"pet-bowl", "自動餵食器":"auto-feeder",
    "寵物飲水機":"auto-feeder",
}


def build_article_prompt(product: dict, images: list) -> str:
    name      = product["name"]
    price     = product.get("price", "499")
    rating    = product.get("rating", "4.8")
    kw        = product.get("affiliate_keyword", "寵物用品")
    commission = product.get("commission_rate", 5.0)

    # 圖片說明（讓 Claude 知道有哪些圖）
    img_note = ""
    if images:
        img_note = f"\n商品圖片（你在文章中提到「商品圖如下」時可以提及真實圖片存在即可，圖片路徑：{images[0]}）"

    return f"""你是台灣知名寵物部落客「毛孩研究室」，請用繁體中文寫一篇高品質 SEO 評測文章。

商品資訊：
- 商品名稱：{name}
- 售價：NT${price}
- 買家評分：{rating}/5
- 主要關鍵字：{kw}{img_note}

請直接輸出 HTML（只有 body 內容，不包含 <html><head> 等標籤，不要加 ```html 標記）。

文章結構（依序，不可跳過）：

<h1>吸引人的標題（含關鍵字「{kw}」，加上「評測」或「開箱」，50字以內）</h1>

<p>開場（150字）：從真實飼主痛點切入，建立共鳴，自然帶出商品。</p>

<div class="spec-box">
<h3>商品快速規格</h3>
<table class="spec-table">
<tr><td>商品名稱</td><td>{name}</td></tr>
<tr><td>售價</td><td>NT$ {price}</td></tr>
<tr><td>買家評分</td><td>{rating}/5</td></tr>
<tr><td>適合對象</td><td>（寫入適合的寵物/飼主類型）</td></tr>
<tr><td>主要特色</td><td>（2~3個關鍵特色）</td></tr>
</table>
</div>

<h2>外觀與品質評測</h2>
<p>（180字，描述外觀、材質、包裝、做工，真實飼主觀點）</p>

<h2>實際使用心得</h2>
<p>（220字，毛孩使用反應、實際效果、與其他商品比較，要有具體描述）</p>

<div class="pros-cons">
<div class="pros">
<h3>✅ 優點</h3>
<ul>
<li>（具體優點 1，含數據或具體描述）</li>
<li>（具體優點 2）</li>
<li>（CP值分析，NT${price}買到這些優點划算嗎？）</li>
</ul>
</div>
<div class="cons">
<h3>❌ 缺點或注意事項</h3>
<ul>
<li>（誠實說出缺點 1）</li>
<li>（注意事項 2）</li>
</ul>
</div>
</div>

<h2>適合哪種飼主？</h2>
<p>（120字，具體描述最適合的情境與使用者）</p>

<h2>購買價格分析與推薦</h2>
<p>（120字，與同類商品比較，分析CP值，說明為何值得買）</p>

<h2>常見問題 FAQ</h2>
<h3>（包含「{kw}」的問題，如：{kw}怎麼選才對？）</h3>
<p>（50字具體回答）</p>
<h3>（使用相關問題）？</h3>
<p>（50字具體回答）</p>
<h3>（效果/安全問題）？</h3>
<p>（50字具體回答）</p>

<h2>總結</h2>
<p>（100字結論：推薦指數、適合誰、最後CTA）</p>

格式要求：
- 只輸出 HTML body 內容
- 關鍵字「{kw}」自然出現 7~10 次
- 語氣親切、像真實飼主部落客，不要 AI 感
- 優缺點要具體、誠實
- 不要加任何 markdown 符號（```等）"""


def step2_generate_articles(products: list, articles_per_run: int = 10) -> list:
    print("\n" + "="*55)
    print("  STEP 2：生成 SEO 評測文章")
    print("="*55)
    _check_env()

    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    date_str  = datetime.now().strftime("%Y%m%d")
    ARTICLES_DIR = ROOT / "pipeline" / "output" / "articles"
    DATA_DIR     = ROOT / "pipeline" / "output" / "data"
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    generated = []
    for i, product in enumerate(products[:articles_per_run], 1):
        name     = product["name"]
        price    = product.get("price", "")
        rating   = product.get("rating", "4.8")
        kw       = product.get("affiliate_keyword", "寵物用品")
        aff_link = product.get("affiliate_link",
                   f"https://shopee.tw/search?keyword={quote(name[:25])}")
        img      = product.get("image", "")

        print(f"\n  [{i}/{min(len(products), articles_per_run)}] 生成: {name[:35]}...")
        try:
            prompt = build_article_prompt(product, [img] if img else [])
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2500,
                messages=[{"role": "user", "content": prompt}],
            )
            html_body = msg.content[0].text.strip()
            # 去掉可能的 ```html 包裹
            html_body = re.sub(r'^```html?\s*', '', html_body)
            html_body = re.sub(r'\s*```$', '', html_body)

            # 提取 h1 作為標題
            h1_m = re.search(r'<h1[^>]*>(.*?)</h1>', html_body, re.IGNORECASE | re.DOTALL)
            title = re.sub(r'<[^>]+>', '', h1_m.group(1)).strip() if h1_m else name

            # 存 HTML（加 meta 供 build_article_page 讀）
            safe_nm = re.sub(r'[\\/*?:"<>|]', '', name[:25])
            html_path = ARTICLES_DIR / f"{date_str}_{i:02d}_{safe_nm}.html"
            description = f"{name} 評測推薦，NT${price}，買家評分 {rating}/5"
            html_path.write_text(f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<meta name="description" content="{description}">
</head>
<body>
{html_body}
</body>
</html>""", encoding='utf-8')

            generated.append({
                "title":         title,
                "keyword":       kw,
                "affiliate_url": aff_link,
                "article_link":  f"https://shopee.tw/search?keyword={quote(name[:30])}",
                "price":         price,
                "rating":        rating,
                "html_path":     str(html_path),
                # 傳給 build.py 用
                "product_name":  name,
                "product_image": img,
            })
            print(f"  ✓ {title[:45]}")
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")

    # 存摘要 JSON
    summary_path = DATA_DIR / f"articles_summary_{date_str}.json"
    summary_path.write_text(json.dumps([{
        "title":         a["title"],
        "keyword":       a["keyword"],
        "affiliate_url": a["affiliate_url"],
        "article_link":  a["article_link"],
        "price":         a["price"],
        "rating":        a["rating"],
        "html_path":     f"pipeline/output/articles/{date_str}_{i+1:02d}_*.html",
        "product_name":  a.get("product_name", ""),
        "product_image": a.get("product_image", ""),
    } for i, a in enumerate(generated)], ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"\n  共生成 {len(generated)} 篇 | 摘要：{summary_path.name}")
    return generated


# ── 3. 建站 ─────────────────────────────────────────────────────
def step3_build(generated: list) -> list:
    print("\n" + "="*55)
    print("  STEP 3：套用模板、更新首頁")
    print("="*55)
    import build as B
    B.ARTICLES_DST.mkdir(exist_ok=True)
    with open(ROOT / "article-template.html", encoding='utf-8') as f:
        template = f.read()

    # 讀現有 meta
    meta_path = ROOT / "articles_meta.json"
    all_meta = json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists() else []
    existing  = {a["filename"] for a in all_meta}

    new_meta = []
    for art in generated:
        src = Path(art["html_path"])
        if not src.exists():
            continue
        summary = {
            "keyword":       art["keyword"],
            "price":         art["price"],
            "rating":        art["rating"],
            "affiliate_url": art["affiliate_url"],
            "article_link":  art["article_link"],
            "product_name":  art.get("product_name", ""),
        }
        # product_image 直接傳給 build_article_page 跳過重下載
        if art.get("product_image"):
            # 注入已下載圖片到 summary（build.py 內會優先用）
            summary["_product_imgs_cache"] = [art["product_image"]]

        page_html, meta = B.build_article_page(src, template, summary)
        if meta["filename"] not in existing:
            dst = B.ARTICLES_DST / meta["filename"]
            dst.write_text(page_html, encoding='utf-8')
            all_meta.append(meta)
            existing.add(meta["filename"])
            new_meta.append(meta)
            print(f"  ✓ {meta['title'][:45]}")

    meta_path.write_text(json.dumps(all_meta, ensure_ascii=False, indent=2), encoding='utf-8')
    B.update_index(all_meta)
    B.build_sitemap(all_meta)
    B._inject_related_articles(all_meta)

    print(f"\n  新增 {len(new_meta)} 篇，累積 {len(all_meta)} 篇")
    return all_meta


# ── 4. Git Push ──────────────────────────────────────────────────
def step4_git_push():
    print("\n" + "="*55)
    print("  STEP 4：推送 GitHub Pages")
    print("="*55)
    import subprocess
    date_str = datetime.now().strftime("%Y-%m-%d")
    cmds = [
        ["git", "add", "-A"],
        ["git", "commit", "-m",
         f"auto: 每日發文 {date_str}｜高傭金商品評測 × {date_str}\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"],
        ["git", "push"],
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        print(f"  $ {' '.join(cmd[:3])}: {r.returncode}")
        if r.stdout: print("   ", r.stdout.strip()[:120])
        if r.returncode != 0 and r.stderr:
            print("  STDERR:", r.stderr.strip()[:200])


# ── 5. Email 通知 ────────────────────────────────────────────────
def step5_notify(all_meta: list):
    print("\n" + "="*55)
    print("  STEP 5：寄送 Email 通知")
    print("="*55)
    try:
        from pipeline.notify import send_daily_email
        send_daily_email(all_meta)
    except Exception as e:
        print(f"  [Email] 跳過：{e}")


# ── 主流程 ───────────────────────────────────────────────────────
def main(n_products: int = 10, skip_git: bool = False, skip_email: bool = False):
    print("\n🐾  毛孩研究室 每日自動發文管線")
    print(f"    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    products  = step1_find_products(n_products)
    generated = step2_generate_articles(products, articles_per_run=n_products)

    if not generated:
        print("  [!] 沒有生成任何文章，中止")
        return

    all_meta  = step3_build(generated)

    if not skip_git:
        step4_git_push()
    if not skip_email:
        step5_notify(all_meta)

    print("\n✅  管線完成！")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10, help="文章數量")
    ap.add_argument("--no-git",   action="store_true")
    ap.add_argument("--no-email", action="store_true")
    args = ap.parse_args()
    main(n_products=args.n, skip_git=args.no_git, skip_email=args.no_email)
