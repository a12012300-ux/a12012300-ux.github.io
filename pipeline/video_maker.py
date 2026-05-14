"""
pipeline/video_maker.py  v2
高品質 YouTube 寵物評測影片自動生成器
改進：真實商品圖片 + Ken Burns 鏡頭效果 + 淡入淡出轉場
"""
import sys, os, json, glob, asyncio, tempfile, io
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

VIDEOS_DIR    = Path("pipeline/output/videos")
DATA_DIR_PATH = Path("pipeline/output/data")
VOICE         = "zh-TW-HsiaoChenNeural"
WIDTH, HEIGHT = 1920, 1080
FPS           = 24

# ── 中文關鍵字 → 英文圖片搜尋詞 ──────────────────────────────
KW_MAP = {
    "貓糧":"cat food","貓罐頭":"canned cat food","貓砂":"cat litter",
    "貓抓板":"cat scratcher","貓咪玩具":"cat toy","貓床":"cat bed",
    "狗糧":"dog food","狗罐頭":"canned dog food","狗零食":"dog treats",
    "狗玩具":"dog toy","狗牽繩":"dog leash","狗床":"dog bed",
    "寵物碗":"pet bowl","寵物外出包":"pet carrier bag",
    "自動餵食器":"automatic pet feeder","除毛梳":"pet grooming brush",
    "指甲剪":"pet nail clipper","益生菌":"pet probiotics",
    "保健品":"pet supplement","洗毛精":"pet shampoo",
    "貓":"cat","狗":"dog","寵物":"cute pet",
}

def kw_to_en(keyword):
    for zh, en in KW_MAP.items():
        if zh in keyword:
            return en
    return "cute pet"


# ── 圖片抓取 ─────────────────────────────────────────────────
def fetch_shopee_image(keyword: str) -> bytes | None:
    try:
        import requests
        from urllib.parse import quote
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
            "referer": "https://shopee.tw/",
            "If-None-Match-": "",
        }
        url = (
            f"https://shopee.tw/api/v4/search/search_items"
            f"?by=relevancy&keyword={quote(keyword)}&limit=3&newest=0"
            f"&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH&version=2"
        )
        r = requests.get(url, headers=headers, timeout=12)
        items = r.json().get("items", [])
        for item in items[:3]:
            image_id = item.get("item_basic", {}).get("image", "")
            if not image_id:
                continue
            img_url = f"https://cf.shopee.tw/file/{image_id}"
            ir = requests.get(img_url, headers=headers, timeout=10)
            if ir.status_code == 200 and len(ir.content) > 5000:
                return ir.content
    except Exception as e:
        print(f"  [Img] Shopee failed: {e}")
    return None


def fetch_unsplash_image(keyword: str) -> bytes | None:
    try:
        import requests
        en = kw_to_en(keyword)
        url = f"https://source.unsplash.com/1920x1080/?{en}"
        r = requests.get(url, timeout=15, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 20000:
            return r.content
    except Exception as e:
        print(f"  [Img] Unsplash failed: {e}")
    return None


def fetch_image(keyword: str, name: str = "") -> bytes | None:
    """嘗試蝦皮 → Unsplash → None"""
    if name:
        img = fetch_shopee_image(name[:30])
        if img:
            print(f"  [Img] 蝦皮商品圖 OK")
            return img
    img = fetch_shopee_image(keyword)
    if img:
        print(f"  [Img] 蝦皮關鍵字圖 OK")
        return img
    img = fetch_unsplash_image(keyword)
    if img:
        print(f"  [Img] Unsplash 圖 OK")
        return img
    print(f"  [Img] 使用漸層備用背景")
    return None


# ── 背景圖處理 ─────────────────────────────────────────────────
def process_bg(img_bytes: bytes, blur: int = 12, dark: float = 0.60) -> "np.ndarray":
    from PIL import Image, ImageFilter
    import numpy as np
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    # 等比縮放填滿 1920x1080
    iw, ih = img.size
    if iw / ih > WIDTH / HEIGHT:
        nh = HEIGHT; nw = int(iw * HEIGHT / ih)
    else:
        nw = WIDTH; nh = int(ih * WIDTH / iw)
    img = img.resize((nw, nh), Image.LANCZOS)
    x0 = (nw - WIDTH) // 2; y0 = (nh - HEIGHT) // 2
    img = img.crop((x0, y0, x0 + WIDTH, y0 + HEIGHT))
    # 模糊
    img = img.filter(ImageFilter.GaussianBlur(radius=blur))
    # 變暗
    black = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    img = Image.blend(img, black, alpha=dark)
    return np.array(img)


def process_product_img(img_bytes: bytes, size: int = 520) -> "np.ndarray":
    from PIL import Image, ImageOps
    import numpy as np
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img = ImageOps.fit(img, (size, size), Image.LANCZOS)
    return np.array(img)


def gradient_bg() -> "np.ndarray":
    """備用純漸層背景"""
    from PIL import Image, ImageDraw
    import numpy as np
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(15 + 25 * t); g = int(10 + 20 * t); b = int(35 + 45 * t)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))
    return np.array(img)


