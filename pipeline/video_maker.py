"""
pipeline/video_maker.py  v3  —  高流量 YouTube 影片生成器
套用頂尖寵物頻道技巧：
  ✓ Pexels 真實寵物影片 B-roll（每 10-15 秒換畫面）
  ✓ 前 5 秒強力 Hook（痛點問句＋商品預覽）
  ✓ Ken Burns 推拉鏡頭效果
  ✓ 淡入淡出轉場
  ✓ 自動生成高點擊率縮圖
  ✓ 結構：Hook → 揭示 → 特色 → 優 → 缺 → 評分 → CTA
需 env: PEXELS_API_KEY（選填，有更好；無則退回靜態圖）
"""
import sys, os, json, glob, asyncio, tempfile, io, hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

VIDEOS_DIR     = Path("pipeline/output/videos")
THUMBS_DIR     = Path("pipeline/output/thumbs")
VOICE          = "zh-TW-HsiaoChenNeural"
WIDTH, HEIGHT  = 1920, 1080
FPS            = 24
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

# ── 關鍵字映射 ────────────────────────────────────────────────
KW_EN = {
    "貓糧":"cat food","貓罐頭":"cat eating","貓砂":"cat litter box",
    "貓抓板":"cat scratching","貓咪玩具":"kitten playing toy",
    "貓床":"cat sleeping","貓零食":"cat treat",
    "狗糧":"dog food bowl","狗罐頭":"dog eating","狗零食":"dog treat",
    "狗玩具":"dog playing fetch","狗牽繩":"dog walking leash",
    "狗床":"dog sleeping","除毛梳":"cat grooming",
    "寵物碗":"pet eating bowl","自動餵食器":"automatic feeder",
    "寵物外出包":"cat carrier bag","指甲剪":"cat grooming spa",
    "益生菌":"healthy happy pet","洗毛精":"cat bath grooming",
    "貓":"cute kitten playing","狗":"cute puppy playing",
    "寵物":"cute pet playing",
}

def kw2en(keyword: str) -> str:
    for zh, en in KW_EN.items():
        if zh in keyword:
            return en
    return "cute pet"

def pet_type(keyword: str) -> str:
    if "貓" in keyword: return "cat"
    if "狗" in keyword: return "dog"
    return "pet"


# ════════════════════════════════════════════════════════════
#  PEXELS 影片抓取
# ════════════════════════════════════════════════════════════
def pexels_video(query: str, max_dur: int = 12, save_path: str = "") -> str | None:
    """從 Pexels 下載寵物短片，回傳 mp4 路徑。失敗回傳 None。"""
    if not PEXELS_API_KEY:
        return None
    try:
        import requests
        h = {"Authorization": PEXELS_API_KEY}
        url = (f"https://api.pexels.com/videos/search"
               f"?query={quote(query)}&per_page=8&orientation=landscape&size=medium")
        videos = requests.get(url, headers=h, timeout=12).json().get("videos", [])
        # 優先選 5-12 秒的
        for v in sorted(videos, key=lambda x: abs(x.get("duration", 99) - 8)):
            if v.get("duration", 99) > max_dur:
                continue
            for f in sorted(v.get("video_files", []),
                            key=lambda x: x.get("width", 0), reverse=True):
                if f.get("width", 0) >= 1280 and "mp4" in f.get("file_type", ""):
                    r = requests.get(f["link"], timeout=40, stream=True)
                    if r.status_code == 200:
                        with open(save_path, "wb") as fp:
                            for chunk in r.iter_content(65536):
                                fp.write(chunk)
                        print(f"  [Pexels] OK: {query[:30]} → {save_path}")
                        return save_path
    except Exception as e:
        print(f"  [Pexels] 失敗 ({query}): {e}")
    return None


# ════════════════════════════════════════════════════════════
#  商品圖片抓取
# ════════════════════════════════════════════════════════════
def shopee_img(keyword: str) -> bytes | None:
    try:
        import requests
        h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
             "referer": "https://shopee.tw/"}
        url = (f"https://shopee.tw/api/v4/search/search_items"
               f"?by=relevancy&keyword={quote(keyword)}&limit=3&newest=0"
               f"&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH&version=2")
        items = requests.get(url, headers=h, timeout=12).json().get("items", [])
        for item in items[:3]:
            img_id = item.get("item_basic", {}).get("image", "")
            if not img_id: continue
            r = requests.get(f"https://cf.shopee.tw/file/{img_id}", headers=h, timeout=10)
            if r.status_code == 200 and len(r.content) > 5000:
                return r.content
    except Exception as e:
        print(f"  [Shopee] 失敗: {e}")
    return None

