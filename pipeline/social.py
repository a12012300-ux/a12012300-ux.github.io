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
    """生成 Instagram 貼文說明（專業圖文風格，長文版）"""
    title   = article.get("title", "")
    keyword = article.get("keyword", "寵物")
    url     = article.get("post_url", BLOG_BASE_URL)
    aff_url = article.get("affiliate_url", "")
    price   = article.get("price", "")
    rating  = article.get("rating", "4.8")

    try:
        r     = float(rating)
        stars = "⭐" * int(r)
    except:
        stars = "⭐⭐⭐⭐"
        r = 4.8

    pet_zh      = "貓咪" if "貓" in keyword else "狗狗" if "狗" in keyword else "毛孩"
    price_badge = f"💰 NT$ {price}" if price else ""
    try:
        avg = f"NT$ {int(float(price)*1.3):.0f}"
    except:
        avg = "市場均價"

    caption = (
        f"你家{pet_zh}需要嗎？這款超熱賣！👇\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 {title[:40]}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{stars} 買家評分 {rating} / 5\n"
        f"{price_badge}（市場均價 {avg}，現在更划算！）\n\n"
        f"🔍 我的完整實測心得：\n\n"
        f"✅ {pet_zh}接受度極高，幾乎零適應期\n"
        f"✅ 品質遠超同價位水準，做工細緻\n"
        f"✅ 材質安全認證，無刺鼻塑膠味\n"
        f"✅ CP 值爆表，省下 30% 以上\n"
        f"✅ 回購率超高，老客戶都說好\n\n"
        f"⚠️ 需要注意：\n"
        f"❌ 需定期清潔才能維持最佳效果\n"
        f"❌ 少數挑剔{pet_zh}可能需 1-2 週適應\n\n"
        f"💡 我的建議：\n"
        f"如果你本來就在找{keyword}，這款是我目前\n"
        f"最推薦的選擇，CP 值在同類產品裡算最高！\n\n"
        f"🔗 完整圖文評測（含使用細節）：\n"
        f"{url}\n\n"
        f"🛒 蝦皮優惠連結：\n"
        f"{aff_url}\n\n"
        f"你家{pet_zh}用過嗎？留言分享！👇\n\n"
        f"#寵物開箱 #{keyword} #{pet_zh}推薦 #台灣寵物\n"
        f"#{pet_zh}日常 #毛孩好物 #寵物評測 #老實說\n"
        f"#寵物必買 #Purrfectlycute"
    )
    return caption


def build_threads_text(article: dict) -> str:
    """生成 Threads 貼文（深度口語化，像真人飼主分享）"""
    title   = article.get("title", "")
    keyword = article.get("keyword", "寵物")
    url     = article.get("post_url", BLOG_BASE_URL)
    aff_url = article.get("affiliate_url", "")
    price   = article.get("price", "")
    rating  = article.get("rating", "4.8")

    pet_zh = "貓咪" if "貓" in keyword else "狗狗" if "狗" in keyword else "毛孩"
    try:
        avg_price = f"NT$ {int(float(price)*1.3):.0f}"
    except:
        avg_price = "市場均價"

    price_line = f"售價 NT$ {price}（同類均價 {avg_price}，省超多！）" if price else ""

    text = (
        f"你家{pet_zh}最近用什麼{keyword}？\n\n"
        f"我剛幫大家實測完這款，忍不住想分享！\n\n"
        f"【{title[:38]}】\n"
        f"買家評分 {rating}/5 ⭐  {price_line}\n\n"
        f"─────────────────\n"
        f"老實說，這款讓我有點驚喜：\n\n"
        f"✅ {pet_zh}接受度超高\n"
        f"   幾乎是零適應期，當天就愛上了\n\n"
        f"✅ 品質遠超這個價位應有的水準\n"
        f"   拿到手第一眼就覺得值\n\n"
        f"✅ 材質安全，完全無異味\n"
        f"   對嗅覺敏感的{pet_zh}很重要！\n\n"
        f"✅ 定價非常有競爭力\n"
        f"   比同類產品便宜至少 20-30%\n\n"
        f"─────────────────\n"
        f"當然也有要注意的地方：\n\n"
        f"⚠️ 需要定期清潔保養\n"
        f"   懶得維護的話效果會打折\n\n"
        f"⚠️ 少數非常挑剔的{pet_zh}可能要 1-2 週適應\n"
        f"   不要急，慢慢來\n\n"
        f"─────────────────\n"
        f"總評：如果你在找{keyword}，這款是我目前\n"
        f"最推薦的選擇，CP 值真的沒話說！\n\n"
        f"完整圖文評測（有很多使用細節）\n"
        f"👉 {url}\n\n"
        f"蝦皮優惠連結（聯盟折扣）\n"
        f"👉 {aff_url}\n\n"
        f"你家{pet_zh}用過這類{keyword}嗎？效果如何？\n"
        f"歡迎留言分享你的經驗！\n\n"
        f"#寵物開箱 #{keyword} #台灣寵物 #毛孩好物\n"
        f"#{pet_zh}推薦 #寵物評測 #老實說 #Purrfectlycute"
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
        # 優先使用 build.py 生成的社群圖片卡，fallback 用 Unsplash
        social_img = meta.get("social_image_url") or meta.get("image_url") or \
                     "https://images.unsplash.com/photo-1574158622682-e40e69881006?w=800&h=800&fit=crop&q=80"
        articles.append({
            "title":          title,
            "keyword":        s.get("keyword", "寵物"),
            "affiliate_url":  s.get("affiliate_url", ""),
            "price":          s.get("price", ""),
            "rating":         s.get("rating", "4.8"),
            "image_url":      social_img,
            "post_url":       post_url,
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
