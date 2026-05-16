"""
fix_affiliate_links.py  ──  全面修正版
======================================
在 GitHub Actions datacenter IP 環境執行（蝦皮 API 可用）：

策略：
  1. 解析所有文章的 affiliate_url：
     - s.shopee.tw/XXXXX    → 跟隨 301 redirect → 取 keyword 參數 → Shopee 搜尋
     - shopee.tw/search?keyword=XXX  → 直接解碼 keyword → Shopee 搜尋
     - shopee.tw/-i.{shopId}.{itemId}  → 已是直接商品頁，跳過
     - ruten.com.tw/item/show?...       → 露天直接商品頁，跳過
  2. 用 Shopee API 搜尋 keyword → 取 shopId + itemId → 建立直接 URL
  3. 去重：同一個舊 URL 只搜尋一次，批量替換所有使用它的文章
  4. 更新 articles_meta.json 及對應 HTML 檔案

本機執行：蝦皮 API 403，會跳過（不影響功能）
GitHub Actions 執行：蝦皮 API 可用，會完整修復
"""

import sys, json, re, time, requests
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, parse_qs

ROOT      = Path(__file__).parent.parent
META_PATH = ROOT / "articles_meta.json"
POSTS_DIR = ROOT / "posts"

H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "referer": "https://shopee.tw/",
}


# ── 工具函數 ──────────────────────────────────────────────────────────────────

def resolve_short_link(url: str) -> str:
    """
    跟隨 s.shopee.tw 短連結，回傳最終 URL（不跟隨全部，只取第一個 301）。
    失敗回傳原始 url。
    """
    try:
        r = requests.head(url, headers=H, timeout=8, allow_redirects=False)
        loc = r.headers.get("Location", "")
        if loc:
            return loc
    except Exception:
        pass
    # HEAD 可能被封，用 GET 但設 stream=True 不下載 body
    try:
        r = requests.get(url, headers=H, timeout=8, allow_redirects=False,
                         stream=True)
        r.close()
        loc = r.headers.get("Location", "")
        if loc:
            return loc
    except Exception:
        pass
    return url


def extract_keyword(url: str) -> str:
    """
    從 shopee.tw/search?keyword=XXX 或 s.shopee.tw 短連結中取關鍵字。
    回傳 decoded 字串，失敗回傳空字串。
    """
    parsed = urlparse(url)

    # 已是直接商品頁 shopee.tw/-i.xxx.xxx
    if re.match(r"^/-i\.\d+\.\d+$", parsed.path):
        return ""

    # 搜尋頁 keyword 參數
    qs = parse_qs(parsed.query)
    kw = qs.get("keyword", [""])[0]
    return unquote(kw).strip()


def shopee_direct_url(query: str) -> str:
    """
    搜尋蝦皮，取第一個結果的直接商品 URL。
    403（居家 IP）回傳空字串。
    """
    if not query:
        return ""
    try:
        resp = requests.get(
            "https://shopee.tw/api/v4/search/search_items"
            f"?by=relevancy&keyword={quote(query[:40])}&limit=3&newest=0"
            "&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH&version=2",
            headers=H, timeout=12
        )
        if resp.status_code != 200:
            print(f"    [Shopee] status={resp.status_code} → 跳過")
            return ""
        items = resp.json().get("items", [])
        if not items:
            return ""
        ib      = items[0].get("item_basic", {})
        shop_id = ib.get("shopid", "")
        item_id = ib.get("itemid", "")
        if shop_id and item_id:
            return f"https://shopee.tw/-i.{shop_id}.{item_id}"
    except Exception as e:
        print(f"    [Shopee] 例外: {e}")
    return ""


def needs_fix(url: str) -> bool:
    """判斷 affiliate_url 是否需要修正（不是直接商品頁）。"""
    if not url:
        return False
    # 已是蝦皮直接商品頁
    if re.search(r"shopee\.tw/-i\.\d+\.\d+", url):
        return False
    # 露天直接商品頁
    if "ruten.com.tw/item/show" in url:
        return False
    # 短連結或搜尋頁 → 需要修正
    return True