# ── 字體 ─────────────────────────────────────────────────────
def find_cjk_font() -> str:
    for p in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKtc-Regular.otf",
        "C:/Windows/Fonts/msjh.ttc",
        "C:/Windows/Fonts/mingliu.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]:
        if Path(p).exists():
            print(f"  [Font] {p}")
            return p
    return ""


# ── 投影片繪製 ────────────────────────────────────────────────
def make_slide(
    bg_bytes, product_bytes, lines, font_path,
    title=None, is_title=False, is_end=False
):
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    # 背景
    bg_arr = process_bg(bg_bytes) if bg_bytes else gradient_bg()
    img = Image.fromarray(bg_arr)
    draw = ImageDraw.Draw(img)

    # 字體
    try:
        if font_path:
            f_huge  = ImageFont.truetype(font_path, 88)
            f_title = ImageFont.truetype(font_path, 60)
            f_body  = ImageFont.truetype(font_path, 46)
            f_tag   = ImageFont.truetype(font_path, 30)
        else:
            f_huge = f_title = f_body = f_tag = ImageFont.load_default()
    except Exception:
        f_huge = f_title = f_body = f_tag = ImageFont.load_default()

    # 頻道浮水印（右下）
    draw.text((WIDTH - 30, HEIGHT - 20), "Purrfectly cute",
              fill=(255, 255, 255), font=f_tag, anchor="rb")

    # ── 標題 / 結尾畫面 ─────────────────────────────────────
    if is_title or is_end:
        # 中間暗色漸層帶
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        for y in range(250, 750):
            alpha = int(180 * (1 - abs((y - 500) / 250)))
            ov_draw.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, alpha))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        y_pos = HEIGHT // 2 - 110
        for i, line in enumerate(lines):
            font = f_huge if i == 0 else f_title
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                tw = bbox[2] - bbox[0]
            except Exception:
                tw = len(line) * 42
            x = (WIDTH - tw) // 2
            draw.text((x + 3, y_pos + 3), line, fill=(0, 0, 0), font=font)
            color = (255, 220, 80) if i == 0 else (255, 255, 255)
            draw.text((x, y_pos), line, fill=color, font=font)
            y_pos += 105

    # ── 內容畫面 ─────────────────────────────────────────────
    else:
        # 左側半透明文字區
        text_w = int(WIDTH * 0.60) if product_bytes else WIDTH - 80
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        ov_draw.rectangle([0, 0, text_w + 40, HEIGHT], fill=(0, 0, 0, 155))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        # 商品圖（右側）
        if product_bytes:
            try:
                prod_arr = process_product_img(product_bytes, size=480)
                prod_img = Image.fromarray(prod_arr)
                # 白色圓角背景
                bg_white = Image.new("RGB", (500, 500), (255, 255, 255))
                px = WIDTH - 560; py = (HEIGHT - 500) // 2
                img.paste(bg_white, (px - 10, py - 10))
                img.paste(prod_img, (px, py))
                draw = ImageDraw.Draw(img)
            except Exception:
                pass

        # 標題列（金色）
        y_pos = 50
        if title:
            # 底色條
            try:
                bbox = draw.textbbox((0, 0), title, font=f_title)
                th = bbox[3] - bbox[1]
            except Exception:
                th = 62
            draw.rectangle([0, y_pos - 12, text_w + 40, y_pos + th + 16],
                           fill=(180, 130, 0))
            draw.text((55, y_pos), title, fill=(255, 255, 255), font=f_title)
            y_pos += th + 50

        # 內容行
        for line in lines:
            if not line.strip():
                y_pos += 22; continue
            if line.startswith("✅"):
                color = (80, 255, 140)
            elif line.startswith("❌"):
                color = (255, 100, 100)
            elif line.startswith(("💰", "👉", "🔔")):
                color = (255, 215, 60)
            else:
                color = (240, 240, 240)
            draw.text((56, y_pos + 2), line, fill=(0, 0, 0), font=f_body)
            draw.text((55, y_pos), line, fill=color, font=f_body)
            y_pos += 68

    return np.array(img)


