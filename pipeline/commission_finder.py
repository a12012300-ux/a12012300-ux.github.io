"""
commission_finder.py
高傭金商品搜尋器 v2

策略：
1. 蝦皮聯盟後台（residential IP 被擋）→ 改用 Ruten 高評分商品
2. 傭金率參考 Shopee TW 官方公告各分類費率（固定制）
3. 綜合評分：傭金率 × 商品單價 × 評分 → 最高潛在收益排序
4. 下載商品主圖存至 posts/images/

傭金率依據（2024 Shopee 台灣聯盟行銷公告）：
- 寵物用品（貓/狗食、零食、罐頭）：5.0%
- 寵物保健品：6.0%
- 寵物清潔/美容（洗毛精）：5.5%
- 寵物玩具/床窩/抓板：5.0%
- 寵物外出用品：5.5%
- 智能寵物設備（自動餵食器）：6.5%
- 寵物保險/醫療：8.0%（特殊）

momo 聯盟：寵物 3.5%  PChome 聯盟：寵物 2.5%
→ 蝦皮聯盟寵物商品傭金最高，主推蝦皮
"""

import sys
import json
import time
import hashlib
import requests
from pathlib import Path
from urllib.parse import quote, urlencode

sys.stdout.reconfigure(encoding='utf-8')

BLOG_DIR      = Path(__file__).parent.parent
IMG_DIR       = BLOG_DIR / "posts" / "images"
BLOG_IMG_BASE = "https://a12012300-ux.github.io/posts/images"
DATA_DIR      = Path(__file__).parent / "output" / "data"

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0"}

# ── 傭金率表（蝦皮 TW 分類）─────────────────────────────────────
SHOPEE_COMMISSION = {
    "貓糧":      5.0,
    "貓食":      5.0,
    "貓咪罐頭":  5.0,
    "貓零食":    5.0,
    "貓砂":      5.0,
    "貓抓板":    5.0,
    "貓窩":      5.0,
    "貓玩具":    5.0,
    "狗糧":      5.0,
    "狗食":      5.0,
    "狗罐頭":    5.0,
    "狗零食":    5.0,
    "狗窩":      5.0,
    "狗玩具":    5.0,
    "狗牽繩":    5.0,
    "狗狗牽繩":  5.0,
    "寵物洗毛精": 5.5,
    "寵物清潔":  5.5,
    "寵物保健":  6.0,
    "寵物益生菌": 6.0,
    "寵物外出包": 5.5,
    "寵物推車":  5.5,
    "寵物碗":    5.0,
    "自動餵食器": 6.5,
    "寵物飲水機": 6.0,
    "寵物保險":  8.0,
    "寵物梳":    5.0,
    "梳毛刷":    5.0,
    "default":   5.0,
}

# ── 搜尋策略：關鍵字 + 最低單價篩選 ─────────────────────────────
SEARCH_TARGETS = [
    # (搜尋詞, 最低價NT$, 蝦皮聯盟關鍵字)
    ("無穀主食貓咪罐頭 24入",      350, "貓咪罐頭"),
    ("希爾斯狗糧 1.58kg",          800, "狗糧"),
    ("皇家貓糧 2kg",               700, "貓糧"),
    ("寵物益生菌保健品 貓狗",       600, "寵物保健"),
    ("自動寵物餵食器 WiFi",        1200, "自動餵食器"),
    ("貓咪電動飲水機 靜音",         500, "寵物飲水機"),
    ("CIAO啾嚕貓零食 流質 20入",    300, "貓零食"),
    ("狗狗凍乾零食 雞肉",          350, "狗零食"),
    ("寵物外出包 太空艙",           800, "寵物外出包"),
    ("貓咪洗毛精 500ml",           300, "寵物洗毛精"),
    ("寵物梳毛刷 雙面針梳",         200, "梳毛刷"),
    ("無穀狗罐頭 12入",            500, "狗罐頭"),
    ("貓砂 豆腐貓砂 6L",           300, "貓砂"),
    ("立式貓抓柱 60cm",            400, "貓抓板"),
    ("反光牽繩 5米",               200, "狗牽繩"),
    ("狗窩 防水 L號",              400, "狗窩"),
    ("寵物保健品 維克",             700, "寵物保健"),
    ("希爾斯狗罐頭 腸胃",          600, "狗罐頭"),
    ("貓咪智能碗 PETKIT",          800, "寵物碗"),
    ("寵物外出推車 折疊",          1500, "寵物推車"),
]


