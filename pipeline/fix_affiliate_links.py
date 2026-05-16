"""
fix_affiliate_links.py
=======================
在 GitHub Actions datacenter IP 環境執行（蝦皮 API 可用）：
- 掃描所有文章，找出 affiliate_url 仍是搜尋頁（search?keyword）的
- 用蝦皮 API 搜尋對應商品，取得 shop_id + item_id
- 更新為直接商品頁面 URL：https://shopee.tw/-i.{shopId}.{itemId}
- 同時更新 HTML 檔案裡的所有連結 + articles_meta.json

本機執行：蝦皮 API 403，會跳過（不影響功能）
GitHub Actions 執行：蝦皮 API 可用，會完整修復
"""

import sys, json, re, time, requests
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, parse_qs

ROOT     = Path(__file__).parent.parent
META_PATH = ROOT / "articles_meta.json"
POSTS_DIR = ROOT / "posts"

H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
    "referer":    "https://shopee.tw/",
}


def shopee_direct_url(query: str) -> str:
    """搜尋蝦皮，取第一個結果的直接商品 URL。403 時回傳空字串。"""
    try:
        resp = requests.get(
            "https://shopee.tw/api/v4/search/search_items"
            f"?by=relevancy&keyword={quote(query[:40])}&limit=3&newest=0"
            "&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH&version=2",
            headers=H, timeout=10
        )
        if resp.status_code != 200:
            return ""
        items = resp.json().get("items", [])
        if not items:
            return ""
        ib      = items[0].get("item_basic", {})
        shop_id = ib.get("shopid", "")
        item_id = ib.get("itemid", "")
        if shop_id and item_id:
            return f"https://shopee.tw/-i.{shop_id}.{item_id}"
    except Exception:
        pass
    return ""


def update_links_in_html(html: str, old_url: str, new_url: str) -> str:
    """把 HTML 裡所有出現 old_url 的地方換成 new_url"""
    return html.replace(old_url, new_url)


def run_fix():
    if not META_PATH.exists():
        print("  [Fix] articles_meta.json 不存在，跳過")
        return

    meta = json.loads(META_PATH.read_text(encoding='utf-8'))
    broken = [a for a in meta if "search?keyword" in a.get("affiliate_url", "")]
    print(f"  [Fix] 找到 {len(broken)} 篇需要修正的文章")

    if not broken:
        return

    # 測試蝦皮 API 是否可用
    test = shopee_direct_url("貓糧")
    if not test:
        print("  [Fix] 蝦皮 API 不可用（居家 IP 403），跳過")
        return

    print("  [Fix] 蝦皮 API 可用，開始修正連結...")
    fixed = 0

    for a in meta:
        old_url = a.get("affiliate_url", "")
        if "search?keyword" not in old_url:
            continue

        # 取乾淨的商品名稱
        pname = a.get("product_name", "")
        if not pname or len(pname) > 40 or "評測" in pname or "推薦" in pname:
            # product_name 是文章標題，不是商品名，嘗試從 URL 解碼
            qs = parse_qs(urlparse(old_url).query)
            pname = unquote(qs.get("keyword", [""])[0])
        if not pname:
            continue

        new_url = shopee_direct_url(pname)
        if not new_url:
            continue

        # 更新 meta
        a["affiliate_url"] = new_url

        # 更新 HTML 檔案
        post_path = POSTS_DIR / a["filename"]
        if post_path.exists():
            html = post_path.read_text(encoding='utf-8')
            # 替換所有搜尋 URL（encoded 和原始格式）
            updated = update_links_in_html(html, old_url, new_url)
            # 也替換 HTML-encoded 版本
            old_encoded = old_url.replace("&", "&amp;")
            new_encoded = new_url.replace("&", "&amp;")
            updated = update_links_in_html(updated, old_encoded, new_encoded)
            if updated != html:
                post_path.write_text(updated, encoding='utf-8')

        fixed += 1
        print(f"  ✓ {a['title'][:40]}")
        print(f"    {old_url[:60]} →")
        print(f"    {new_url}")
        time.sleep(0.2)

    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n  [Fix] 修正完成：{fixed} 篇")


if __name__ == "__main__":
    run_fix()