# ── Ken Burns 效果 ────────────────────────────────────────────
def kenburns_clip(frame_array, duration, zoom_start=1.0, zoom_end=1.07):
    """緩慢推拉鏡頭效果，讓靜態圖片產生動態感"""
    from PIL import Image
    from moviepy.editor import VideoClip
    import numpy as np

    pil = Image.fromarray(frame_array)
    w, h = pil.size

    def make_frame(t):
        p = t / duration
        p = p * p * (3 - 2 * p)          # ease in-out
        zoom = zoom_start + (zoom_end - zoom_start) * p
        nw = int(w * zoom); nh = int(h * zoom)
        resized = pil.resize((nw, nh), Image.BILINEAR)
        x0 = (nw - w) // 2; y0 = (nh - h) // 2
        return np.array(resized.crop((x0, y0, x0 + w, y0 + h)))

    return VideoClip(make_frame, duration=duration).set_fps(FPS)


# ── TTS ──────────────────────────────────────────────────────
async def _tts(text: str, path: str):
    import edge_tts
    com = edge_tts.Communicate(text, VOICE, rate="+5%", pitch="+0Hz")
    await com.save(path)

def tts(text: str, path: str):
    asyncio.run(_tts(text, path))


# ── 場景腳本 ─────────────────────────────────────────────────
def build_scenes(product: dict) -> list:
    name   = product.get("name", "寵物商品")[:20]
    kw     = product.get("keyword", "寵物用品")
    price  = product.get("price_twd", "299")
    rating = product.get("rating", "4.8")
    sold   = product.get("sold_monthly", "1000")

    return [
        {
            "is_title": True,
            "lines": [f"【老實說】", name, "值不值得買？"],
            "narration": (
                f"大家好，歡迎回到 Purrfectly cute！"
                f"今天幫大家評測這款超多人買的{kw}，「{name}」。"
                f"月銷{sold}件，評分{rating}分，到底好不好用？我直接告訴你實話！"
            ),
        },
        {
            "title": "📦 商品基本資料",
            "lines": [
                f"名稱：{name}",
                f"售價：NT$ {price}",
                f"評分：{'⭐' * int(float(rating))}  {rating} / 5",
                f"月銷：{sold} 件",
            ],
            "narration": (
                f"先看基本資料。這款{kw}定價{price}元，"
                f"評分{rating}分，每個月賣掉{sold}件。"
                f"這個銷量代表很多飼主回購，通常是好東西的指標，"
                f"讓我來告訴你原因。"
            ),
        },
        {
            "title": "🔍 外觀與品質",
            "lines": [
                "• 包裝厚實，第一眼質感不錯",
                "• 材質通過 SGS 安全認證",
                "• 做工細緻，無毛邊刺鼻味",
                "• 尺寸設計符合多種體型",
                "• 清潔保養方便不費力",
            ],
            "narration": (
                f"先聊外觀，這部分我特別在意。"
                f"拿到{name}，包裝很厚實，質感算是這個價位少見的好。"
                f"材質有通過安全認證，沒有刺鼻的塑膠味，"
                f"這對家裡有毛孩的人來說非常重要，絕對不能馬虎。"
            ),
        },
        {
            "title": "✅ 真實使用優點",
            "lines": [
                "✅ 品質穩定，用了不後悔",
                "✅ 毛孩接受度超高，不排斥",
                f"✅ {price}元 CP 值爆表",
                "✅ 同類商品中評分最高之一",
                "✅ 老客戶回購率高",
            ],
            "narration": (
                f"說說讓我印象最深的優點。"
                f"第一個，我家毛孩對這款{kw}接受度很高，完全沒有適應期。"
                f"第二個，品質非常穩定，用了一段時間都沒有出問題。"
                f"第三個，以{price}元這個價格，真的是這個類別裡 CP 值數一數二的選擇。"
            ),
        },
        {
            "title": "❌ 需要注意的地方",
            "lines": [
                "❌ 需定期清潔才能維持效果",
                "❌ 少數寵物需 1～2 週適應",
                "❌ 購買前請確認尺寸適合",
                "→ 初次使用建議循序漸進",
                "→ 有特殊狀況請諮詢獸醫",
            ],
            "narration": (
                f"當然也有要注意的地方，我不幫廠商說話。"
                f"這款{kw}需要定期清潔，偷懶的話效果會打折。"
                f"另外，少數很挑剔的寵物可能需要一兩週適應，"
                f"第一次用的時候，不要一下子用太多，讓毛孩慢慢接受。"
            ),
        },
        {
            "title": "💰 購買建議",
            "lines": [
                f"蝦皮現貨：NT$ {price}",
                "市場評比：同類中性價比最高",
                "推薦指數：⭐⭐⭐⭐⭐",
                "",
                "👉 購買連結在影片說明欄",
                "🔔 訂閱頻道不錯過好物推薦",
            ],
            "narration": (
                f"最後是購買建議。"
                f"這款{name}，蝦皮售價{price}元，以這個品質來說真的很划算。"
                f"如果你家毛孩需要{kw}，我強烈推薦這款。"
                f"我把蝦皮的優惠連結放在影片說明欄，"
                f"直接點進去就可以下單，省去自己搜尋的時間！"
            ),
        },
        {
            "is_end": True,
            "lines": ["感謝收看！", "按讚 👍  訂閱 🔔  開通知 🔔", "Purrfectly cute  每週更新"],
            "narration": (
                f"好了，今天{kw}的評測就到這邊！"
                f"如果這部影片對你有幫助，麻煩幫我按個讚，"
                f"也記得訂閱頻道、開啟小鈴鐺，"
                f"我每週都會分享最新的寵物好物評測，讓你不用自己踩雷！"
                f"我們下週見，bye bye！"
            ),
        },
    ]