def unsplash_img(keyword: str) -> bytes | None:
    try:
        import requests
        r = requests.get(f"https://source.unsplash.com/1920x1080/?{kw2en(keyword)}",
                         timeout=15, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 20000:
            return r.content
    except: pass
    return None

def get_product_img(keyword: str, name: str = "") -> bytes | None:
    for q in ([name[:30]] if name else []) + [keyword]:
        img = shopee_img(q)
        if img: return img
    return unsplash_img(keyword)


# ════════════════════════════════════════════════════════════
#  背景 / 投影片處理
# ════════════════════════════════════════════════════════════
def blur_darken(img_bytes: bytes, blur: int = 14, dark: float = 0.65) -> "np.ndarray":
    from PIL import Image, ImageFilter
    import numpy as np
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    iw, ih = img.size
    if iw / ih > WIDTH / HEIGHT:
        nh = HEIGHT; nw = int(iw * HEIGHT / ih)
    else:
        nw = WIDTH; nh = int(ih * WIDTH / iw)
    img = img.resize((nw, nh), Image.LANCZOS)
    x0 = (nw - WIDTH) // 2; y0 = (nh - HEIGHT) // 2
    img = img.crop((x0, y0, x0 + WIDTH, y0 + HEIGHT))
    img = img.filter(ImageFilter.GaussianBlur(radius=blur))
    black = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    return np.array(Image.blend(img, black, alpha=dark))

def gradient_bg() -> "np.ndarray":
    from PIL import Image, ImageDraw
    import numpy as np
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        t = y / HEIGHT
        draw.line([(0, y), (WIDTH, y)],
                  fill=(int(10 + 20*t), int(5 + 10*t), int(30 + 40*t)))
    return np.array(img)

def find_font() -> str:
    for p in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKtc-Regular.otf",
        "C:/Windows/Fonts/msjh.ttc",
        "C:/Windows/Fonts/mingliu.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]:
        if Path(p).exists():
            return p
    return ""


# ════════════════════════════════════════════════════════════
#  投影片繪製
# ════════════════════════════════════════════════════════════
def draw_slide(bg_bytes, prod_bytes, lines, font_path,
               title=None, is_title=False, is_end=False,
               score=None) -> "np.ndarray":
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    bg = Image.fromarray(blur_darken(bg_bytes) if bg_bytes else gradient_bg())

    try:
        fH  = ImageFont.truetype(font_path, 92) if font_path else ImageFont.load_default()
        fT  = ImageFont.truetype(font_path, 62) if font_path else ImageFont.load_default()
        fB  = ImageFont.truetype(font_path, 46) if font_path else ImageFont.load_default()
        fSM = ImageFont.truetype(font_path, 30) if font_path else ImageFont.load_default()
    except Exception:
        fH = fT = fB = fSM = ImageFont.load_default()

    draw = ImageDraw.Draw(bg)

    # 浮水印
    draw.text((WIDTH - 28, HEIGHT - 18), "Purrfectly cute",
              fill=(200, 200, 200), font=fSM, anchor="rb")

    # ── 標題 / 結尾 ─────────────────────────────────────────
    if is_title or is_end:
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        for y in range(HEIGHT // 3, HEIGHT * 2 // 3):
            a = int(200 * (1 - abs(y - HEIGHT // 2) / (HEIGHT // 6)))
            a = max(0, min(255, a))
            od.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, a))
        bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(bg)
        y_pos = HEIGHT // 2 - 110
        for i, line in enumerate(lines):
            font = fH if i == 0 else fT
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                tw = bbox[2] - bbox[0]
            except Exception:
                tw = len(line) * 45
            x = (WIDTH - tw) // 2
            draw.text((x + 3, y_pos + 3), line, fill=(0, 0, 0), font=font)
            col = (255, 215, 0) if i == 0 else (255, 255, 255)
            draw.text((x, y_pos), line, fill=col, font=font)
            y_pos += 108

    # ── 內容畫面 ─────────────────────────────────────────────
    else:
        text_w = int(WIDTH * 0.58) if prod_bytes else WIDTH - 60
        # 左側遮罩
        mask = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        md = ImageDraw.Draw(mask)
        md.rectangle([0, 0, text_w + 50, HEIGHT], fill=(0, 0, 0, 160))
        bg = Image.alpha_composite(bg.convert("RGBA"), mask).convert("RGB")
        draw = ImageDraw.Draw(bg)

        # 商品圖
        if prod_bytes:
            try:
                pi = Image.open(io.BytesIO(prod_bytes)).convert("RGB")
                pw = 500; ph = 500
                pi.thumbnail((pw, ph), Image.LANCZOS)
                px = WIDTH - 560; py = (HEIGHT - ph) // 2
                # 白色背景
                bg.paste(Image.new("RGB", (pw + 20, ph + 20), (255, 255, 255)),
                         (px - 10, py - 10))
                bg.paste(pi, (px + (pw - pi.width) // 2, py + (ph - pi.height) // 2))
                draw = ImageDraw.Draw(bg)
            except Exception:
                pass

        # 評分（若有）
        if score is not None:
            stars = "★" * score + "☆" * (5 - score)
            draw.text((60, HEIGHT - 70), f"評分：{stars}  {score}/5",
                      fill=(255, 215, 0), font=fSM)

        # 標題列
        y_pos = 48
        if title:
            try:
                bbox = draw.textbbox((0, 0), title, font=fT)
                th = bbox[3] - bbox[1]
            except Exception:
                th = 64
            draw.rectangle([0, y_pos - 10, text_w + 50, y_pos + th + 14],
                           fill=(180, 130, 0))
            draw.text((52, y_pos), title, fill=(255, 255, 255), font=fT)
            y_pos += th + 50

        # 內容
        for line in lines:
            if not line.strip():
                y_pos += 20; continue
            col = (240, 240, 240)
            if line.startswith("✅"): col = (80, 255, 140)
            elif line.startswith("❌"): col = (255, 100, 100)
            elif line.startswith(("💰", "👉", "🔔", "⭐")): col = (255, 215, 60)
            draw.text((56, y_pos + 2), line, fill=(0, 0, 0), font=fB)
            draw.text((55, y_pos), line, fill=col, font=fB)
            y_pos += 68

    return np.array(bg)


# ════════════════════════════════════════════════════════════
#  縮圖生成（高 CTR 設計）
# ════════════════════════════════════════════════════════════
def generate_thumbnail(product: dict, prod_img_bytes: bytes,
                       output_path: str, font_path: str):
    """生成 1280x720 高點擊率縮圖"""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import numpy as np

    TW, TH = 1280, 720
    name   = product.get("name", "")[:18]
    price  = product.get("price_twd", "")
    kw     = product.get("keyword", "寵物")

    try:
        fBig = ImageFont.truetype(font_path, 90) if font_path else ImageFont.load_default()
        fMed = ImageFont.truetype(font_path, 54) if font_path else ImageFont.load_default()
        fSm  = ImageFont.truetype(font_path, 38) if font_path else ImageFont.load_default()
    except Exception:
        fBig = fMed = fSm = ImageFont.load_default()

    # 背景：商品圖模糊 + 漸層
    if prod_img_bytes:
        bg = Image.open(io.BytesIO(prod_img_bytes)).convert("RGB")
        bg = bg.resize((TW, TH), Image.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=6))
        dark = Image.new("RGB", (TW, TH), (0, 0, 0))
        bg = Image.blend(bg, dark, alpha=0.55)
    else:
        bg = Image.new("RGB", (TW, TH), (20, 10, 50))

    # 商品圖（右側大圖，無模糊）
    if prod_img_bytes:
        try:
            pi = Image.open(io.BytesIO(prod_img_bytes)).convert("RGB")
            pi.thumbnail((520, 520), Image.LANCZOS)
            bw = Image.new("RGB", (pi.width + 20, pi.height + 20), (255, 255, 255))
            bg.paste(bw, (TW - pi.width - 70, (TH - pi.height) // 2 - 10))
            bg.paste(pi, (TW - pi.width - 60, (TH - pi.height) // 2))
        except Exception:
            pass

    draw = ImageDraw.Draw(bg)

    # 紅色「值不值得買？」大字
    q_text = "值不值得買？"
    try:
        bbox = draw.textbbox((0, 0), q_text, font=fBig)
        tw = bbox[2] - bbox[0]
    except Exception:
        tw = len(q_text) * 48
    x = (TW // 2 - 280 - tw) // 2
    # 紅底
    draw.rectangle([x - 20, 60, x + tw + 20, 60 + 100], fill=(220, 30, 30))
    draw.text((x, 65), q_text, fill=(255, 255, 255), font=fBig)

    # 商品名
    draw.text((40, 190), name, fill=(255, 215, 0), font=fMed)

    # 價格 badge
    price_text = f"NT$ {price}"
    draw.rectangle([40, 270, 280, 340], fill=(255, 80, 0))
    draw.text((55, 278), price_text, fill=(255, 255, 255), font=fSm)

    # 頻道名
    draw.text((40, TH - 55), "Purrfectly cute", fill=(200, 200, 200), font=fSm)

    # 老實說標籤
    draw.rectangle([40, TH - 110, 250, TH - 65], fill=(0, 120, 200))
    draw.text((55, TH - 105), "老實說評測", fill=(255, 255, 255), font=fSm)

    bg.save(output_path, "JPEG", quality=95)
    print(f"  [Thumb] 縮圖已儲存：{output_path}")


# ════════════════════════════════════════════════════════════
#  Ken Burns 效果
# ════════════════════════════════════════════════════════════
def kenburns(frame_arr, duration, zoom_s=1.00, zoom_e=1.07):
    from PIL import Image
    from moviepy.editor import VideoClip
    import numpy as np
    pil = Image.fromarray(frame_arr)
    w, h = pil.size

    def make_frame(t):
        p = t / duration
        p = p * p * (3 - 2 * p)
        zm = zoom_s + (zoom_e - zoom_s) * p
        nw, nh = int(w * zm), int(h * zm)
        rs = pil.resize((nw, nh), Image.BILINEAR)
        x0, y0 = (nw - w) // 2, (nh - h) // 2
        return np.array(rs.crop((x0, y0, x0 + w, y0 + h)))

    return VideoClip(make_frame, duration=duration).set_fps(FPS)


# ════════════════════════════════════════════════════════════
#  TTS
# ════════════════════════════════════════════════════════════
async def _tts(text: str, path: str):
    import edge_tts
    com = edge_tts.Communicate(text, VOICE, rate="+3%", pitch="+0Hz")
    await com.save(path)

def tts(text: str, path: str):
    asyncio.run(_tts(text, path))


# ════════════════════════════════════════════════════════════
#  影片場景腳本（高流量結構）
# ════════════════════════════════════════════════════════════
def build_scenes(product: dict) -> list:
    name   = product.get("name", "寵物商品")[:22]
    kw     = product.get("keyword", "寵物用品")
    price  = product.get("price_twd", "299")
    rating = product.get("rating", "4.8")
    sold   = product.get("sold_monthly", "1000")
    pt     = pet_type(kw)
    en_kw  = kw2en(kw)

    return [
        # ── Scene 1：Hook（5秒）────────────────────────────
        {
            "type": "broll",           # 用 Pexels B-roll 影片
            "pexels_query": f"{en_kw} close up",
            "duration": 7,
            "overlay_text": f"你家{pt == 'cat' and '貓' or pt == 'dog' and '狗' or '寵物'}也有這困擾嗎？",
            "overlay_sub": "看完再決定！",
            "narration": (
                f"嘿！如果你也在幫你的毛孩找好用的{kw}，"
                f"你絕對要看完這部影片！"
                f"今天我幫大家完整測試這款月銷{sold}件的熱門商品，"
                f"到底好不好用，我全部說給你聽！"
            ),
        },
        # ── Scene 2：商品揭示 ──────────────────────────────
        {
            "type": "product",
            "title": "🎯 今日評測商品",
            "lines": [
                f"【{name}】",
                f"售價 NT$ {price}",
                f"評分 {rating} / 5  {'⭐' * int(float(rating))}",
                f"月銷 {sold} 件  🔥 熱賣中",
            ],
            "narration": (
                f"今天要評測的是「{name}」。"
                f"這款{kw}在蝦皮上評分高達{rating}分，每個月賣掉{sold}件，"
                f"光看這個數字就知道很多人在買。"
                f"但銷量好不代表適合你，所以我來幫你把關！"
            ),
        },
        # ── Scene 3：為什麼這麼多人買？─────────────────────
        {
            "type": "product",
            "title": "🤔 為什麼這麼多人買？",
            "lines": [
                f"• 同類商品中評分最高之一",
                f"• {sold} 位飼主選擇這款",
                f"• 蝦皮熱銷榜常客",
                f"• 買家回購率極高",
                f"• 價格在合理範圍內",
            ],
            "narration": (
                f"先來說為什麼這麼多人買。"
                f"月銷{sold}件這個數字在{kw}類別裡算是很亮眼的，"
                f"而且評分{rating}分代表買家整體滿意度相當高。"
                f"不過我知道你想聽的是真實使用感受，不是數字，"
                f"所以接下來我直接告訴你我的評測結果！"
            ),
        },
        # ── Scene 4：B-roll 橋段 ──────────────────────────
        {
            "type": "broll",
            "pexels_query": f"happy {en_kw}",
            "duration": 6,
            "overlay_text": "我實際測試給你看",
            "overlay_sub": "以下是真實體驗",
            "narration": (
                f"好，廢話不多說，直接進入實測！"
                f"我把{name}的每個細節都測過一遍，"
                f"優點說優點，缺點我也不會幫廠商蓋住。"
            ),
        },
        # ── Scene 5：功能細節 ──────────────────────────────
        {
            "type": "product",
            "title": "🔍 外觀 & 功能細節",
            "lines": [
                "• 包裝品質佳，質感超越同價位",
                "• 材質通過安全認證，無毒無異味",
                "• 設計符合寵物習性，直覺好上手",
                "• 尺寸設計適合不同體型",
                "• 清潔保養非常方便",
            ],
            "narration": (
                f"先聊外觀和功能。"
                f"拿到{name}第一眼，包裝很紮實，這個價格能有這種質感不多見。"
                f"材質有安全認證，沒有刺鼻塑膠味——這點超重要，"
                f"因為寵物的嗅覺比人類靈敏好幾倍，如果有異味牠們根本不會靠近。"
                f"操作上也非常直覺，不用看說明書就能馬上上手。"
            ),
        },
        # ── Scene 6：優點 ──────────────────────────────────
        {
            "type": "product",
            "title": "✅ 真實優點（不業配）",
            "lines": [
                "✅ 品質穩定，長期使用沒有問題",
                "✅ 毛孩接受度極高，幾乎零適應期",
                f"✅ NT$ {price} 這個價格 CP 值爆表",
                "✅ 做工細緻，不像廉價品",
                "✅ 用了之後理解為何回購率高",
            ],
            "narration": (
                f"說說讓我真的很滿意的地方。"
                f"最大的亮點是我家毛孩的接受度——幾乎是零適應期，"
                f"直接就喜歡上了，這對我來說是最重要的指標。"
                f"品質方面，用了一段時間都沒有出現變形或損壞的問題。"
                f"而且說真的，以{price}元這個價格，"
                f"你很難在市場上找到比這個更划算的選擇。"
            ),
        },
        # ── Scene 7：B-roll + 缺點引導 ─────────────────────
        {
            "type": "broll",
            "pexels_query": f"curious {pt} looking",
            "duration": 5,
            "overlay_text": "但有一個地方要注意...",
            "overlay_sub": "我直說不幫廠商講話",
            "narration": (
                f"當然，沒有什麼東西是完美的，"
                f"我也不是業配帳號，有缺點我一定說清楚。"
            ),
        },
        # ── Scene 8：缺點（誠實評測）──────────────────────
        {
            "type": "product",
            "title": "❌ 需要注意的地方",
            "lines": [
                "❌ 需定期清潔才能維持最佳效果",
                "❌ 少數挑剔的寵物需 1-2 週適應",
                "❌ 注意選對尺寸，勿憑感覺亂選",
                "→ 初次使用建議循序漸進",
                "→ 有特殊狀況請先諮詢獸醫",
            ],
            "narration": (
                f"需要注意的地方。"
                f"第一，這款{kw}需要定期清潔，如果你是那種比較懶得保養的，"
                f"使用效果會大打折扣，這點要誠實說。"
                f"第二，極少數非常挑剔的寵物可能需要一兩週適應，"
                f"別急，給牠時間。"
                f"最後提醒，買之前一定要確認尺寸符合你家毛孩。"
            ),
        },
        # ── Scene 9：價格分析 ──────────────────────────────
        {
            "type": "product",
            "title": "💰 價格分析：值不值得？",
            "lines": [
                f"蝦皮現貨：NT$ {price}",
                f"市場同類均價：NT$ {int(float(price) * 1.3):.0f} 起",
                f"省下約：NT$ {int(float(price) * 0.3):.0f}",
                "",
                f"⭐ 推薦指數：{'★' * 4}☆  4.5 / 5",
                "👉 連結在說明欄 ↓",
            ],
            "narration": (
                f"最後說說值不值得買。"
                f"這款{name}，蝦皮現在賣{price}元，"
                f"同類商品大概都要{int(float(price) * 1.3):.0f}元起跳，"
                f"這個定價算是同級品裡偏低的。"
                f"如果你本來就有在考慮這類{kw}，"
                f"我認為這款是目前市場上 CP 值最高的選擇之一，不要猶豫。"
                f"購買連結我放在說明欄，有聯盟折扣，"
                f"直接點進去就可以下單！"
            ),
            "score": 4,
        },
        # ── Scene 10：Happy ending B-roll ─────────────────
        {
            "type": "broll",
            "pexels_query": f"happy {pt} cozy home",
            "duration": 6,
            "overlay_text": f"總評：強推！",
            "overlay_sub": f"適合 {pet_type(kw) == 'cat' and '貓咪' or '毛孩'} 飼主入手",
            "narration": (
                f"好了！今天「{name}」的完整評測就到這邊。"
                f"綜合來說，這款{kw}品質穩定、CP 值高、毛孩接受度好，"
                f"是我目前同類裡最推薦的選擇。"
            ),
        },
        # ── Scene 11：CTA Outro ────────────────────────────
        {
            "type": "end",
            "is_end": True,
            "lines": ["喜歡記得按讚 👍", "訂閱開通知 🔔 不錯過好物", "Purrfectly cute  每週更新"],
            "narration": (
                f"如果這部影片有幫到你，麻煩按個讚，"
                f"訂閱頻道開啟小鈴鐺！"
                f"我每週都會更新最新的寵物好物評測，"
                f"讓你不用自己踩雷、幫你省時間省錢。"
                f"我們下週見！掰掰！"
            ),
        },
    ]


# ════════════════════════════════════════════════════════════
#  B-roll 投影片（Pexels 影片 + 文字疊加）
# ════════════════════════════════════════════════════════════
def make_broll_slide(text_main: str, text_sub: str,
                     font_path: str) -> "np.ndarray":
    """製作 B-roll 過場文字卡（Pexels 影片沒抓到時的備用畫面）"""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    bg = Image.new("RGB", (WIDTH, HEIGHT), (15, 10, 30))
    draw = ImageDraw.Draw(bg)
    for y in range(HEIGHT):
        t = y / HEIGHT
        r, g, b = int(15 + 25 * t), int(10 + 15 * t), int(30 + 50 * t)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    try:
        fL = ImageFont.truetype(font_path, 78) if font_path else ImageFont.load_default()
        fS = ImageFont.truetype(font_path, 46) if font_path else ImageFont.load_default()
    except Exception:
        fL = fS = ImageFont.load_default()

    for i, (txt, fnt, col, y) in enumerate([
        (text_main, fL, (255, 215, 0), HEIGHT // 2 - 60),
        (text_sub,  fS, (200, 200, 200), HEIGHT // 2 + 55),
    ]):
        try:
            bbox = draw.textbbox((0, 0), txt, font=fnt)
            tw = bbox[2] - bbox[0]
        except Exception:
            tw = len(txt) * 40
        x = (WIDTH - tw) // 2
        draw.text((x + 2, y + 2), txt, fill=(0, 0, 0), font=fnt)
        draw.text((x, y), txt, fill=col, font=fnt)

    draw.text((WIDTH - 28, HEIGHT - 18), "Purrfectly cute",
              fill=(120, 120, 120), font=
              (ImageFont.truetype(font_path, 28) if font_path else ImageFont.load_default()),
              anchor="rb")
    return np.array(bg)


def overlay_text_on_video(video_clip, text_main: str, text_sub: str,
                           font_path: str) -> "VideoClip":
    """在 Pexels 影片上疊加半透明文字"""
    from moviepy.editor import VideoClip
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    W, H = video_clip.size
    try:
        fL = ImageFont.truetype(font_path, 72) if font_path else ImageFont.load_default()
        fS = ImageFont.truetype(font_path, 44) if font_path else ImageFont.load_default()
        fWM = ImageFont.truetype(font_path, 26) if font_path else ImageFont.load_default()
    except Exception:
        fL = fS = fWM = ImageFont.load_default()

    # 預渲染文字 overlay（RGBA）
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # 底部漸層
    for y in range(H * 2 // 3, H):
        a = int(180 * (y - H * 2 // 3) / (H // 3))
        od.line([(0, y), (W, y)], fill=(0, 0, 0, min(a, 180)))

    def center_text(txt, fnt, y, col, draw_obj):
        try:
            bbox = draw_obj.textbbox((0, 0), txt, font=fnt)
            tw = bbox[2] - bbox[0]
        except Exception:
            tw = len(txt) * 38
        x = (W - tw) // 2
        draw_obj.text((x + 2, y + 2), txt, fill=(0, 0, 0, 200), font=fnt)
        draw_obj.text((x, y), txt, fill=col, font=fnt)

    center_text(text_main, fL, H * 3 // 4 - 60, (255, 215, 0, 255), od)
    center_text(text_sub,  fS, H * 3 // 4 + 32, (255, 255, 255, 220), od)
    od.text((W - 20, H - 15), "Purrfectly cute",
            fill=(180, 180, 180, 200), font=fWM, anchor="rb")

    overlay_arr = np.array(overlay)

    def make_frame(t):
        frame = video_clip.get_frame(t).copy()
        bg_pil  = Image.fromarray(frame).convert("RGBA")
        merged  = Image.alpha_composite(bg_pil, overlay)
        return np.array(merged.convert("RGB"))

    return VideoClip(make_frame, duration=video_clip.duration).set_fps(FPS)


# ════════════════════════════════════════════════════════════
#  主影片合成
# ════════════════════════════════════════════════════════════
def create_video(product: dict, output_path: str) -> float:
    from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_videoclips

    font_path  = find_font()
    scenes     = build_scenes(product)
    keyword    = product.get("keyword", "寵物用品")
    name       = product.get("name", "")

    print(f"  [Img] 抓取商品圖...")
    prod_img = get_product_img(keyword, name)

    clips = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, scene in enumerate(scenes):
            print(f"\n  ── 場景 {i+1}/{len(scenes)}: {scene.get('title') or scene.get('type','?')}")

            # TTS 語音
            audio_path = f"{tmpdir}/a{i:02d}.mp3"
            tts(scene["narration"], audio_path)
            aud_dur = AudioFileClip(audio_path).duration

            # ── B-roll 場景 ──────────────────────────────
            if scene.get("type") == "broll":
                broll_dur  = scene.get("duration", 7)
                total_dur  = max(broll_dur, aud_dur + 0.5)
                clip_path  = f"{tmpdir}/broll_{i:02d}.mp4"

                vid_path = pexels_video(scene["pexels_query"],
                                        max_dur=int(broll_dur) + 8,
                                        save_path=clip_path)

                if vid_path:
                    raw = VideoFileClip(vid_path).without_audio()
                    # 調整尺寸
                    if raw.size != [WIDTH, HEIGHT]:
                        raw = raw.resize((WIDTH, HEIGHT))
                    # 截到需要時長
                    if raw.duration > total_dur:
                        raw = raw.subclip(0, total_dur)
                    elif raw.duration < total_dur:
                        # 重複播放補足長度
                        from moviepy.editor import concatenate_videoclips as cv
                        loops = int(total_dur / raw.duration) + 2
                        raw = cv([raw] * loops).subclip(0, total_dur)
                    # 疊加文字
                    vclip = overlay_text_on_video(
                        raw,
                        scene.get("overlay_text", ""),
                        scene.get("overlay_sub", ""),
                        font_path
                    )
                else:
                    # 備用：靜態文字卡 + Ken Burns
                    slide = make_broll_slide(
                        scene.get("overlay_text", ""),
                        scene.get("overlay_sub", ""),
                        font_path
                    )
                    vclip = kenburns(slide, total_dur)

            # ── 結尾 ─────────────────────────────────────
            elif scene.get("is_end"):
                total_dur = aud_dur + 0.8
                slide = draw_slide(
                    prod_img, None,
                    scene["lines"], font_path,
                    is_end=True
                )
                vclip = kenburns(slide, total_dur, zoom_s=1.0, zoom_e=1.04)

            # ── 一般商品投影片 ────────────────────────────
            else:
                total_dur = aud_dur + 0.6
                zoom_in   = (i % 2 == 0)
                slide = draw_slide(
                    prod_img, prod_img,
                    scene.get("lines", []), font_path,
                    title  = scene.get("title"),
                    score  = scene.get("score"),
                )
                vclip = kenburns(
                    slide, total_dur,
                    zoom_s = 1.00 if zoom_in else 1.07,
                    zoom_e = 1.07 if zoom_in else 1.00,
                )

            # 加音軌
            aud = AudioFileClip(audio_path)
            if aud.duration < total_dur:
                vclip = vclip.set_audio(aud)
            else:
                vclip = vclip.set_audio(aud.subclip(0, total_dur))

            # 轉場
            if i > 0:
                vclip = vclip.crossfadein(0.35)
            if i < len(scenes) - 1:
                vclip = vclip.crossfadeout(0.35)

            clips.append(vclip)
            print(f"     OK  時長 {total_dur:.1f}s")

        total = sum(c.duration for c in clips)
        print(f"\n  [合成] 總時長 {total:.0f}s（{total/60:.1f} min），開始渲染...")
        final = concatenate_videoclips(clips, method="compose", padding=-0.35)
        final.write_videofile(
            output_path, fps=FPS,
            codec="libx264", audio_codec="aac",
            bitrate="3500k", verbose=False, logger=None,
        )
        dur = final.duration
        final.close()
        return dur


# ════════════════════════════════════════════════════════════
#  主函式
# ════════════════════════════════════════════════════════════
def run_video_maker():
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(glob.glob("pipeline/output/data/articles_summary_*.json"), reverse=True)
    if not files:
        print("[Video] 找不到文章摘要，跳過")
        return []

    with open(files[0], encoding="utf-8") as f:
        articles = json.load(f)

    if not articles:
        try:
            from pipeline.config import PRODUCT_DATABASE
            today  = datetime.now().strftime("%Y%m%d")
            offset = int(hashlib.md5(today.encode()).hexdigest(), 16) % len(PRODUCT_DATABASE)
            p      = PRODUCT_DATABASE[offset]
            articles = [{"title": p["name"], "keyword": p["keyword"],
                         "price": str(p["price_twd"]), "rating": str(p["rating"]),
                         "affiliate_url": ""}]
        except Exception as e:
            print(f"[Video] 備用失敗：{e}"); return []

    date_str = datetime.now().strftime("%Y%m%d")
    article  = articles[0]
    product  = {
        "name":         article.get("title", "寵物商品評測"),
        "keyword":      article.get("keyword", "寵物用品"),
        "price_twd":    article.get("price", "299"),
        "rating":       article.get("rating", "4.8"),
        "sold_monthly": "1000+",
        "affiliate_url": article.get("affiliate_url", ""),
    }

    output_path = str(VIDEOS_DIR / f"{date_str}_01.mp4")
    thumb_path  = str(THUMBS_DIR / f"{date_str}_01.jpg")

    print(f"\n{'='*55}")
    print(f"  [Video] {product['name'][:38]}")
    print(f"  [Pexels] {'已設定 ✓' if PEXELS_API_KEY else '未設定（僅靜態圖）'}")
    print(f"{'='*55}")

    try:
        dur = create_video(product, output_path)
        print(f"\n  [Video] ✓ {output_path}")
        print(f"  [Video] 長度：{dur:.0f}s（{dur/60:.1f} 分鐘）")

        # 縮圖
        font_path = find_font()
        prod_img  = get_product_img(product["keyword"], product["name"])
        if prod_img and font_path:
            generate_thumbnail(product, prod_img, thumb_path, font_path)

        return [{
            "path":         output_path,
            "thumb_path":   thumb_path,
            "title":        f"【老實說評測】{product['name'][:20]} 值不值得買？",
            "keyword":      product["keyword"],
            "description":  (
                f"今天完整評測「{product['name'][:30]}」！\n"
                f"評分 {product['rating']}/5，月銷 {product['sold_monthly']} 件。\n\n"
                f"🛒 蝦皮優惠連結：{product['affiliate_url']}\n"
                f"📖 完整評測文章：https://a12012300-ux.github.io\n\n"
                f"⏱ 時間章節：\n"
                f"0:00 你也遇過這困擾嗎？\n"
                f"0:30 今日評測商品介紹\n"
                f"1:00 外觀 & 功能細節\n"
                f"1:45 真實優點（不業配）\n"
                f"2:30 需要注意的地方\n"
                f"3:15 價格分析值不值得？\n"
                f"3:45 最終評分 & 推薦\n\n"
                f"#Purrfectlycute #{product['keyword']} #寵物推薦 #台灣寵物 #寵物評測"
            ),
        }]
    except Exception as e:
        print(f"  [Video] 失敗：{e}")
        import traceback; traceback.print_exc()
        return []


if __name__ == "__main__":
    run_video_maker()
