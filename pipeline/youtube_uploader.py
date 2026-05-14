"""
pipeline/youtube_uploader.py
自動上傳影片到 YouTube 頻道 @Andrewhsieh88
依賴：pip install google-auth google-auth-oauthlib google-api-python-client
首次使用：需先跑 get_refresh_token.py 取得 refresh token
"""
import sys, os, json, glob
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

YOUTUBE_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")


def get_youtube_service():
    """用 refresh token 建立 YouTube API 服務"""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token         = None,
        refresh_token = YOUTUBE_REFRESH_TOKEN,
        token_uri     = "https://oauth2.googleapis.com/token",
        client_id     = YOUTUBE_CLIENT_ID,
        client_secret = YOUTUBE_CLIENT_SECRET,
        scopes        = ["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds)


def upload_video(video_path: str, title: str, description: str, tags: list = None):
    """上傳影片到 YouTube"""
    from googleapiclient.http import MediaFileUpload

    youtube = get_youtube_service()

    body = {
        "snippet": {
            "title":       title[:100],
            "description": description[:5000],
            "tags":        tags or ["寵物", "毛孩研究室", "寵物評測"],
            "categoryId":  "22",        # People & Blogs
            "defaultLanguage": "zh-TW",
        },
        "status": {
            "privacyStatus":       "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)

    print(f"  [YouTube] 上傳中：{title[:50]}")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  [YouTube] 上傳進度：{pct}%")

    video_id = response.get("id", "")
    print(f"  [YouTube] ✓ 上傳成功！https://youtu.be/{video_id}")
    return video_id


def run_youtube_uploader():
    """主函式：上傳今日生成的影片"""
    if not all([YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN]):
        print("  [YouTube] 未設定 YOUTUBE_CLIENT_ID / CLIENT_SECRET / REFRESH_TOKEN，跳過上傳")
        return

    # 讀取今日影片資料
    date_str = datetime.now().strftime("%Y%m%d")
    video_files = sorted(
        glob.glob(f"pipeline/output/videos/{date_str}_*.mp4"), reverse=True
    )

    if not video_files:
        print("  [YouTube] 找不到今日影片，跳過上傳")
        return

    # 讀取文章摘要（取得標題 & 描述）
    summary_files = sorted(
        glob.glob("pipeline/output/data/articles_summary_*.json"), reverse=True
    )
    articles = []
    if summary_files:
        with open(summary_files[0], encoding="utf-8") as f:
            articles = json.load(f)

    for i, video_path in enumerate(video_files[:1]):   # 每天上傳 1 支
        article = articles[i] if i < len(articles) else {}
        keyword = article.get("keyword", "寵物用品")
        name    = article.get("title", "寵物商品評測")
        aff_url = article.get("affiliate_url", "")
        rating  = article.get("rating", "4.8")
        price   = article.get("price", "")

        title = f"【開箱實測】{name[:18]} 值不值得買？老實說！"
        description = "\n".join([
            f"今天幫大家實測「{name[:30]}」！",
            f"評分 {rating}/5，這個價格到底划不划算？",
            "",
            f"🛒 蝦皮優惠購買連結：{aff_url}",
            f"📖 完整評測文章：https://a12012300-ux.github.io",
            "",
            "⏱ 時間章節：",
            "0:00 開場 & 本集內容",
            "0:30 商品基本介紹",
            "1:30 外觀 & 設計",
            "2:30 使用優點",
            "3:30 需要注意的地方",
            "4:30 價格分析 & 購買建議",
            "5:30 總結 & 訂閱",
            "",
            "─────────────────────────",
            "🐾 毛孩研究室 每週更新寵物好物評測",
            "喜歡的話記得點讚 👍 訂閱 🔔 開啟小鈴鐺通知！",
            "",
            f"#{keyword} #寵物推薦 #毛孩研究室 #台灣寵物 #寵物評測 #開箱",
        ])

        tags = [keyword, "寵物推薦", "毛孩研究室", "台灣寵物", "寵物評測",
                "開箱", "寵物用品", "寵物開箱", "寵物好物"]

        try:
            upload_video(video_path, title, description, tags)
        except Exception as e:
            print(f"  [YouTube] 上傳失敗：{e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    run_youtube_uploader()