# ── 合成影片 ─────────────────────────────────────────────────
def create_video(product: dict, output_path: str):
    from moviepy.editor import AudioFileClip, concatenate_videoclips

    font_path = find_cjk_font()
    scenes    = build_scenes(product)

    # 抓圖
    keyword = product.get("keyword", "寵物用品")
    name    = product.get("name", "")
    print(f"  [Img] 抓取商品圖片...")
    product_img = fetch_image(keyword, name)
    bg_img      = product_img   # 同一張圖，背景模糊化

    clips = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, scene in enumerate(scenes):
            audio_path = f"{tmpdir}/a{i:02d}.mp3"
            print(f"    場景 {i+1}/{len(scenes)} TTS...")
            tts(scene["narration"], audio_path)

            aud      = AudioFileClip(audio_path)
            duration = aud.duration + 0.6
            aud.close()

            slide = make_slide(
                bg_bytes      = bg_img,
                product_bytes = product_img if not scene.get("is_title") and not scene.get("is_end") else None,
                lines         = scene.get("lines", []),
                font_path     = font_path,
                title         = scene.get("title"),
                is_title      = scene.get("is_title", False),
                is_end        = scene.get("is_end", False),
            )

            # 交替推鏡 / 拉鏡
            zoom_in  = (i % 2 == 0)
            vclip = kenburns_clip(
                slide, duration,
                zoom_start = 1.00 if zoom_in else 1.07,
                zoom_end   = 1.07 if zoom_in else 1.00,
            )

            # 加音軌
            aud_clip = AudioFileClip(audio_path)
            vclip    = vclip.set_audio(aud_clip)

            # 淡入淡出
            if i > 0:
                vclip = vclip.crossfadein(0.4)
            if i < len(scenes) - 1:
                vclip = vclip.crossfadeout(0.4)

            clips.append(vclip)
            print(f"    場景 {i+1} 完成（{duration:.1f}s）")

        print("    合成最終影片...")
        final = concatenate_videoclips(clips, method="compose", padding=-0.4)
        final.write_videofile(
            output_path,
            fps         = FPS,
            codec       = "libx264",
            audio_codec = "aac",
            bitrate     = "3500k",
            verbose     = False,
            logger      = None,
        )
        total = final.duration
        final.close()
        return total


