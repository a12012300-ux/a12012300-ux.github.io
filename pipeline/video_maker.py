"""
pipeline/video_maker.py
自動 YouTube 影片生成器
每天從文章摘要生成 1 支寵物評測影片（約 5-8 分鐘）
依賴：pip install edge-tts moviepy pillow numpy
系統：apt-get install ffmpeg fonts-noto-cjk
"""
import sys, os, json, glob, asyncio, tempfile
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

VIDEOS_DIR   = Path("pipeline/output/videos")
DATA_DIR_PATH = Path("pipeline/output/data")
VOICE        = "zh-TW-HsiaoChenNeural"   # 台灣女聲（免費）
WIDTH, HEIGHT = 1920, 1080
FPS           = 24

# ── 主題配色 ──────────────────────────────────────────────────
THEME = {
    "bg":     (255, 245, 248),
    "grad":   (240, 225, 235),
    "text":   (50,  25,  55),
    "accent": (180, 55, 100),
    "light":  (220, 180, 200),
}


# ── 工具：尋找中文字體 ─────────────────────────────────────────
def find_cjk_font() -> str:
    candidates = [
        # GitHub Actions / Ubuntu
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKtc-Regular.otf",
        # Windows
        "C:/Windows/Fonts/msjh.ttc",
        "C:/Windows/Fonts/mingliu.ttc",
        "C:/Windows/Fonts/kaiu.ttf",
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for p in candidates:
        if Path(p).exists():
            print(f"  [Font] 使用字體：{p}")
            return p
    print("  [Font] 使用預設字體（中文可能無法顯示）")
    return ""


# ── 生成單張投影片 ────────────────────────────────────────────
def make_slide(lines, font_path, title=None, is_title=False, is_end=False):
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    img = Image.new("RGB", (WIDTH, HEIGHT), THEME["bg"])
    draw = ImageDraw.Draw(img)

    # 漸層背景
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(THEME["bg"][0] * (1 - t) + THEME["grad"][0] * t)
        g = int(THEME["bg"][1] * (1 - t) + THEME["grad"][1] * t)
        b = int(THEME["bg"][2] * (1 - t) + THEME["grad"][2] * t)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # 上下裝飾條
    draw.rectangle([0, 0, WIDTH, 12], fill=THEME["accent"])
    draw.rectangle([0, HEIGHT - 12, WIDTH, HEIGHT], fill=THEME["accent"])

    # 側邊裝飾
    draw.rectangle([0, 0, 8, HEIGHT], fill=THEME["light"])

    # 載入字體
    try:
        if font_path:
            big_font  = ImageFont.truetype(font_path, 90)
            title_font = ImageFont.truetype(font_path, 65)
            body_font  = ImageFont.truetype(font_path, 48)
            tag_font   = ImageFont.truetype(font_path, 36)
        else:
            big_font = title_font = body_font = tag_font = ImageFont.load_default()
    except Exception:
        big_font = title_font = body_font = tag_font = ImageFont.load_default()

    # 品牌標籤（右下角）
    brand = "毛孩研究室"
    draw.text((WIDTH - 300, HEIGHT - 60), brand, fill=THEME["accent"], font=tag_font)

    if is_title or is_end:
        # ── 標題 / 結尾投影片 ──
        y_pos = HEIGHT // 3 - 40
        for line in lines:
            try:
                bbox = draw.textbbox((0, 0), line, font=big_font)
                tw = bbox[2] - bbox[0]
            except Exception:
                tw = len(line) * 40
            x = (WIDTH - tw) // 2
            # 陰影
            draw.text((x + 3, y_pos + 3), line, fill=THEME["light"], font=big_font)
            draw.text((x, y_pos), line, fill=THEME["accent"] if is_title else THEME["text"], font=big_font)
            y_pos += 110

    else:
        # ── 內容投影片 ──
        y_pos = 40
        if title:
            draw.text((60, y_pos), title, fill=THEME["accent"], font=title_font)
            y_pos += 100
            draw.rectangle([60, y_pos, WIDTH - 60, y_pos + 4], fill=THEME["light"])
            y_pos += 24

        for line in lines:
            if not line.strip():
                y_pos += 30
                continue
            color = THEME["text"]
            if line.startswith("✅"):
                color = (40, 140, 60)
            elif line.startswith("❌"):
                color = (180, 40, 40)
            elif line.startswith("💰") or line.startswith("👉"):
                color = THEME["accent"]
            draw.text((60, y_pos), line, fill=color, font=body_font)
            y_pos += 72

    return np.array(img)


# ── 生成 TTS 語音 ─────────────────────────────────────────────
async def _tts(text: str, path: str):
    import edge_tts
    com = edge_tts.Communicate(text, VOICE, rate="+8%", pitch="+0Hz")
    await com.save(path)


def tts(text: str, path: str):
    asyncio.run(_tts(text, path))


# ── 建立影片腳本（場景列表） ─────────────────────────────────────
def build_scenes(product: dict) -> list:
    name    = product.get("name", "寵物商品")
    kw      = product.get("keyword", "寵物用品")
    price   = product.get("price_twd", "299")
    rating  = product.get("rating", "4.8")
    sold    = product.get("sold_monthly", "1000")
    aff_url = product.get("affiliate_url", "")

    return [
        {
            "is_title": True,
            "lines": ["【開箱實測】", name[:18], "值不值得買？老實說！"],
            "narration": (
                f"大家好，歡迎來到毛孩研究室！"
                f"今天我要幫大家實測一款超熱門的{kw}，就是「{name[:20]}」。"
                f"這款商品在蝦皮月銷{sold}件，評分高達{rating}分，"
                f"到底好不好用？我今天直接告訴你！"
            ),
        },
        {
            "title": "📦 商品基本資料",
            "lines": [
                f"商品名稱：{name[:24]}",
                f"參考售價：NT$ {price}",
                f"買家評分：{rating} / 5  ⭐⭐⭐⭐⭐",
                f"月銷數量：{sold} 件",
                f"商品分類：{kw}",
            ],
            "narration": (
                f"先來看基本資料。這款{kw}，售價大約新台幣{price}元，"
                f"在蝦皮的評分是{rating}分，而且每個月銷售{sold}件，"
                f"可以說是同類商品裡的暢銷款，很多飼主都在買。"
            ),
        },
        {
            "title": "🔍 外觀 & 設計",
            "lines": [
                "• 包裝專業，質感佳",
                "• 材質通過安全認證，寵物安心用",
                "• 操作直覺，不用看說明書",
                "• 尺寸設計適合多種體型",
                "• 清潔保養非常方便",
            ],
            "narration": (
                f"先聊聊外觀設計。拿到{name[:15]}的第一眼，包裝質感很不錯，"
                f"設計感有到位。材質部分通過相關安全認證，"
                f"對毛孩來說安全無虞。操作非常直覺，"
                f"不需要看說明書就能馬上上手，這點我很喜歡。"
            ),
        },
        {
            "title": "✅ 使用優點",
            "lines": [
                "✅ 品質穩定，耐用度高",
                "✅ 毛孩接受度超高",
                "✅ 這個價格 CP 值爆表",
                "✅ 蝦皮好評如潮，回購率高",
                "✅ 適合長期日常使用",
            ],
            "narration": (
                f"來說說優點，也是我最推薦這款的原因。"
                f"第一，品質非常穩定，用了很長時間都沒有出現問題。"
                f"第二，我家毛孩對這款{kw}接受度超高，反應真的很正面。"
                f"第三，以新台幣{price}元的價格來說，CP值真的是爆表，"
                f"這是我願意回購的最大原因。"
            ),
        },
        {
            "title": "❌ 需要注意的地方",
            "lines": [
                "❌ 需定期清潔，不能偷懶",
                "❌ 部分寵物需要 1-2 週適應期",
                "❌ 選購前請對照寵物體型",
                "→ 第一次使用請循序漸進",
                "→ 有疑問建議諮詢獸醫",
            ],
            "narration": (
                f"當然也有一些需要注意的地方，我直說不幫廠商講話。"
                f"這款{kw}需要定期清潔，才能維持最佳效果，懶得清潔的飼主要注意。"
                f"另外，部分寵物可能需要一到兩週的適應期，"
                f"第一次使用建議循序漸進，不要一下子用太多或太久。"
            ),
        },
        {
            "title": "💰 價格分析 & 購買連結",
            "lines": [
                f"蝦皮現貨售價：NT$ {price}",
                "市場比較：同類商品中偏低",
                "推薦指數：⭐⭐⭐⭐⭐",
                "",
                "👉 購買連結在影片說明欄",
                "🔔 訂閱頻道不錯過好物推薦",
            ],
            "narration": (
                f"最後來說購買建議。這款{name[:15]}，在蝦皮售價約{price}元，"
                f"以這個品質來說非常划算。"
                f"如果你的毛孩也需要{kw}，我非常推薦這款。"
                f"購買連結我放在影片說明欄，"
                f"有蝦皮聯盟優惠連結，點進去可以直接下單，"
                f"幫你省掉自己搜尋的時間。"
            ),
        },
        {
            "is_end": True,
            "lines": ["感謝收看！", "點讚 👍  訂閱 🔔  開通知", "毛孩研究室  週週更新"],
            "narration": (
                f"好了，今天{kw}的評測就到這邊結束！"
                f"如果這部影片對你有幫助，麻煩給我一個讚，"
                f"也記得訂閱頻道開啟小鈴鐺通知，"
                f"我每週都會分享最新的寵物好物評測和開箱，"
                f"讓你不用自己踩雷！我們下週見，掰掰！"
            ),
        },
    ]


# ── 合成完整影片 ──────────────────────────────────────────────
def create_video(product: dict, output_path: str):
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

    font_path = find_cjk_font()
    scenes    = build_scenes(product)
    clips     = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, scene in enumerate(scenes):
            audio_path = f"{tmpdir}/a{i:02d}.mp3"

            # 生成語音
            print(f"    場景 {i+1}/{len(scenes)} TTS...")
            tts(scene["narration"], audio_path)

            # 量測音訊長度
            audio_clip   = AudioFileClip(audio_path)
            duration     = audio_clip.duration + 0.8   # 結尾留白
            audio_clip.close()

            # 生成投影片
            slide = make_slide(
                lines      = scene.get("lines", []),
                font_path  = font_path,
                title      = scene.get("title"),
                is_title   = scene.get("is_title", False),
                is_end     = scene.get("is_end", False),
            )

            # 組合圖 + 音
            img_clip   = ImageClip(slide).set_duration(duration)
            audio      = AudioFileClip(audio_path)
            video_clip = img_clip.set_audio(audio)
            clips.append(video_clip)

        print("    合成影片中...")
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(
            output_path,
            fps          = FPS,
            codec        = "libx264",
            audio_codec  = "aac",
            bitrate      = "2000k",
            verbose      = False,
            logger       = None,
        )
        total = final.duration
        final.close()
        return total


# ── 主函式 ────────────────────────────────────────────────────
def run_video_maker():
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(glob.glob("pipeline/output/data/articles_summary_*.json"), reverse=True)
    if not files:
        print("[Video] 找不到文章摘要，跳過影片生成")
        return []

    with open(files[0], encoding="utf-8") as f:
        articles = json.load(f)

    if not articles:
        print("[Video] 文章列表為空，跳過")
        return []

    date_str  = datetime.now().strftime("%Y%m%d")
    generated = []

    # 每天生成 1 支影片（避免 GitHub Actions 超時）
    article = articles[0]
    product = {
        "name":         article.get("title", "寵物商品評測"),
        "keyword":      article.get("keyword", "寵物用品"),
        "price_twd":    article.get("price", "299"),
        "rating":       article.get("rating", "4.8"),
        "sold_monthly": "1000+",
        "affiliate_url": article.get("affiliate_url", ""),
    }

    output_path = str(VIDEOS_DIR / f"{date_str}_01.mp4")

    print(f"\n{'='*50}")
    print(f"  [Video] 生成影片：{product['name'][:30]}")
    print(f"{'='*50}")

    try:
        duration = create_video(product, output_path)
        print(f"  [Video] ✓ 完成：{output_path}")
        print(f"  [Video] 影片長度：{duration:.0f} 秒（{duration/60:.1f} 分鐘）")
        generated.append({
            "path":    output_path,
            "title":   f"【開箱實測】{product['name'][:20]} 值不值得買？老實說！",
            "keyword": product["keyword"],
            "description": (
                f"今天實測「{product['name'][:30]}」！\n"
                f"評分 {product['rating']}/5，月銷 {product['sold_monthly']} 件。\n\n"
                f"🛒 蝦皮優惠連結：{product['affiliate_url']}\n"
                f"📖 完整評測文章：https://a12012300-ux.github.io\n\n"
                f"#毛孩研究室 #{product['keyword']} #寵物推薦 #台灣寵物 #{product['keyword']}推薦"
            ),
        })
    except Exception as e:
        print(f"  [Video] 失敗：{e}")
        import traceback
        traceback.print_exc()

    return generated


if __name__ == "__main__":
    run_video_maker()
