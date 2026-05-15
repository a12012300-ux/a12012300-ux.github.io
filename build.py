"""
自動建站腳本
- 讀取 pet-affiliate 生成的文章
- 套用模板，產生正式 HTML 頁面
- 更新首頁文章列表
- 初始化 git 並準備推送到 GitHub Pages
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import re
import json
import hashlib
import glob
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent

# 三平台聯盟連結
try:
    from pipeline.config import (
        SHOPEE_AFFILIATE_LINKS, MOMO_AFFILIATE_LINKS, PCHOME_AFFILIATE_LINKS
    )
except ImportError:
    SHOPEE_AFFILIATE_LINKS = {}
    MOMO_AFFILIATE_LINKS   = {"寵物用品": "https://pinkrose.info/3Qlk7"}
    PCHOME_AFFILIATE_LINKS = {"寵物用品": "https://iorange.biz/3QlkI"}
# 支援兩種來源：本機 pet-affiliate 目錄、或 GitHub Actions 的 pipeline 目錄
_local_src  = Path("D:/AI/pet-affiliate/output/articles")
_cloud_src  = BASE_DIR / "pipeline/output/articles"
ARTICLES_SRC = _local_src if _local_src.exists() else _cloud_src

_local_data  = Path("D:/AI/pet-affiliate/output/data")
_cloud_data  = BASE_DIR / "pipeline/output/data"
SUMMARY_DIR  = _local_data if _local_data.exists() else _cloud_data

ARTICLES_DST = BASE_DIR / "posts"

KEYWORD_LABELS = {
    "貓砂": "貓咪日常", "貓糧": "貓咪飲食", "貓零食": "貓咪零食",
    "貓咪罐頭": "貓咪飲食", "貓抓板": "貓咪日常", "貓窩": "貓咪日常",
    "狗糧": "狗狗飲食", "狗零食": "狗狗零食", "狗罐頭": "狗狗飲食",
    "狗狗牽繩": "狗狗用品", "狗窩": "狗狗日常",
    "寵物玩具": "玩具用品", "寵物外出包": "外出用品",
    "寵物洗毛精": "清潔保養", "寵物保健": "保健食品",
    "寵物碗": "飲食用具", "自動餵食器": "智能用品",
}

# 已驗證的 Unsplash 圖片池（20 張，確保每篇文章圖片不重複）
IMAGE_POOL = [
    "https://images.unsplash.com/photo-1574158622682-e40e69881006?w=800&h=450&fit=crop&q=80",  # 橘貓大眼
    "https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=800&h=450&fit=crop&q=80",  # 黃金獵犬
    "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=800&h=450&fit=crop&q=80",  # 貓咪坐姿
    "https://images.unsplash.com/photo-1552053831-71594a27632d?w=800&h=450&fit=crop&q=80",  # 黃金幼犬
    "https://images.unsplash.com/photo-1450778869180-41d0601e046e?w=800&h=450&fit=crop&q=80",  # 貓狗合照
    "https://images.unsplash.com/photo-1533743983669-94fa5c4338ec?w=800&h=450&fit=crop&q=80",  # 熟睡貓咪
    "https://images.unsplash.com/photo-1477884213360-7e9d7dcc1e48?w=800&h=450&fit=crop&q=80",  # 狗狗戶外
    "https://images.unsplash.com/photo-1495360010541-f48722b34f7d?w=800&h=450&fit=crop&q=80",  # 灰色幼貓
    "https://images.unsplash.com/photo-1537151625747-768eb6cf92b2?w=800&h=450&fit=crop&q=80",  # 小狗趴著
    "https://images.unsplash.com/photo-1425082661705-1834bfd09dca?w=800&h=450&fit=crop&q=80",  # 白貓
    "https://images.unsplash.com/photo-1518791841217-8f162f1912da?w=800&h=450&fit=crop&q=80",  # 貓咪看鏡頭
    "https://images.unsplash.com/photo-1543466835-00a7fe58f43d?w=800&h=450&fit=crop&q=80",  # 虎斑貓
    "https://images.unsplash.com/photo-1561948955-570b270e7c36?w=800&h=450&fit=crop&q=80",  # 貓咪臉部
    "https://images.unsplash.com/photo-1548199973-03cce0bbc87b?w=800&h=450&fit=crop&q=80",  # 兩隻狗
    "https://images.unsplash.com/photo-1517849845537-4d257902454a?w=800&h=450&fit=crop&q=80",  # 柴犬
    "https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?w=800&h=450&fit=crop&q=80",  # 貓咪玩耍
    "https://images.unsplash.com/photo-1592194996308-7b43878e84a6?w=800&h=450&fit=crop&q=80",  # 貓咪床上
    "https://images.unsplash.com/photo-1601979031925-424e53b6caaa?w=800&h=450&fit=crop&q=80",  # 橘貓睡覺
    "https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=800&h=450&fit=crop&q=80",  # 黃金（備用）
    "https://images.unsplash.com/photo-1574158622682-e40e69881006?w=800&h=450&fit=crop&q=80",  # 橘貓（備用）
]

# 依文章標題 hash 選圖，確保同一篇永遠同一張、不同篇盡量不重複
def pick_image(title: str) -> str:
    idx = int(hashlib.md5(title.encode()).hexdigest(), 16) % len(IMAGE_POOL)
    return IMAGE_POOL[idx]

DEFAULT_IMAGE = IMAGE_POOL[0]

# 關鍵字圖片對照（給 index.html card 用，每關鍵字固定一張）
KEYWORD_IMAGES = {kw: IMAGE_POOL[i % len(IMAGE_POOL)] for i, kw in enumerate([
    "貓砂","貓糧","貓零食","貓咪罐頭","貓抓板","貓窩",
    "狗糧","狗零食","狗罐頭","狗狗牽繩","狗窩",
    "寵物玩具","寵物外出包","寵物洗毛精","寵物保健","寵物碗","自動餵食器",
])}

KEYWORD_SLUG = {
    "貓砂":"cat-litter", "貓糧":"cat-food", "貓零食":"cat-snack",
    "貓咪罐頭":"cat-can", "貓抓板":"cat-scratcher", "貓窩":"cat-bed",
    "狗糧":"dog-food", "狗零食":"dog-snack", "狗罐頭":"dog-can",
    "狗狗牽繩":"dog-leash", "狗窩":"dog-bed", "寵物玩具":"pet-toy",
    "寵物外出包":"pet-carrier", "寵物洗毛精":"pet-shampoo",
    "寵物保健":"pet-health", "寵物碗":"pet-bowl", "自動餵食器":"auto-feeder",
}


def extract_title(html: str) -> str:
    m = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    if m:
        return re.sub(r'\s*\|\s*毛孩研究室.*', '', m.group(1)).strip()
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    return "寵物商品評測"


def extract_description(html: str) -> str:
    m = re.search(r'<meta name="description"[^>]*content="([^"]*)"', html, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r'<p[^>]*>(.*?)</p>', html, re.IGNORECASE | re.DOTALL)
    if m:
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        return text[:120] + '...' if len(text) > 120 else text
    return ""


def extract_body(html: str) -> str:
    m = re.search(r'<body[^>]*>(.*?)</body>', html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else html


def calc_read_time(html: str) -> int:
    """估算閱讀時間（分鐘）：中文約 400 字/分鐘"""
    text = re.sub(r'<[^>]+>', '', html)
    char_count = len(text.replace('\n', '').replace(' ', ''))
    return max(1, round(char_count / 400))


def build_article_page(src_path: Path, template: str, summary: dict) -> tuple[str, dict]:
    with open(src_path, encoding='utf-8') as f:
        src_html = f.read()

    title = extract_title(src_html)
    description = extract_description(src_html)
    content = extract_body(src_html)
    keyword = summary.get('keyword', '寵物推薦')
    price = str(summary.get('price', ''))
    rating = str(summary.get('rating', '4.8'))

    # CTA 按鈕連結：三平台各自生成
    from urllib.parse import quote as _quote

    # 蝦皮
    raw_aff = summary.get('affiliate_url', '')
    if raw_aff and ('s.shopee.tw' in raw_aff or 'shopee.tw' in raw_aff):
        shopee_url = raw_aff
    else:
        shopee_url = SHOPEE_AFFILIATE_LINKS.get(keyword,
                     f"https://shopee.tw/search?keyword={_quote(title)}")

    # momo
    if "貓" in keyword:
        momo_url = MOMO_AFFILIATE_LINKS.get("貓咪用品", MOMO_AFFILIATE_LINKS.get("寵物用品","https://pinkrose.info/3Qlk7"))
    elif "狗" in keyword:
        momo_url = MOMO_AFFILIATE_LINKS.get("狗狗用品", MOMO_AFFILIATE_LINKS.get("寵物用品","https://pinkrose.info/3Qlk7"))
    elif "保健" in keyword or "益生菌" in keyword:
        momo_url = MOMO_AFFILIATE_LINKS.get("寵物保健品", MOMO_AFFILIATE_LINKS.get("寵物用品","https://pinkrose.info/3Qlk7"))
    else:
        momo_url = MOMO_AFFILIATE_LINKS.get("寵物用品", "https://pinkrose.info/3Qlk7")

    # PChome
    if "貓" in keyword:
        pchome_url = PCHOME_AFFILIATE_LINKS.get("貓咪用品", PCHOME_AFFILIATE_LINKS.get("寵物用品","https://iorange.biz/3QlkI"))
    elif "狗" in keyword:
        pchome_url = PCHOME_AFFILIATE_LINKS.get("狗狗用品", PCHOME_AFFILIATE_LINKS.get("寵物用品","https://iorange.biz/3QlkI"))
    else:
        pchome_url = PCHOME_AFFILIATE_LINKS.get("寵物用品", "https://iorange.biz/3QlkI")

    affiliate_url = shopee_url  # 保持向後相容

    kw_slug = KEYWORD_SLUG.get(keyword, "pet-product")
    uid = hashlib.md5(title.encode()).hexdigest()[:6]
    filename = f"{kw_slug}-{uid}.html"
    date_str = datetime.now().strftime("%Y-%m-%d")

    image_url = pick_image(title)  # 依標題 hash 選圖，每篇不同
    read_time = calc_read_time(content)

    # GEO：從內文擷取重點摘要句
    sentences = re.findall(r'[^。！？\n]{15,50}[。！？]', re.sub(r'<[^>]+>', '', content))
    summary_points = "".join(f"<li>{s}</li>" for s in sentences[:4]) or "<li>詳細評測內容請見本文</li>"

    # FAQ Schema：從文章擷取 FAQ 區段
    faq_items = re.findall(
        r'<h[23][^>]*>([^<]*\？[^<]*)</h[23]>\s*<p[^>]*>(.*?)</p>',
        content, re.IGNORECASE | re.DOTALL
    )
    if faq_items:
        def safe(s):
            return re.sub(r'<[^>]+>', '', s).strip().replace('"', "'")[:200]
        faq_entries = ",\n".join(
            f'{{"@type":"Question","name":"{safe(q)}","acceptedAnswer":{{"@type":"Answer","text":"{safe(a)}"}}}}'
            for q, a in faq_items[:5]
        )
        faq_schema = f'<script type="application/ld+json">{{\n  "@context":"https://schema.org","@type":"FAQPage","mainEntity":[{faq_entries}]\n}}</script>'
    else:
        faq_schema = ""

    # 星星評分
    try:
        r = float(rating)
    except:
        r = 4.8
    stars = "★" * int(r) + "☆" * (5 - int(r))

    page = template
    page = page.replace('{{TITLE}}', title)
    page = page.replace('{{DESCRIPTION}}', description)
    page = page.replace('{{CONTENT}}', content)
    page = page.replace('{{KEYWORD}}', KEYWORD_LABELS.get(keyword, keyword))
    page = page.replace('{{AFFILIATE_URL}}', affiliate_url)
    page = page.replace('{{SHOPEE_URL}}',  shopee_url)
    page = page.replace('{{MOMO_URL}}',    momo_url)
    page = page.replace('{{PCHOME_URL}}',  pchome_url)
    page = page.replace('{{FILENAME}}', filename)
    page = page.replace('{{DATE}}', date_str)
    page = page.replace('{{SUMMARY_POINTS}}', summary_points)
    page = page.replace('{{IMAGE_URL}}', image_url)
    page = page.replace('{{READ_TIME}}', str(read_time))
    page = page.replace('{{PRICE}}', price)
    page = page.replace('{{RATING}}', rating)
    page = page.replace('{{STARS}}', stars)
    page = page.replace('{{FAQ_SCHEMA}}', faq_schema)

    meta = {
        "title": title,
        "description": description,
        "keyword": keyword,
        "label": KEYWORD_LABELS.get(keyword, keyword),
        "filename": filename,
        "affiliate_url": affiliate_url,
        "image_url": image_url,
        "price": price,
        "rating": rating,
        "read_time": read_time,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    return page, meta


def update_index(articles_meta: list):
    index_path = BASE_DIR / "index.html"
    with open(index_path, encoding='utf-8') as f:
        index_html = f.read()

    cards_html = ""
    for a in sorted(articles_meta, key=lambda x: x['date'], reverse=True):
        img = a.get('image_url') or pick_image(a['title'])
        price = a.get('price', '')
        rating = a.get('rating', '4.8')
        read_time = a.get('read_time', 3)
        try:
            r = float(rating)
        except:
            r = 4.8
        price_html = f'<span class="card-price">NT${price}</span>' if price else ''
        stars = "★" * int(r) + "☆" * (5 - int(r))
        cards_html += f"""
    <div class="card">
      <a href="posts/{a['filename']}" class="card-img-link">
        <img src="{img}" alt="{a['title']}" loading="lazy" class="card-img" onerror="this.onerror=null;this.src='https://images.unsplash.com/photo-1574158622682-e40e69881006?w=800&h=450&fit=crop&q=80'">
      </a>
      <div class="card-body">
        <span class="card-tag">{a['label']}</span>
        <h2><a href="posts/{a['filename']}">{a['title']}</a></h2>
        <p>{a['description'][:75]}...</p>
        <div class="card-meta">
          <span class="stars" title="評分 {rating}/5">{stars} {rating}</span>
          {price_html}
          <span class="read-time">📖 {read_time} 分鐘</span>
        </div>
        <div class="card-footer">
          <a href="posts/{a['filename']}" class="btn-read">閱讀評測 →</a>
          <span class="card-date">{a['date']}</span>
        </div>
      </div>
    </div>"""

    # 用清晰標記替換卡片區域，避免重複疊加
    index_html = re.sub(
        r'<!-- CARDS_START -->.*?<!-- CARDS_END -->',
        '<!-- CARDS_START -->' + cards_html + '\n  <!-- CARDS_END -->',
        index_html, flags=re.DOTALL
    )
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_html)


def run_build():
    ARTICLES_DST.mkdir(exist_ok=True)

    with open(BASE_DIR / "article-template.html", encoding='utf-8') as f:
        template = f.read()

    summary_files = sorted(glob.glob(str(SUMMARY_DIR / "articles_summary_*.json")), reverse=True)
    if not summary_files:
        print("[!] 找不到文章摘要，請先執行 module2_writer.py")
        return

    with open(summary_files[0], encoding='utf-8') as f:
        summaries = json.load(f)

    # 補充摘要裡可能缺少的 price/rating（從 radar JSON 讀取）
    radar_files = sorted(glob.glob(str(SUMMARY_DIR / "radar_*.json")), reverse=True)
    radar_map = {}
    if radar_files:
        with open(radar_files[0], encoding='utf-8') as f:
            radar_data = json.load(f)
        for p in radar_data:
            radar_map[p.get('keyword', '')] = p

    for s in summaries:
        kw = s.get('keyword', '')
        if kw in radar_map:
            if 'price' not in s:
                s['price'] = radar_map[kw].get('price_twd', '')
            if 'rating' not in s:
                s['rating'] = radar_map[kw].get('rating', '4.8')

    src_files = sorted(glob.glob(str(ARTICLES_SRC / "*.html")))

    print(f"\n{'='*50}")
    print(f"  建站中... 共 {len(src_files)} 篇文章")
    print(f"{'='*50}\n")

    all_meta = []
    meta_cache_path = BASE_DIR / "articles_meta.json"

    if meta_cache_path.exists():
        with open(meta_cache_path, encoding='utf-8') as f:
            all_meta = json.load(f)
        existing = {a['filename'] for a in all_meta}
    else:
        existing = set()

    new_count = 0
    for src_path in src_files:
        idx = src_files.index(src_path)
        summary = summaries[idx] if idx < len(summaries) else {}

        page_html, meta = build_article_page(Path(src_path), template, summary)

        if meta['filename'] not in existing:
            dst_path = ARTICLES_DST / meta['filename']
            with open(dst_path, 'w', encoding='utf-8') as f:
                f.write(page_html)
            all_meta.append(meta)
            existing.add(meta['filename'])
            new_count += 1
            print(f"  ✓ {meta['title'][:40]}")

    with open(meta_cache_path, 'w', encoding='utf-8') as f:
        json.dump(all_meta, f, ensure_ascii=False, indent=2)

    update_index(all_meta)
    build_sitemap(all_meta)

    print(f"\n  新增 {new_count} 篇，累積 {len(all_meta)} 篇文章")
    print(f"  首頁已更新：{BASE_DIR / 'index.html'}")
    return all_meta


def build_sitemap(articles_meta: list):
    base_url = "https://a12012300-ux.github.io"
    urls = [f"  <url><loc>{base_url}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>"]
    for a in articles_meta:
        urls.append(f"  <url><loc>{base_url}/posts/{a['filename']}</loc><changefreq>weekly</changefreq><priority>0.8</priority><lastmod>{a['date']}</lastmod></url>")

    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += "\n".join(urls)
    sitemap += "\n</urlset>"

    with open(BASE_DIR / "sitemap.xml", 'w', encoding='utf-8') as f:
        f.write(sitemap)
    print(f"  Sitemap 已更新：{len(articles_meta)} 個 URL")


if __name__ == "__main__":
    run_build()
