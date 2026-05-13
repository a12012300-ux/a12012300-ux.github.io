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
import shutil
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

def build_article_page(src_path: Path, template: str, summary: dict) -> tuple[str, dict]:
    with open(src_path, encoding='utf-8') as f:
        src_html = f.read()

    title = extract_title(src_html)
    description = extract_description(src_html)
    content = extract_body(src_html)
    keyword = summary.get('keyword', '寵物推薦')
    affiliate_url = summary.get('affiliate_url', 'https://shopee.tw')

    page = template
    page = page.replace('{{TITLE}}', title)
    page = page.replace('{{DESCRIPTION}}', description)
    page = page.replace('{{CONTENT}}', content)
    page = page.replace('{{KEYWORD}}', KEYWORD_LABELS.get(keyword, keyword))
    page = page.replace('{{AFFILIATE_URL}}', affiliate_url)

    # 用流水號 + 關鍵字英文對照產生純英數檔名，GitHub Pages 不支援中文 URL
    KEYWORD_SLUG = {
        "貓砂":"cat-litter", "貓糧":"cat-food", "貓零食":"cat-snack",
        "貓咪罐頭":"cat-can", "貓抓板":"cat-scratcher", "貓窩":"cat-bed",
        "狗糧":"dog-food", "狗零食":"dog-snack", "狗罐頭":"dog-can",
        "狗狗牽繩":"dog-leash", "狗窩":"dog-bed", "寵物玩具":"pet-toy",
        "寵物外出包":"pet-carrier", "寵物洗毛精":"pet-shampoo",
        "寵物保健":"pet-health", "寵物碗":"pet-bowl", "自動餵食器":"auto-feeder",
    }
    kw_slug = KEYWORD_SLUG.get(keyword, "pet-product")
    import hashlib
    uid = hashlib.md5(title.encode()).hexdigest()[:6]
    filename = f"{kw_slug}-{uid}.html"

    meta = {
        "title": title,
        "description": description,
        "keyword": keyword,
        "label": KEYWORD_LABELS.get(keyword, keyword),
        "filename": filename,
        "affiliate_url": affiliate_url,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    return page, meta

def update_index(articles_meta: list):
    index_path = BASE_DIR / "index.html"
    with open(index_path, encoding='utf-8') as f:
        index_html = f.read()

    cards_html = ""
    for a in sorted(articles_meta, key=lambda x: x['date'], reverse=True):
        cards_html += f"""
    <div class="card">
      <span class="card-tag">{a['label']}</span>
      <h2>{a['title']}</h2>
      <p>{a['description'][:80]}...</p>
      <div class="card-footer">
        <a href="posts/{a['filename']}">閱讀評測 →</a>
        <span>{a['date']}</span>
      </div>
    </div>"""

    index_html = re.sub(
        r'<!-- 文章卡片由 build\.py 自動生成 -->.*?(?=\s*</div>\s*</div>)',
        '<!-- 文章卡片由 build.py 自動生成 -->' + cards_html,
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

    print(f"\n  新增 {new_count} 篇，累積 {len(all_meta)} 篇文章")
    print(f"  首頁已更新：{BASE_DIR / 'index.html'}")
    return all_meta

if __name__ == "__main__":
    run_build()