def update_html(html: str, old_url: str, new_url: str) -> str:
    """把 HTML 裡所有出現 old_url 的地方換成 new_url（含 HTML-encoded 版本）。"""
    html = html.replace(old_url, new_url)
    html = html.replace(old_url.replace("&", "&amp;"),
                        new_url.replace("&", "&amp;"))
    return html


# ── 主流程 ────────────────────────────────────────────────────────────────────

def run_fix():
    if not META_PATH.exists():
        print("  [Fix] articles_meta.json 不存在，跳過")
        return

    meta = json.loads(META_PATH.read_text(encoding='utf-8'))

    # 找出所有需要修正的文章
    to_fix = [a for a in meta if needs_fix(a.get("affiliate_url", ""))]
    print(f"  [Fix] 共 {len(meta)} 篇文章，需修正: {len(to_fix)} 篇")

    if not to_fix:
        print("  [Fix] 全部已是直接商品頁，無需修正 ✓")
        return

    # 先測試蝦皮 API 是否可用
    test = shopee_direct_url("貓糧")
    if not test:
        print("  [Fix] 蝦皮 API 不可用（居家 IP 403），跳過")
        return

    print("  [Fix] 蝦皮 API 可用，開始全面修正...\n")

    # ── 步驟1：為每個不重複的舊 URL 解析關鍵字並查詢新 URL ────────────────
    unique_old_urls = list({a["affiliate_url"] for a in to_fix})
    url_map: dict[str, str] = {}   # old_url → new direct URL

    for old_url in unique_old_urls:
        print(f"  處理: {old_url[:70]}")

        # s.shopee.tw 短連結 → 解析 redirect 取 keyword
        if "s.shopee.tw" in old_url:
            resolved = resolve_short_link(old_url)
            print(f"    → redirect: {resolved[:70]}")
            kw = extract_keyword(resolved)
        else:
            kw = extract_keyword(old_url)

        print(f"    → keyword: {kw!r}")
        if not kw:
            print("    → 無法取得關鍵字，跳過")
            continue

        new_url = shopee_direct_url(kw)
        if new_url:
            url_map[old_url] = new_url
            print(f"    ✓ {new_url}")
        else:
            print(f"    ✗ Shopee 搜尋無結果")

        time.sleep(0.3)   # 避免速率限制

    print(f"\n  [Fix] 成功解析 {len(url_map)}/{len(unique_old_urls)} 個舊連結\n")

    if not url_map:
        print("  [Fix] 沒有可更新的連結，結束")
        return

    # ── 步驟2：批量更新 meta + HTML ──────────────────────────────────────────
    fixed_count = 0
    for a in meta:
        old_url = a.get("affiliate_url", "")
        if old_url not in url_map:
            continue

        new_url = url_map[old_url]
        a["affiliate_url"] = new_url

        # 更新對應的 HTML 檔案
        post_path = POSTS_DIR / a["filename"]
        if post_path.exists():
            html = post_path.read_text(encoding='utf-8')
            updated = update_html(html, old_url, new_url)
            if updated != html:
                post_path.write_text(updated, encoding='utf-8')

        fixed_count += 1
        title_short = a["title"][:45]
        print(f"  ✓ [{fixed_count}] {title_short}")
        print(f"      {old_url[:55]} →")
        print(f"      {new_url}")

    # ── 步驟3：儲存 meta ─────────────────────────────────────────────────────
    META_PATH.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    # ── 結果報告 ─────────────────────────────────────────────────────────────
    remaining = sum(1 for a in meta if needs_fix(a.get("affiliate_url", "")))
    print(f"\n  [Fix] 完成！修正 {fixed_count} 篇，剩餘需修正: {remaining} 篇")
    if remaining:
        print("  [Fix] 以下文章無法自動修正（搜尋無結果）：")
        for a in meta:
            if needs_fix(a.get("affiliate_url", "")):
                print(f"    - {a['title'][:50]}  |  {a['affiliate_url'][:55]}")


if __name__ == "__main__":
    run_fix()