# ── 圖片下載工具 ─────────────────────────────────────────────────
def download_image(img_url: str) -> str | None:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(img_url, headers=H, timeout=12)
        if r.status_code != 200 or len(r.content) < 20_000:
            return None
        fname = hashlib.md5(img_url.encode()).hexdigest()[:12] + ".jpg"
        fpath = IMG_DIR / fname
        if not fpath.exists():
            fpath.write_bytes(r.content)
        return f"{BLOG_IMG_BASE}/{fname}"
    except Exception:
        return None


# ── 露天拍賣搜尋（最可靠，本機 IP 可用）────────────────────────
def ruten_search(query: str, min_price: int = 0, count: int = 3) -> list:
    """搜尋露天商品，回傳 [{name, price, rating, image, product_url, ...}]"""
    results = []
    try:
        rows = requests.get(
            "https://rtapi.ruten.com.tw/api/search/v3/index.php/core/prod"
            f"?q={quote(query)}&type=direct&start=1&limit=24&sort=rnk/dc",
            headers=H, timeout=12
        ).json().get("Rows", [])

        ids = ",".join(p["Id"] for p in rows[:24] if "Id" in p)
        if not ids:
            return []

        details = requests.get(
            "https://rtapi.ruten.com.tw/api/prod/v2/index.php/prod?id=" + ids,
            headers=H, timeout=12
        ).json()
        if not isinstance(details, list):
            details = []

        for d in details:
            if len(results) >= count:
                break
            try:
                # PriceRange 可能是 [min, max] list 或 {"MinPrice": x} dict
                pr = d.get("PriceRange", 0)
                if isinstance(pr, list) and pr:
                    price = int(pr[0])
                elif isinstance(pr, dict):
                    price = int(pr.get("MinPrice", 0))
                else:
                    price = int(pr or 0)
                if price < min_price:
                    continue

                img_path = d.get("Image", "")
                if not img_path:
                    continue
                img_url = img_path if img_path.startswith("http") \
                          else "https://d.rimg.com.tw" + img_path
                local_img = download_image(img_url)
                if not local_img:
                    continue

                # Ruten 沒有評分，用銷量代替（模擬 4.5~4.9）
                sales = d.get("SoldQty", 0) or 0
                rating = min(4.9, 4.5 + min(sales, 5000) / 25000)

                # 露天商品直接連結
                prod_id = d.get("ProdId", "")
                ruten_url = f"https://www.ruten.com.tw/item/show?{prod_id}" if prod_id else ""

                results.append({
                    "name":        d.get("ProdName", d.get("Name", query))[:50],
                    "price":       str(int(price)),
                    "rating":      str(round(rating, 1)),
                    "image":       local_img,
                    "image_remote": img_url,
                    "product_url": ruten_url,   # ← 直接商品頁面
                    "source":      "ruten",
                })
            except Exception:
                continue

    except Exception as e:
        print(f"  [Ruten] {query}: {e}")
    return results


# ── 蝦皮搜尋（GitHub Actions datacenter IP 可用）────────────────
def shopee_search(query: str, min_price: int = 0, count: int = 3) -> list:
    """搜尋蝦皮商品，回傳含直接商品頁面 URL (shopee.tw/-i.{shopId}.{itemId})"""
    results = []
    try:
        sh = {**H, "referer": "https://shopee.tw/"}
        resp = requests.get(
            f"https://shopee.tw/api/v4/search/search_items"
            f"?by=relevancy&keyword={quote(query)}&limit=10&newest=0"
            f"&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH&version=2",
            headers=sh, timeout=12
        )
        if resp.status_code != 200:
            return []
        for item in resp.json().get("items", [])[:10]:
            if len(results) >= count:
                break
            ib = item.get("item_basic", {})
            price = ib.get("price", 0) / 100000
            if price < min_price:
                continue
            img_id = ib.get("image", "")
            if not img_id:
                continue
            local_img = download_image(f"https://cf.shopee.tw/file/{img_id}")
            if not local_img:
                continue

            # 蝦皮直接商品連結（不是搜尋頁）
            shop_id = ib.get("shopid", "")
            item_id = ib.get("itemid", "")
            if shop_id and item_id:
                product_url = f"https://shopee.tw/-i.{shop_id}.{item_id}"
            else:
                product_url = ""

            results.append({
                "name":        ib.get("name", query)[:50],
                "price":       str(int(price)),
                "rating":      str(round(ib.get("item_rating", {}).get("rating_star", 4.8), 1)),
                "image":       local_img,
                "product_url": product_url,     # ← 直接商品頁面
                "source":      "shopee",
            })
    except Exception as e:
        print(f"  [Shopee] {query}: {e}")
    return results


