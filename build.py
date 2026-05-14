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
ARTICLES_SRC = Path("D:/AI/pet-affiliate/output/articles")
ARTICLES_DST = BASE_DIR / "posts"
SUMMARY_DIR = Path("D:/AI/pet-affiliate/output/data")

KEYWORD_LABELS = {
    "貓砂": "貓咪日常", "貓糧": "貓咪飲食", "貓零食": "貓咪零食",
    "貓咪罐頭": "貓咪飲食", "貓抓板": "貓咪日常", "貓窩": "貓咪日常",
    "狗糧": "狗狗飲食", "狗零食": "狗狗零食", "狗罐頭": "狗狗飲食",
    "狗狗牽繩": "狗狗用品", "狗窩": "狗狗日常",
    "寵物玩具": "玩具用品", "寵物外出包": "外出用品",
    "寵物洗毛精": "清潔保養", "寵物保健": "保健食品",
    "寵物碗": "飲食用具", "自動餵食器": "智能用品",
}

# Unsplash 免費圖片（依關鍵字分類）
KEYWORD_IMAGES = {
    "貓砂":      "https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?w=800&h=450&fit=crop&auto=format&q=80",
    "貓糧":      "https://images.unsplash.com/photo-1548767797-d8c844163c4a?w=800&h=450&fit=crop&auto=format&q=80",
    "貓零食":    "https://images.unsplash.com/photo-1574158622682-e40e69881006?w=800&h=450&fit=crop&auto=format&q=80",
    "貓咪罐頭":  "https://images.unsplash.com/photo-1574158622682-e40e69881006?w=800&h=450&fit=crop&auto=format&q=80",
    "貓抓板":    "https://images.unsplash.com/photo-1615789591457-74a63395c990?w=800&h=450&fit=crop&auto=format&q=80",
    "貓窩":      "https://images.unsplash.com/photo-1506146332389-18140dc7b2fb?w=800&h=450&fit=crop&auto=format&q=80",
    "狗糧":      "https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=800&h=450&fit=crop&auto=format&q=80",
    "狗零食":    "https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=800&h=450&fit=crop&auto=format&q=80",
    "狗罐頭":    "https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=800&h=450&fit=crop&auto=format&q=80",
    "狗狗牽繩":  "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800&h=450&fit=crop&auto=format&q=80",
    "狗窩":      "https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=800&h=450&fit=crop&auto=format&q=80",
    "寵物玩具":  "https://images.unsplash.com/photo-1526336024174-e58f5cdd8e13?w=800&h=450&fit=crop&auto=format&q=80",
    "寵物外出包": "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=800&h=450&fit=crop&auto=format&q=80",
    "寵物洗毛精": "https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=800&h=450&fit=crop&auto=format&q=80",
    "寵物保健":  "https://images.unsplash.com/photo-1574158622682-e40e69881006?w=800&h=450&fit=crop&auto=format&q=80",
    "寵物碗":    "https://images.unsplash.com/photo-1548767797-d8c844163c4a?w=800&h=450&fit=crop&auto=format&q=80",
    "自動餵食器": "https://images.unsplash.com/photo-1548767797-d8c844163c4a?w=800&h=450&fit=crop&auto=format&q=80",
}
DEFAULT_IMAGE = "https://images.unsplash.com/photo-1574158622682-e40e69881006?w=800&h=450&fit=crop&auto=format&q=80"

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
    affiliate_url = summary.get('affiliate_url', 'https://shopee.tw')
    price = str(summary.get('price', ''))
    rating = str(summary.get('rating', '4.8'))

    kw_slug = KEYWORD_SLUG.get(keyword, "pet-product")
    uid = hashlib.md5(title.encode()).hexdigest()[:6]
    filename = f"{kw_slug}-{uid}.html"
    date_str = datetime.now().strftime("%Y-%m-%d")

    image_url = KEYWORD_IMAGES.get(keyword, DEFAULT_IMAGE)
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
        img = a.get('image_url', DEFAULT_IMAGE)
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
        <img src="{img}" alt="{a['title']}" loading="lazy" class="card-img">
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
