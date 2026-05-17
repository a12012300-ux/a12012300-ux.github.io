"""
每日 Email 通知 v2
- 寄送 IG + Threads 完整貼文文字（新長版）
- 附上 1080×1080 圖文卡片 JPEG 附件（每篇一張）
- 附上部落格文章連結清單
"""
import smtplib, os, json, glob, sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GMAIL_USER         = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
BLOG_BASE_URL      = "https://a12012300-ux.github.io"
BASE_DIR           = Path(__file__).parent.parent
SOCIAL_DIR         = BASE_DIR / "posts" / "social"


def _load_articles_meta() -> dict:
    """回傳 title → meta 對照表"""
    meta_path = BASE_DIR / "articles_meta.json"
    if not meta_path.exists():
        return {}
    with open(meta_path, encoding="utf-8") as f:
        data = json.load(f)
    return {m["title"]: m for m in data}


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

    meta_map = _load_articles_meta()
    today = datetime.now().strftime("%Y-%m-%d")

    # ── 從 social.py 取新版貼文產生器 ───────────────────────
    try:
        from pipeline.social import build_ig_caption, build_threads_text, BLOG_BASE_URL as _BU
    except Exception:
        build_ig_caption = build_threads_text = None


def build_dcard_text(article: dict) -> str:
    """生成 Dcard 貼文（口語化、互動感強）"""
    title   = article.get("title", "")
    keyword = article.get("keyword", "寵物")
    post_url = article.get("post_url", BLOG_BASE_URL)
    price   = article.get("price", "")
    rating  = article.get("rating", "4.8")

    # 依關鍵字選開場白
    openers = {
        "貓砂":    "身為貓奴，貓砂問題真的困擾我超久\n試過好幾款，每次都有點失望",
        "貓糧":    "挑食的貓真的讓人頭痛\n換了好幾個牌子才找到這款",
        "狗糧":    "狗狗腸胃敏感讓我試了好幾款飼料\n終於找到這個讓牠穩定的",
        "貓零食":  "我家貓超挑嘴，這款是少數讓牠秒衝過來的\n根本貓界毒品 😂",
        "狗零食":  "訓練狗狗最需要好零食\n這款讓我家毛孩乖乖坐下等",
        "自動餵食器": "上班族養寵物最怕的就是飼料問題\n買了這個之後整個解放",
        "貓咪罐頭": "主食罐選擇太多讓我頭很痛\n後來研究了一輪整理成文章",
        "狗罐頭":  "狗罐頭成分差很多，踩過幾次雷\n這篇把我試過的整理給大家",
        "寵物外出包": "帶毛孩出門一直是個挑戰\n試了幾款外出包之後有些心得",
        "寵物保健": "毛孩保健品真的很多坑\n整理了一下我用過覺得有效的",
        "寵物洗毛精": "洗澡對毛孩來說壓力很大\n找到這款溫和的之後好多了",
    }

    opener = openers.get(keyword, f"最近研究了一下{keyword}，整理了一篇心得")

    price_note = f"價格大概 NT${price}，CP值很高" if price else "價格合理，CP值不錯"

    dcard_text = f"""{opener}

{price_note}，評分 {rating}/5

詳細比較和心得在這：
{post_url}

你們有用過這款嗎？或是有推薦其他的歡迎分享！"""

    return dcard_text

    # ── 組 email 正文 ────────────────────────────────────────
    msg = MIMEMultipart("mixed")
    msg["From"]    = GMAIL_USER
    msg["To"]      = GMAIL_USER
    msg["Subject"] = f"[毛孩研究室] {today} 每日貼文包 — {len(articles)} 篇文章 + Dcard文章 + 圖文卡片"

    divider = "━" * 48

    body_lines = [
        f"🐾 毛孩研究室 每日自動發文包",
        f"日期：{today}  |  今日 {len(articles)} 篇新文章",
        f"",
        f"📖 部落格首頁：{BLOG_BASE_URL}",
        f"",
        divider,
        f"  使用說明",
        divider,
        f"1. 每篇文章有三版貼文：Dcard版 + IG版 + Threads版",
        f"2. Dcard版：直接複製貼到 dcard.tw 寵物版",
        f"3. 對應的圖文卡片 JPEG 在附件（依序標號）",
        f"4. 發 IG 時選圖文卡片 + 貼 IG版文字",
        f"5. 發 Threads 時貼 Threads版文字（可附圖）",
        f"",
    ]

    attached_images = []  # (filename, bytes)

    for idx, a in enumerate(articles[:5], 1):  # 最多 5 篇
        title   = a.get("title", "")
        keyword = a.get("keyword", "寵物")
        aff_url = a.get("affiliate_url", "")
        rating  = a.get("rating", "4.8")
        price   = a.get("price", "")

        # 從 meta 取得文章 URL 和社群卡片路徑
        meta = meta_map.get(title, {})
        filename = meta.get("filename", "")
        post_url = f"{BLOG_BASE_URL}/posts/{filename}" if filename else BLOG_BASE_URL

        # 社群卡片 JPEG
        social_card_fname = None
        social_image_url  = meta.get("social_image_url", "")
        if social_image_url and "/posts/social/" in social_image_url:
            card_name = social_image_url.split("/posts/social/")[-1]
            card_path = SOCIAL_DIR / card_name
            if card_path.exists():
                social_card_fname = card_name
                with open(card_path, "rb") as cf:
                    attached_images.append((f"圖文卡片_{idx:02d}_{keyword}.jpg", cf.read()))

        # 組貼文文字
        article_data = {
            "title":         title,
            "keyword":       keyword,
            "affiliate_url": aff_url,
            "rating":        rating,
            "price":         price,
            "post_url":      post_url,
            "image_url":     social_image_url,
        }

        if build_ig_caption and build_threads_text:
            ig_text      = build_ig_caption(article_data)
            threads_text = build_threads_text(article_data)
        else:
            # 備用短版
            ig_text = threads_text = (
                f"{title}\n評分 {rating}/5  NT${price}\n"
                f"{post_url}\n{aff_url}\n"
                f"#寵物 #{keyword} #台灣寵物 #Purrfectlycute"
            )

        card_note = f"（圖文卡片：附件 圖文卡片_{idx:02d}_{keyword}.jpg）" if social_card_fname else "（圖文卡片未產生）"
        dcard_text = build_dcard_text(article_data)

        body_lines += [
            divider,
            f"  第 {idx} 篇  |  {title[:42]}",
            divider,
            f"文章連結：{post_url}",
            f"圖文卡片：{card_note}",
            f"",
            f"▶ Dcard 版貼文（複製貼上即可）",
            f"  發文位置：dcard.tw → 寵物版 → 發表文章",
            f"  標題建議：{title[:40]}",
            f"─ ─ ─ ─ ─ ─ ─ ─",
            dcard_text,
            f"",
            f"▶ IG 版貼文（發 Instagram 用）",
            f"─ ─ ─ ─ ─ ─ ─ ─",
            ig_text,
            f"",
            f"▶ Threads 版貼文（發 Threads 用）",
            f"─ ─ ─ ─ ─ ─ ─ ─",
            threads_text,
            f"",
        ]

    body_lines += [
        divider,
        f"今日所有文章：",
        "",
    ] + [f"  {i}. {a.get('title', '')}" for i, a in enumerate(articles, 1)] + [
        "",
        f"祝收益節節高升！",
        f"毛孩研究室 自動化系統",
    ]

    body_text = "\n".join(body_lines)
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    # ── 附加圖文卡片 JPEG ────────────────────────────────────
    for img_fname, img_bytes in attached_images:
        img_part = MIMEImage(img_bytes, name=img_fname)
        img_part["Content-Disposition"] = f'attachment; filename="{img_fname}"'
        msg.attach(img_part)
        print(f"  [Email] 附加圖文卡片：{img_fname}")

    # ── 寄出 ─────────────────────────────────────────────────
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            s.send_message(msg)
        print(f"  [Email] 已寄送到 {GMAIL_USER}（含 {len(attached_images)} 張圖文卡片）")
    except Exception as e:
        print(f"  [Email] 寄送失敗：{e}")


if __name__ == "__main__":
    run_notify()