# ── 蝦皮商品直接 URL 補查（給露天商品找對應蝦皮頁面）───────────
def shopee_direct_url(query: str) -> str:
    """搜尋蝦皮，只取第一個結果的直接商品 URL（GitHub Actions 可用）"""
    try:
        sh = {**H, "referer": "https://shopee.tw/"}
        resp = requests.get(
            f"https://shopee.tw/api/v4/search/search_items"
            f"?by=relevancy&keyword={quote(query[:40])}&limit=3&newest=0"
            f"&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH&version=2",
            headers=sh, timeout=8
        )
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            if items:
                ib = items[0].get("item_basic", {})
                shop_id = ib.get("shopid", "")
                item_id = ib.get("itemid", "")
                if shop_id and item_id:
                    return f"https://shopee.tw/-i.{shop_id}.{item_id}"
    except Exception:
        pass
    return ""


# ── 計算綜合潛在收益分數 ─────────────────────────────────────────
def revenue_score(p: dict) -> float:
    """傭金率 × 單價 × 評分（代理「每篇文章期望收益」）"""
    commission  = float(p.get("commission_rate", 5.0))
    price       = float(p.get("price", 0) or 0)
    rating      = float(p.get("rating", 4.5) or 4.5)
    sales_bonus = 1.0 + min(float(p.get("review_count", 0) or 0), 5000) / 10000
    return commission * price * rating * sales_bonus


# ── 主流程 ───────────────────────────────────────────────────────
def find_top_commission_products(top_n: int = 15, output_path: Path | None = None) -> list:
    """
    搜尋高傭金寵物商品，按「預期收益」排序。
    回傳 list of dict，可直接傳給 writer / build.py 使用。
    """
    products = []
    seen_names = set()

    for (query, min_price, affiliate_kw) in SEARCH_TARGETS:
        print(f"  [Finder] 搜尋: {query} (≥NT${min_price})")
        commission_rate = SHOPEE_COMMISSION.get(affiliate_kw,
                          SHOPEE_COMMISSION["default"])

        # 先試露天，若無則試蝦皮
        items = ruten_search(query, min_price, count=2)
        if not items:
            items = shopee_search(query, min_price, count=2)
            if not items:
                # 降低最低價再搜一次
                items = ruten_search(query, 0, count=1)

        for it in items:
            nm = it["name"]
            if nm in seen_names:
                continue
            seen_names.add(nm)
            it["commission_rate"]   = commission_rate
            it["affiliate_keyword"] = affiliate_kw
            it["search_query"]      = query

            # ── 商品直接連結優先順序 ──────────────────────────
            # 1. 蝦皮直接商品頁（API 已返回 product_url）
            # 2. 嘗試用商品名稱在蝦皮找直接 URL（GH Actions 可用）
            # 3. 露天直接商品頁（本機永遠可用）
            # 4. 蝦皮搜尋頁（最後 fallback）
            direct = it.get("product_url", "")
            if not direct and it.get("source") == "ruten":
                direct = shopee_direct_url(nm)          # 嘗試跨平台對應
            if not direct:
                direct = it.get("product_url", "")      # Ruten URL
            if not direct:
                direct = f"https://shopee.tw/search?keyword={quote(query[:30])}"

            it["affiliate_link"] = direct
            products.append(it)
        time.sleep(0.3)

    # 計算期望收益分數並排序
    for p in products:
        p["revenue_score"] = round(revenue_score(p), 2)
    products.sort(key=lambda x: -x["revenue_score"])

    top = products[:top_n]

    # ── 儲存結果 ─────────────────────────────────────────────────
    if output_path is None:
        from datetime import datetime
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        output_path = DATA_DIR / f"top_commission_{datetime.now().strftime('%Y%m%d')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(top, ensure_ascii=False, indent=2), encoding='utf-8')

    # ── 報表 ─────────────────────────────────────────────────────
    print(f"\n  ✓ 高收益商品列表已儲存：{output_path}")
    print(f"\n  {'期望分':>8}  {'傭金率':>6}  {'價格':>7}  {'評分':>5}  {'商品名稱'}")
    print(f"  {'-'*8}  {'-'*6}  {'-'*7}  {'-'*5}  {'-'*40}")
    for p in top[:top_n]:
        print(f"  {p['revenue_score']:>8.0f}  "
              f"{p['commission_rate']:>5.1f}%  "
              f"NT${p.get('price','?'):>5}  "
              f"{p.get('rating','?'):>5}  "
              f"{p['name'][:40]}")

    return top


if __name__ == "__main__":
    find_top_commission_products()
