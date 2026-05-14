"""
社群媒體自動發文模組
支援：Instagram Business API + Threads API
完全自動，每天在 GitHub Actions 觸發，不需人工操作

前置需求：
- Instagram: 需要 IG Business/Creator 帳號 + Facebook Page + Meta Developer App
- Threads: 需要 Threads 帳號 + Threads API 存取權限

環境變數（設定在 GitHub Actions Secrets）：
  IG_USER_ID         - Instagram Business 帳號 ID
  IG_ACCESS_TOKEN    - 長效存取 Token（60天有效）
  THREADS_USER_ID    - Threads 帳號 ID
  THREADS_ACCESS_TOKEN - Threads 存取 Token
"""
import sys, os, json, glob, time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.config import (
    IG_USER_ID, IG_ACCESS_TOKEN,
    THREADS_USER_ID, THREADS_ACCESS_TOKEN,
    SOCIAL_POSTS_PER_DAY, BLOG_BASE_URL,
    DATA_DIR
)

try:
    import requests
except ImportError:
    print("[!] 請安裝 requests：pip install requests")
    sys.exit(1)

# ─── Instagram Graph API ────────────────────────────────────────────────────

IG_API = "https://graph.facebook.com/v19.0"

def ig_create_container(ig_user_id: str, token: str,
                         image_url: str, caption: str) -> str | None:
    """步驟1：建立 Instagram 媒體容器"""
    url = f"{IG_API}/{ig_user_id}/media"
    resp = requests.post(url, data={
        "image_url": image_url,
        "caption": caption,
        "access_token": token,
    }, timeout=30)
    data = resp.json()
    if "id" in data:
        print(f"  [IG] 容器建立成功：{data['id']}")
        return data["id"]
    print(f"  [IG] 容器建立失敗：{data}")
    return None


def ig_publish(ig_user_id: str, token: str, creation_id: str) -> bool:
    """步驟2：發布 Instagram 貼文"""
    url = f"{IG_API}/{ig_user_id}/media_publish"
    resp = requests.post(url, data={
        "creation_id": creation_id,
        "access_token": token,
    }, timeout=30)
    data = resp.json()
    if "id" in data:
        print(f"  [IG] 發布成功！貼文 ID：{data['id']}")
        return True
    print(f"  [IG] 發布失敗：{data}")
    return False


def post_to_instagram(image_url: str, caption: str) -> bool:
    """完整的 Instagram 發文流程"""
    if not IG_USER_ID or not IG_ACCESS_TOKEN:
        print("  [IG] 未設定 IG_USER_ID / IG_ACCESS_TOKEN，跳過")
        return False

    creation_id = ig_create_container(IG_USER_ID, IG_ACCESS_TOKEN, image_url, caption)
    if not creation_id:
        return False

    # Instagram 需要等待媒體處理（建議等 5 秒）
    time.sleep(5)
    return ig_publish(IG_USER_ID, IG_ACCESS_TOKEN, creation_id)


# ─── Threads API ───────────────────────────────────────────────────────────

THREADS_API = "https://graph.threads.net/v1.0"

def threads_create_container(user_id: str, token: str,
                              text: str, image_url: str = None) -> str | None:
    """步驟1：建立 Threads 貼文容器"""
    url = f"{THREADS_API}/{user_id}/threads"
    payload = {
        "access_token": token,
        "text": text,
    }
    if image_url:
        payload["media_type"] = "IMAGE"
        payload["image_url"] = image_url
    else:
        payload["media_type"] = "TEXT"

    resp = requests.post(url, data=payload, timeout=30)
    data = resp.json()
    if "id" in data:
        print(f"  [Threads] 容器建立成功：{data['id']}")
        return data["id"]
    print(f"  [Threads] 容器建立失敗：{data}")
    return None


def threads_publish(user_id: str, token: str, creation_id: str) -> bool:
    """步驟2：發布 Threads 貼文"""
    url = f"{THREADS_API}/{user_id}/threads_publish"
    resp = requests.post(url, data={
        "creation_id": creation_id,
        "access_token": token,
    }, timeout=30)
    data = resp.json()
    if "id" in data:
        print(f"  [Threads] 發布成功！貼文 ID：{data['id']}")
        return True
    print(f"  [Threads] 發布失敗：{data}")
    return False


def post_to_threads(text: str, image_url: str = None) -> bool:
    """完整的 Threads 發文流程"""
    if not THREADS_USER_ID or not THREADS_ACCESS_TOKEN:
        print("  [Threads] 未設定 THREADS_USER_ID / THREADS_ACCESS_TOKEN，跳過")
        return False

    creation_id = threads_create_container(THREADS_USER_ID, THREADS_ACCESS_TOKEN,
                                           text, image_url)
    if not creation_id:
        return False

    time.sleep(3)
    return threads_publish(THREADS_USER_ID, THREADS_ACCESS_TOKEN, creation_id)


# ─── 貼文內容產生器 ──────────────────────────────────────────────────────────

