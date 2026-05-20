"""
indexnow.py
===========
每次發佈新文章後，自動通知 Bing / Yandex / IndexNow 網路
讓搜尋引擎在幾分鐘內就知道有新內容，大幅加速收錄速度

使用方式：
  python pipeline/indexnow.py          # 提交今天的新文章
  python pipeline/indexnow.py --all    # 提交所有文章（首次使用）
"""
import sys, json, requests, argparse
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from datetime import datetime

ROOT      = Path(__file__).parent.parent
META_PATH = ROOT / "articles_meta.json"
BASE_URL  = "https://a12012300-ux.github.io"
API_KEY   = "31a9d5db80a74f93940abaf6a33011f0"
KEY_LOCATION = f"{BASE_URL}/{API_KEY}.txt"

# IndexNow 支援的搜尋引擎端點（提交一個，其他自動同步）
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"

def submit_urls(urls: list[str]) -> bool:
    """批次提交 URLs 到 IndexNow"""
    if not urls:
        print("  [IndexNow] 沒有需要提交的網址")
        return True

    host = "a12012300-ux.github.io"
    payload = {
        "host": host,
        "key": API_KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls[:10000],  # IndexNow 單次上限 10000
    }

    try:
        resp = requests.post(
            INDEXNOW_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=20,
        )
        if resp.status_code in (200, 202):
            print(f"  [IndexNow] ✓ 成功提交 {len(urls)} 個網址（狀態碼 {resp.status_code}）")
            return True
        else:
            print(f"  [IndexNow] ✗ 提交失敗：{resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  [IndexNow] ✗ 例外：{e}")
        return False


def get_today_urls() -> list[str]:
    """取得今天新發佈的文章 URL + 首頁 + 分類頁"""
    urls = [BASE_URL + "/", BASE_URL + "/feed.xml"]

    # 今日新文章
    if META_PATH.exists():
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        today = datetime.now().strftime("%Y-%m-%d")
        for a in meta:
            if a.get("date", "") == today:
                urls.append(f"{BASE_URL}/posts/{a['filename']}")

    # 分類頁（每次都提交，讓搜尋引擎知道分類頁已更新）
    cat_dir = ROOT / "category"
    if cat_dir.exists():
        for cat_file in sorted(cat_dir.glob("*.html")):
            urls.append(f"{BASE_URL}/category/{cat_file.name}")

    return urls


def get_all_urls() -> list[str]:
    """取得所有 URL（文章 + 分類 + 首頁 + feed）"""
    urls = [BASE_URL + "/", BASE_URL + "/feed.xml"]

    # 所有文章
    if META_PATH.exists():
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        for a in meta:
            urls.append(f"{BASE_URL}/posts/{a['filename']}")

    # 分類頁
    cat_dir = ROOT / "category"
    if cat_dir.exists():
        for cat_file in sorted(cat_dir.glob("*.html")):
            urls.append(f"{BASE_URL}/category/{cat_file.name}")

    return urls


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="提交所有文章（首次使用）")
    args = parser.parse_args()

    if args.all:
        urls = get_all_urls()
        print(f"  [IndexNow] 提交全部 {len(urls)} 個網址...")
    else:
        urls = get_today_urls()
        print(f"  [IndexNow] 提交今日 {len(urls)} 個網址...")

    for u in urls[:8]:
        print(f"    {u}")
    if len(urls) > 8:
        print(f"    ...（共 {len(urls)} 個）")

    submit_urls(urls)