# ── 主函式 ────────────────────────────────────────────────────
def run_video_maker():
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(glob.glob("pipeline/output/data/articles_summary_*.json"), reverse=True)
    if not files:
        print("[Video] 找不到文章摘要，跳過")
        return []

    with open(files[0], encoding="utf-8") as f:
        articles = json.load(f)

    if not articles:
        print("[Video] 文章列表為空，改用 PRODUCT_DATABASE 備用")
        try:
            from pipeline.config import PRODUCT_DATABASE
            import hashlib
            today  = datetime.now().strftime("%Y%m%d")
            offset = int(hashlib.md5(today.encode()).hexdigest(), 16) % len(PRODUCT_DATABASE)
            p      = PRODUCT_DATABASE[offset]
            articles = [{
                "title":    p["name"],
                "keyword":  p["keyword"],
                "price":    str(p["price_twd"]),
                "rating":   str(p["rating"]),
                "affiliate_url": "",
            }]
        except Exception as e:
            print(f"[Video] 備用失敗：{e}")
            return []

    date_str  = datetime.now().strftime("%Y%m%d")
    generated = []
    article   = articles[0]

    product = {
        "name":         article.get("title", "寵物商品評測"),
        "keyword":      article.get("keyword", "寵物用品"),
        "price_twd":    article.get("price", "299"),
        "rating":       article.get("rating", "4.8"),
        "sold_monthly": "1000+",
        "affiliate_url": article.get("affiliate_url", ""),
    }

    output_path = str(VIDEOS_DIR / f"{date_str}_01.mp4")

    print(f"\n{'='*52}")
    print(f"  [Video] {product['name'][:35]}")
    print(f"{'='*52}")

    try:
        duration = create_video(product, output_path)
        print(f"  [Video] ✓ {output_path}")
        print(f"  [Video] 長度：{duration:.0f}s（{duration/60:.1f}分鐘）")
        generated.append({
            "path":        output_path,
            "title":       f"【老實說】{product['name'][:20]} 值不值得買？",
            "keyword":     product["keyword"],
            "description": (
                f"今天評測「{product['name'][:30]}」！\n"
                f"評分 {product['rating']}/5，月銷 {product['sold_monthly']} 件。\n\n"
                f"🛒 蝦皮優惠連結：{product['affiliate_url']}\n"
                f"📖 完整評測文章：https://a12012300-ux.github.io\n\n"
                f"#Purrfectlycute #{product['keyword']} #寵物推薦 #台灣寵物"
            ),
        })
    except Exception as e:
        print(f"  [Video] 失敗：{e}")
        import traceback; traceback.print_exc()

    return generated


if __name__ == "__main__":
    run_video_maker()