def build_ig_caption(article: dict) -> str:
    """生成 Instagram 圖片貼文說明"""
    title   = article.get("title", "")
    keyword = article.get("keyword", "寵物")
    url     = article.get("post_url", BLOG_BASE_URL)
    price   = article.get("price", "")
    rating  = article.get("rating", "4.8")

    price_text = f"💰 NT${price}" if price else ""
    caption = (
        f"🐾 {title}\n\n"
        f"⭐ 評分 {rating}/5 | {price_text}\n\n"
        f"今天幫大家實測了這款熱門{keyword}！\n"
        f"詳細使用心得、優缺點分析全在部落格 👇\n\n"
        f"🔗 {url}\n\n"
        f"#寵物 #{keyword} #台灣寵物 #寵物推薦 #蝦皮寵物 #毛孩 #毛孩研究室"
    )
    return caption


def build_threads_text(article: dict) -> str:
    """生成 Threads 純文字貼文"""
    title   = article.get("title", "")
    keyword = article.get("keyword", "寵物")
    url     = article.get("post_url", BLOG_BASE_URL)
    aff_url = article.get("affiliate_url", "")
    price   = article.get("price", "")
    rating  = article.get("rating", "4.8")

    price_text = f"NT${price} " if price else ""
    text = (
        f"🐾 {title}\n\n"
        f"剛實測了這款{price_text}{keyword}，評分 {rating}/5 ⭐\n\n"
        f"優點：真的很好用，毛孩超愛！\n"
        f"缺點：初期有點味道，幾天後消散\n\n"
        f"詳細評測 👉 {url}\n"
        f"蝦皮優惠價 👉 {aff_url}\n\n"
        f"#毛孩研究室 #{keyword} #寵物推薦"
    )
    return text


# ─── 讀取今日新文章 ──────────────────────────────────────────────────────────

def get_todays_articles(max_posts: int) -> list:
    """讀取最新的 articles_summary JSON，取今天建立的文章"""
    summary_files = sorted(glob.glob(f"{DATA_DIR}/articles_summary_*.json"), reverse=True)
    if not summary_files:
        print("  [Social] 找不到文章摘要，請先執行 writer.py")
        return []

    with open(summary_files[0], encoding="utf-8") as f:
        summaries = json.load(f)

    # 讀取 articles_meta.json 取得最終發布的 URL
    meta_path = Path(__file__).parent.parent / "articles_meta.json"
    meta_map = {}
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            for m in json.load(f):
                meta_map[m["title"]] = m

    articles = []
    for s in summaries[:max_posts]:
        title = s.get("title", "")
        meta  = meta_map.get(title, {})
        filename = meta.get("filename", "")
        post_url = f"{BLOG_BASE_URL}/posts/{filename}" if filename else BLOG_BASE_URL
        articles.append({
            "title":         title,
            "keyword":       s.get("keyword", "寵物"),
            "affiliate_url": s.get("affiliate_url", ""),
            "price":         s.get("price", ""),
            "rating":        s.get("rating", "4.8"),
            "image_url":     meta.get("image_url", "https://images.unsplash.com/photo-1574158622682-e40e69881006?w=800&h=450&fit=crop&q=80"),
            "post_url":      post_url,
        })
    return articles


# ─── 主流程 ──────────────────────────────────────────────────────────────────

def run_social():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n{'='*50}")
    print(f"  社群自動發文 — {today}")
    print(f"{'='*50}")

    articles = get_todays_articles(SOCIAL_POSTS_PER_DAY)
    if not articles:
        print("  [Social] 無新文章可發布")
        return

    ig_ok      = bool(IG_USER_ID and IG_ACCESS_TOKEN)
    threads_ok = bool(THREADS_USER_ID and THREADS_ACCESS_TOKEN)

    if not ig_ok and not threads_ok:
        print("\n  [Social] ⚠️  尚未設定任何社群帳號 Token")
        print("  請在 GitHub → Settings → Secrets 設定：")
        print("    IG_USER_ID, IG_ACCESS_TOKEN")
        print("    THREADS_USER_ID, THREADS_ACCESS_TOKEN")
        print("\n  設定步驟請參考 README 或 docs/social-setup.md")
        return

    ig_count = threads_count = 0

    for i, article in enumerate(articles, 1):
        print(f"\n  [{i}/{len(articles)}] 發文：{article['title'][:40]}")

        # 每篇文章發文間隔 30 秒，避免觸發 API 限流
        if i > 1:
            time.sleep(30)

        # Threads 發文
        if threads_ok:
            text = build_threads_text(article)
            if post_to_threads(text, article.get("image_url")):
                threads_count += 1

        # Instagram 發文（需要圖片）
        if ig_ok:
            caption = build_ig_caption(article)
            image_url = article.get("image_url", "")
            if image_url:
                if post_to_instagram(image_url, caption):
                    ig_count += 1
            else:
                print("  [IG] 無圖片 URL，跳過")

    print(f"\n  ✅ 完成！Instagram: {ig_count} 篇，Threads: {threads_count} 篇")


if __name__ == "__main__":
    run_social()
