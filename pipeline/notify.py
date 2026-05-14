"""
每日 Email 通知
發送今日新文章摘要 + 現成的 IG/Threads 貼文內容到 Gmail
"""
import smtplib, os, json, glob, sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

GMAIL_USER         = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
BLOG_BASE_URL      = "https://a12012300-ux.github.io"


def run_notify():
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("  [Email] 未設定 Gmail，跳過通知")
        return

    # 讀取今日文章摘要
    files = sorted(glob.glob("pipeline/output/data/articles_summary_*.json"), reverse=True)
    if not files:
        print("  [Email] 找不到文章摘要，跳過通知")
        return

    with open(files[0], encoding="utf-8") as f:
        articles = json.load(f)

    today = datetime.now().strftime("%Y-%m-%d")

    # 組 IG / Threads 貼文內容
    ig_sections = []
    for i, a in enumerate(articles[:3], 1):
        title   = a.get("title", "")
        keyword = a.get("keyword", "寵物")
        aff_url = a.get("affiliate_url", "")
        rating  = a.get("rating", "4.8")
        price   = a.get("price", "")
        price_text = f"NT${price} " if price else ""

        section = "\n".join([
            f"== 貼文 {i} == 複製以下內容貼到 IG / Threads ==",
            f"",
            f"[貼文內容開始]",
            f"",
            f"今天幫大家實測了這款熱門{keyword}！",
            f"{title}",
            f"",
            f"評分 {rating}/5 ⭐  {price_text}",
            f"",
            f"詳細評測 >> {BLOG_BASE_URL}",
            f"蝦皮優惠 >> {aff_url}",
            f"",
            f"#毛孩研究室 #{keyword} #寵物推薦 #台灣寵物 #蝦皮寵物",
            f"",
            f"[貼文內容結束]",
            f"",
        ])
        ig_sections.append(section)

    body = "\n".join([
        f"毛孩研究室 每日自動發文通知",
        f"日期：{today}",
        f"今日共發布 {len(articles)} 篇新文章",
        f"",
        f"部落格：{BLOG_BASE_URL}",
        f"",
        "=" * 45,
        "  今日 IG / Threads 貼文內容",
        "  （直接複製貼上，不用修改）",
        "=" * 45,
        "",
    ] + ig_sections + [
        "=" * 45,
        f"今日所有文章：",
        "",
    ] + [f"- {a.get('title', '')}" for a in articles] + [
        "",
        f"祝收益節節高升！",
        f"毛孩研究室 自動化系統",
    ])

    msg = MIMEMultipart()
    msg["From"]    = GMAIL_USER
    msg["To"]      = GMAIL_USER
    msg["Subject"] = f"[毛孩研究室] {today} 今日發文通知（{len(articles)} 篇）"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            s.send_message(msg)
        print(f"  [Email] 已寄送到 {GMAIL_USER}")
    except Exception as e:
        print(f"  [Email] 寄送失敗：{e}")


if __name__ == "__main__":
    run_notify()
