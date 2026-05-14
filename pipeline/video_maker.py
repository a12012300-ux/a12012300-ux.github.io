"""
pipeline/video_maker.py  v4
高流量 YouTube 影片生成器（無需額外 API Key）
技術：多圖多鏡頭動態效果 + 真實商品圖 + 自動縮圖
  ✓ 從蝦皮/Unsplash 抓多張不同寵物圖（模擬 B-roll）
  ✓ 5 種鏡頭運動效果（推近/拉遠/左搖/右搖/斜移）輪流套用
  ✓ 前 5 秒強力 Hook（痛點問句）
  ✓ 結構：Hook → 揭示 → 特色 → 優 → 缺 → 評分 → CTA
  ✓ 自動生成高點擊率縮圖（1280×720）
  ✓ 淡入淡出轉場
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

VIDEOS_DIR = Path("pipeline/output/videos")
THUMBS_DIR = Path("pipeline/output/thumbs")
VOICE      = "zh-TW-HsiaoChenNeural"
WIDTH, HEIGHT = 1920, 1080
FPS = 24

# ── 關鍵字映射 ────────────────────────────────────────────────
KW_EN = {
    "貓糧":"cat food bowl","貓罐頭":"cat eating delicious",
    "貓砂":"cat litter cozy","貓抓板":"cat scratching playing",
    "貓咪玩具":"kitten playing toy","貓床":"cat sleeping cozy",
    "貓零食":"cat treat snack","貓":"cute kitten portrait",
    "狗糧":"dog food bowl","狗罐頭":"dog eating happy",
    "狗零食":"dog treat happy","狗玩具":"puppy playing fetch",
    "狗牽繩":"dog walking park","狗床":"dog sleeping home",
    "狗":"cute puppy portrait","除毛梳":"cat grooming fluffy",
    "寵物碗":"pet eating bowl","自動餵食器":"cat waiting food",
    "寵物外出包":"cat carrier adventure","指甲剪":"cat spa relaxed",
    "益生菌":"healthy happy cat","洗毛精":"cat bath fluffy",
    "寵物":"cute pet home happy",
}
BROLL_VARIANTS = [
    "{kw} close up portrait",
    "happy {pet} home",
    "{pet} playing indoor",
    "{pet} cute funny",
    "{kw} best quality",
]

def kw2en(kw: str) -> str:
    for zh, en in KW_EN.items():
        if zh in kw: return en
    return "cute pet happy"

def pet_type(kw: str) -> str:
    if "貓" in kw: return "cat"
    if "狗" in kw: return "dog"
    return "pet"


# ════════════════════════════════════════════════════════════
#  圖片抓取（多張，不同查詢）
# ════════════════════════════════════════════════════════════
def shopee_img(keyword: str) -> bytes | None:
    try:
        import requests
        h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
             "referer": "https://shopee.tw/"}
        url = (f"https://shopee.tw/api/v4/search/search_items"
               f"?by=relevancy&keyword={quote(keyword)}&limit=5&newest=0"
               f"&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH&version=2")
        items = requests.get(url, headers=h, timeout=12).json().get("items", [])
        for item in items[:5]:
            img_id = item.get("item_basic", {}).get("image", "")
            if not img_id: continue
            r = requests.get(f"https://cf.shopee.tw/file/{img_id}", headers=h, timeout=10)
            if r.status_code == 200 and len(r.content) > 5000:
                return r.content
    except Exception as e:
        print(f"  [Shopee] {e}")
    return None

def unsplash_img(query: str, w: int = 1920, h: int = 1080) -> bytes | None:
    try:
        import requests
        r = requests.get(f"https://source.unsplash.com/{w}x{h}/?{quote(query)}",
                         timeout=15, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 20000:
            return r.content
    except: pass
    return None

def fetch_broll_images(keyword: str, count: int = 4) -> list[bytes]:
    """抓多張不同的寵物圖作為 B-roll 素材"""
    import time
    results = []
    pt = pet_type(keyword)
    queries = [
        kw2en(keyword),
        f"cute {pt} portrait",
        f"happy {pt} indoor home",
        f"{pt} playing funny",
        f"{pt} adorable close up",
    ]
    for q in queries[:count]:
        img = unsplash_img(q)
        if img:
            results.append(img)
        else:
            results.append(None)
        time.sleep(0.3)  # 避免被限速
    return results

def get_product_img(keyword: str, name: str = "") -> bytes | None:
    for q in ([name[:30]] if name else []) + [keyword]:
        img = shopee_img(q)
        if img: return img
    return unsplash_img(kw2en(keyword))


# ════════════════════════════════════════════════════════════
#  字體
# ════════════════════════════════════════════════════════════
def find_font() -> str:
    for p in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKtc-Regular.otf",
        "C:/Windows/Fonts/msjh.ttc",
        "C:/Windows/Fonts/mingliu.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]:
        if Path(p).exists(): return p
    return ""


# ════════════════════════════════════════════════════════════
#  鏡頭運動效果（5種，輪流套用）
# ════════════════════════════════════════════════════════════
MOTION_EFFECTS = ["zoom_in", "pan_left", "zoom_out", "pan_right", "zoom_pan"]

def motion_clip(img_bytes: bytes | None, duration: float,
                effect: str, text_main: str = "", text_sub: str = "",
                font_path: str = "") -> "VideoClip":
    """
    從靜態圖片建立動態鏡頭效果 clip。
    - zoom_in   : 緩慢推近（最常見，有臨場感）
    - zoom_out  : 緩慢拉遠（開場、結尾常用）
    - pan_left  : 鏡頭向左搖（寬景效果）
    - pan_right : 鏡頭向右搖
    - zoom_pan  : 推近＋向右搖（複合鏡頭）
    """
    from PIL import Image, ImageFilter
    from moviepy.editor import VideoClip
    import numpy as np

    # ── 載入並預處理圖片（略大於畫面，留給運動空間）────────
    SCALE = 1.30   # 預留 30% 運動空間
    if img_bytes:
        try:
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        except Exception:
            img_bytes = None

    if not img_bytes:
        # 漸層備用
        img = Image.new("RGB", (WIDTH, HEIGHT))
        from PIL import ImageDraw
        d = ImageDraw.Draw(img)
        for y in range(HEIGHT):
            t = y / HEIGHT
            d.line([(0,y),(WIDTH,y)], fill=(int(10+30*t), int(8+20*t), int(30+60*t)))

    # 縮放：確保有足夠區域做運動
    iw, ih = img.size
    if iw / ih > WIDTH / HEIGHT:
        nh = int(HEIGHT * SCALE); nw = int(iw * nh / ih)
    else:
        nw = int(WIDTH * SCALE); nh = int(ih * nw / iw)
    if nw < WIDTH:  nw = int(WIDTH * SCALE); nh = int(ih * nw / iw)
    if nh < HEIGHT: nh = int(HEIGHT * SCALE); nw = int(iw * nh / ih)
    img = img.resize((nw, nh), Image.LANCZOS)

    # 輕微變暗（文字可讀性）
    black = Image.new("RGB", (nw, nh), (0, 0, 0))
    img = Image.blend(img, black, alpha=0.28)
    arr = np.array(img)

    def ease(t: float) -> float:
        """平滑 S 曲線"""
        p = max(0.0, min(1.0, t / duration))
        return p * p * (3 - 2 * p)

    # ── 各效果 make_frame ─────────────────────────────────
    if effect == "zoom_in":
        def make_frame(t):
            zm = 1.0 + 0.20 * ease(t)
            cw = max(1, int(WIDTH / zm)); ch = max(1, int(HEIGHT / zm))
            x0 = (nw - cw) // 2; y0 = (nh - ch) // 2
            crop = arr[y0:y0+ch, x0:x0+cw]
            return np.array(Image.fromarray(crop).resize((WIDTH, HEIGHT), Image.BILINEAR))

    elif effect == "zoom_out":
        def make_frame(t):
            zm = 1.20 - 0.20 * ease(t)
            cw = max(1, int(WIDTH / zm)); ch = max(1, int(HEIGHT / zm))
            x0 = (nw - cw) // 2; y0 = (nh - ch) // 2
            crop = arr[y0:y0+ch, x0:x0+cw]
            return np.array(Image.fromarray(crop).resize((WIDTH, HEIGHT), Image.BILINEAR))

    elif effect == "pan_left":
        max_pan = nw - WIDTH
        def make_frame(t):
            x0 = int(max_pan * ease(t))
            y0 = (nh - HEIGHT) // 2
            return arr[y0:y0+HEIGHT, x0:x0+WIDTH]

    elif effect == "pan_right":
        max_pan = nw - WIDTH
        def make_frame(t):
            x0 = max_pan - int(max_pan * ease(t))
            y0 = (nh - HEIGHT) // 2
            return arr[y0:y0+HEIGHT, x0:x0+WIDTH]

    else:  # zoom_pan
        max_pan = (nw - WIDTH) // 2
        def make_frame(t):
            zm = 1.0 + 0.15 * ease(t)
            cw = max(1, int(WIDTH / zm)); ch = max(1, int(HEIGHT / zm))
            x0 = (nw - cw) // 2 + int(max_pan * ease(t))
            y0 = (nh - ch) // 2
            x0 = max(0, min(nw - cw, x0))
            crop = arr[y0:y0+ch, x0:x0+cw]
            return np.array(Image.fromarray(crop).resize((WIDTH, HEIGHT), Image.BILINEAR))

    base = VideoClip(make_frame, duration=duration).set_fps(FPS)

    # ── 文字疊加 ──────────────────────────────────────────
    if not text_main:
        return base

    try:
        from PIL import ImageDraw, ImageFont
        fL  = ImageFont.truetype(font_path, 76) if font_path else ImageFont.load_default()
        fS  = ImageFont.truetype(font_path, 44) if font_path else ImageFont.load_default()
        fWM = ImageFont.truetype(font_path, 26) if font_path else ImageFont.load_default()
    except Exception:
        fL = fS = fWM = ImageFont.load_default()

    # 預渲染文字 RGBA overlay
    ov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    # 底部漸層暗帶
    for y in range(HEIGHT * 2 // 3, HEIGHT):
        a = int(200 * (y - HEIGHT * 2 // 3) / (HEIGHT // 3))
        od.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, min(a, 200)))

    def _center(txt, fnt, y, col, draw_obj):
        try:
            bbox = draw_obj.textbbox((0, 0), txt, font=fnt)
            tw = bbox[2] - bbox[0]
        except Exception:
            tw = len(txt) * 38
        x = (WIDTH - tw) // 2
        draw_obj.text((x+2, y+2), txt, fill=(0,0,0,200), font=fnt)
        draw_obj.text((x, y),    txt, fill=col,           font=fnt)

    _center(text_main, fL, HEIGHT * 3 // 4 - 58, (255, 215, 0, 255), od)
    if text_sub:
        _center(text_sub, fS, HEIGHT * 3 // 4 + 36, (255, 255, 255, 220), od)
    od.text((WIDTH-22, HEIGHT-15), "Purrfectly cute",
            fill=(180,180,180,200), font=fWM, anchor="rb")

    ov_arr = np.array(ov)

    def overlay_frame(t):
        frame = base.get_frame(t).copy()
        bg  = Image.fromarray(frame).convert("RGBA")
        out = Image.alpha_composite(bg, Image.fromarray(ov_arr))
        return np.array(out.convert("RGB"))

    from moviepy.editor import VideoClip as VC
    return VC(overlay_frame, duration=duration).set_fps(FPS)


# ════════════════════════════════════════════════════════════
#  商品投影片（有商品圖 + 文字）
# ════════════════════════════════════════════════════════════
def product_slide(bg_bytes, prod_bytes, lines, font_path,
                  title=None, is_title=False, is_end=False, score=None):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import numpy as np

    # 背景（模糊商品圖 or 漸層）
    if bg_bytes:
        try:
            bg = Image.open(io.BytesIO(bg_bytes)).convert("RGB")
            iw, ih = bg.size
            r = max(WIDTH/iw, HEIGHT/ih)
            bg = bg.resize((int(iw*r)+2, int(ih*r)+2), Image.LANCZOS)
            x0 = (bg.width-WIDTH)//2; y0 = (bg.height-HEIGHT)//2
            bg = bg.crop((x0, y0, x0+WIDTH, y0+HEIGHT))
            bg = bg.filter(ImageFilter.GaussianBlur(radius=14))
            black = Image.new("RGB", (WIDTH, HEIGHT), (0,0,0))
            bg = Image.blend(bg, black, alpha=0.65)
        except Exception:
            bg = None
    if not bg_bytes or bg is None:
        bg = Image.new("RGB", (WIDTH, HEIGHT))
        from PIL import ImageDraw as ID2
        d = ID2.Draw(bg)
        for y in range(HEIGHT):
            t = y/HEIGHT
            d.line([(0,y),(WIDTH,y)],fill=(int(10+20*t),int(8+15*t),int(30+50*t)))

    try:
        fH  = ImageFont.truetype(font_path, 92) if font_path else ImageFont.load_default()
        fT  = ImageFont.truetype(font_path, 60) if font_path else ImageFont.load_default()
        fB  = ImageFont.truetype(font_path, 46) if font_path else ImageFont.load_default()
        fSM = ImageFont.truetype(font_path, 28) if font_path else ImageFont.load_default()
    except Exception:
        fH = fT = fB = fSM = ImageFont.load_default()

    draw = ImageDraw.Draw(bg)
    draw.text((WIDTH-25, HEIGHT-15), "Purrfectly cute",
              fill=(180,180,180), font=fSM, anchor="rb")

    # ── 標題 / 結尾 ─────────────────────────────────────
    if is_title or is_end:
        ov = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
        od = ImageDraw.Draw(ov)
        for y in range(HEIGHT//3, HEIGHT*2//3):
            a = int(210*(1-abs(y-HEIGHT//2)/(HEIGHT//6))); a=max(0,min(255,a))
            od.line([(0,y),(WIDTH,y)], fill=(0,0,0,a))
        bg = Image.alpha_composite(bg.convert("RGBA"), ov).convert("RGB")
        draw = ImageDraw.Draw(bg)
        y_pos = HEIGHT//2-115
        for i, line in enumerate(lines):
            font = fH if i==0 else fT
            try:
                bbox = draw.textbbox((0,0), line, font=font)
                tw = bbox[2]-bbox[0]
            except Exception:
                tw = len(line)*44
            x = (WIDTH-tw)//2
            draw.text((x+3, y_pos+3), line, fill=(0,0,0), font=font)
            col = (255,215,0) if i==0 else (255,255,255)
            draw.text((x, y_pos), line, fill=col, font=font)
            y_pos += 110
    else:
        # 左側遮罩
        tw_mask = int(WIDTH*0.58) if prod_bytes else WIDTH-60
        ov = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
        ImageDraw.Draw(ov).rectangle([0,0,tw_mask+45,HEIGHT], fill=(0,0,0,158))
        bg = Image.alpha_composite(bg.convert("RGBA"), ov).convert("RGB")
        draw = ImageDraw.Draw(bg)

        # 商品圖（右側）
        if prod_bytes:
            try:
                pi = Image.open(io.BytesIO(prod_bytes)).convert("RGB")
                pi.thumbnail((500,500), Image.LANCZOS)
                pw, ph = pi.size
                px = WIDTH-560; py = (HEIGHT-ph)//2
                bg.paste(Image.new("RGB",(pw+20,ph+20),(255,255,255)), (px-10,py-10))
                bg.paste(pi, (px+(500-pw)//2, py+(500-ph)//2))
                draw = ImageDraw.Draw(bg)
            except Exception:
                pass

        # 評分（若有）
        if score is not None:
            stars = "★"*score + "☆"*(5-score)
            draw.text((55, HEIGHT-68), f"評分：{stars}  {score}/5",
                      fill=(255,215,0), font=fSM)

        # 標題列
        y_pos = 48
        if title:
            try:
                bbox = draw.textbbox((0,0), title, font=fT)
                th = bbox[3]-bbox[1]
            except Exception:
                th = 64
            draw.rectangle([0, y_pos-10, tw_mask+45, y_pos+th+14], fill=(175,125,0))
            draw.text((52, y_pos), title, fill=(255,255,255), font=fT)
            y_pos += th+50

        for line in lines:
            if not line.strip(): y_pos+=20; continue
            col=(240,240,240)
            if line.startswith("✅"): col=(80,255,140)
            elif line.startswith("❌"): col=(255,100,100)
            elif line.startswith(("💰","👉","🔔","⭐","•")): col=(255,215,60)
            draw.text((56, y_pos+2), line, fill=(0,0,0), font=fB)
            draw.text((55, y_pos),   line, fill=col,     font=fB)
            y_pos += 68

    return np.array(bg)


# ════════════════════════════════════════════════════════════
#  Ken Burns（商品投影片用）
# ════════════════════════════════════════════════════════════
def kenburns(frame_arr, duration, z_s=1.0, z_e=1.06):
    from PIL import Image
    from moviepy.editor import VideoClip
    import numpy as np
    pil = Image.fromarray(frame_arr); w,h = pil.size
    def make_frame(t):
        p = t/duration; p = p*p*(3-2*p)
        zm = z_s+(z_e-z_s)*p
        nw,nh = int(w*zm),int(h*zm)
        rs = pil.resize((nw,nh),Image.BILINEAR)
        x0,y0 = (nw-w)//2,(nh-h)//2
        return np.array(rs.crop((x0,y0,x0+w,y0+h)))
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
#  場景腳本
# ════════════════════════════════════════════════════════════
def build_scenes(product: dict) -> list:
    name   = product.get("name","寵物商品")[:22]
    kw     = product.get("keyword","寵物用品")
    price  = product.get("price_twd","299")
    rating = product.get("rating","4.8")
    sold   = product.get("sold_monthly","1000")
    pt     = pet_type(kw)
    pet_zh = "貓咪" if pt=="cat" else "狗狗" if pt=="dog" else "毛孩"

    return [
        {"type":"broll","effect":"zoom_out",
         "text_main":f"你家{pet_zh}也有這困擾嗎？",
         "text_sub":"看完再決定！這次我幫你測了",
         "narration":(
             f"嘿！如果你也在幫{pet_zh}找好用的{kw}，"
             f"你絕對要看完這支影片！"
             f"今天我完整測試這款月銷{sold}件的熱門商品，"
             f"優點缺點一次全說，讓你買前不踩雷！"
         )},

        {"type":"product","title":"🎯 今日評測商品",
         "lines":[f"【{name}】",f"售價 NT$ {price}",
                  f"評分 {rating} / 5  {'⭐'*int(float(rating))}",f"月銷 {sold} 件  🔥"],
         "narration":(
             f"今天要評測的是「{name}」，"
             f"這款{kw}在蝦皮評分{rating}分，每個月賣掉{sold}件。"
             f"我知道你想問的是：這個東西真的好用嗎？值不值得買？"
             f"我直接告訴你我的真實感受，絕對不幫廠商說話！"
         )},

        {"type":"broll","effect":"pan_left",
         "text_main":"為什麼這麼多人買？",
         "text_sub":f"月銷 {sold} 件的秘密",
         "narration":(
             f"先說為什麼這麼多{pet_zh}飼主選擇這款。"
             f"月銷{sold}件不是偶然，代表很多人用過之後覺得好用才繼續買。"
             f"這類{kw}市場上選擇很多，能脫穎而出一定有原因，"
             f"我來告訴你是什麼。"
         )},

        {"type":"product","title":"🔍 外觀 & 品質細節",
         "lines":["• 包裝質感佳，超越同價位水準",
                  "• 材質通過安全認證，無毒無異味",
                  "• 設計符合寵物習性，一看就懂",
                  "• 適合不同體型，通用性強",
                  "• 清潔保養簡單不費力"],
         "narration":(
             f"先講外觀和品質，這兩點我特別在意。"
             f"拿到{name}第一眼，包裝很厚實，這個價格能有這個質感不多見。"
             f"材質有安全認證，沒有刺鼻的塑膠味——"
             f"這對家裡有{pet_zh}的人超重要，"
             f"因為牠們的嗅覺是我們的幾十倍，有異味根本不會靠近。"
             f"設計上也非常直覺，完全符合{pet_zh}的使用習慣。"
         )},

        {"type":"broll","effect":"zoom_in",
         "text_main":"✅ 真實測試結果",
         "text_sub":"接下來是我誠實的評價",
         "narration":(
             f"好，進入大家最想知道的部分——"
             f"我實際用了之後，有哪些讓我很滿意的地方？"
         )},

        {"type":"product","title":"✅ 真實優點（不業配）",
         "lines":["✅ 品質穩定，長期使用沒問題",
                  f"✅ {pet_zh}接受度極高，幾乎零適應期",
                  f"✅ NT$ {price} CP 值爆表",
                  "✅ 做工細緻，不像廉價品",
                  "✅ 理解為何回購率這麼高"],
         "narration":(
             f"說說讓我真的很滿意的地方。"
             f"最大的亮點是{pet_zh}接受度，"
             f"幾乎是零適應期，直接就喜歡上了。"
             f"這對我來說是最重要的指標，"
             f"因為再好的{kw}，{pet_zh}不接受就沒用。"
             f"品質方面，用了一段時間都沒有出現問題。"
             f"而且以{price}元這個價格，"
             f"你很難在市場上找到比這更划算的選擇。"
         )},

        {"type":"broll","effect":"pan_right",
         "text_main":"❌ 但這點要注意...",
         "text_sub":"我不幫廠商遮缺點",
         "narration":(
             f"當然，沒有什麼東西是完美的，"
             f"我也不是業配帳號，有缺點我一定說清楚。"
         )},

        {"type":"product","title":"❌ 需要注意的地方",
         "lines":["❌ 需定期清潔才能維持效果",
                  f"❌ 少數挑剔的{pet_zh}需 1-2 週適應",
                  "❌ 購買前確認尺寸符合你家毛孩",
                  "→ 初次使用建議循序漸進",
                  "→ 特殊狀況請先諮詢獸醫"],
         "narration":(
             f"需要注意的地方，我直說。"
             f"第一，這款{kw}需要定期清潔，"
             f"如果你比較懶得保養，效果會打折。"
             f"第二，少數非常挑剔的{pet_zh}可能需要一兩週適應，"
             f"別急，慢慢來。"
             f"最後提醒，買之前一定要確認尺寸適合你家{pet_zh}，"
             f"這個很多人會忽略。"
         )},

        {"type":"product","title":"💰 值不值得買？價格分析",
         "lines":[f"蝦皮現貨：NT$ {price}",
                  f"市場同類均價：NT$ {int(float(price)*1.3):.0f} 起",
                  f"省下：NT$ {int(float(price)*0.3):.0f}",
                  "","⭐ 推薦指數：★★★★☆  4.5/5",
                  "👉 購買連結在說明欄 ↓"],
         "score":4,
         "narration":(
             f"最後是最重要的——值不值得買？"
             f"「{name}」，蝦皮現在{price}元，"
             f"同類商品普遍要{int(float(price)*1.3):.0f}元起跳，"
             f"這個定價是同級裡偏低的。"
             f"如果你本來就有在考慮這類{kw}，"
             f"我認為這款是目前 CP 值最高的選擇之一。"
             f"購買連結放在說明欄，有蝦皮聯盟優惠，"
             f"直接點進去下單比自己搜尋划算！"
         )},

        {"type":"broll","effect":"zoom_pan",
         "text_main":f"總評：強力推薦 ⭐⭐⭐⭐",
         "text_sub":f"適合所有 {pet_zh} 飼主入手",
         "narration":(
             f"好了，「{name}」的完整評測就到這邊！"
             f"品質穩定、CP 值高、{pet_zh}接受度好，"
             f"是我目前{kw}類別裡最推薦的選擇。"
         )},

        {"type":"end","is_end":True,
         "lines":["喜歡記得按讚 👍","訂閱開通知 🔔 不錯過","Purrfectly cute 每週更新"],
         "narration":(
             f"如果這支影片對你有幫助，麻煩按個讚！"
             f"訂閱頻道開啟小鈴鐺，"
             f"我每週更新最新的寵物好物評測，"
             f"讓你不用踩雷、省時間省錢。"
             f"我們下週見！Bye bye！"
         )},
    ]


# ════════════════════════════════════════════════════════════
#  縮圖生成
# ════════════════════════════════════════════════════════════
def generate_thumbnail(product: dict, prod_img: bytes,
                       out_path: str, font_path: str):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    TW, TH = 1280, 720
    name  = product.get("name","")[:18]
    price = product.get("price_twd","")
    try:
        fBig = ImageFont.truetype(font_path, 88) if font_path else ImageFont.load_default()
        fMed = ImageFont.truetype(font_path, 52) if font_path else ImageFont.load_default()
        fSm  = ImageFont.truetype(font_path, 36) if font_path else ImageFont.load_default()
    except Exception:
        fBig = fMed = fSm = ImageFont.load_default()

    if prod_img:
        bg = Image.open(io.BytesIO(prod_img)).convert("RGB").resize((TW,TH),Image.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=7))
        bg = Image.blend(bg, Image.new("RGB",(TW,TH),(0,0,0)), alpha=0.55)
    else:
        bg = Image.new("RGB",(TW,TH),(20,10,50))

    # 商品圖右側（清晰）
    if prod_img:
        try:
            pi = Image.open(io.BytesIO(prod_img)).convert("RGB")
            pi.thumbnail((500,500),Image.LANCZOS)
            bw = Image.new("RGB",(pi.width+20,pi.height+20),(255,255,255))
            bg.paste(bw,(TW-pi.width-68,(TH-pi.height)//2-10))
            bg.paste(pi,(TW-pi.width-58,(TH-pi.height)//2))
        except Exception: pass

    draw = ImageDraw.Draw(bg)

    # 紅色大問句
    qtxt = "值不值得買？"
    try:
        bbox = draw.textbbox((0,0),qtxt,font=fBig); tw=bbox[2]-bbox[0]
    except Exception: tw=len(qtxt)*46
    x = 35
    draw.rectangle([x-15,55,x+tw+15,165], fill=(210,25,25))
    draw.text((x,62), qtxt, fill=(255,255,255), font=fBig)

    # 商品名（金色）
    draw.text((40,188), name, fill=(255,215,0), font=fMed)

    # 價格 badge
    draw.rectangle([40,262,270,330], fill=(255,75,0))
    draw.text((55,270), f"NT$ {price}", fill=(255,255,255), font=fSm)

    # 老實說 badge
    draw.rectangle([40,TH-105,238,TH-60], fill=(0,110,200))
    draw.text((52,TH-100), "老實說評測", fill=(255,255,255), font=fSm)

    # 頻道名
    draw.text((40,TH-52), "Purrfectly cute", fill=(180,180,180), font=fSm)

    bg.save(out_path, "JPEG", quality=95)
    print(f"  [Thumb] ✓ {out_path}")


# ════════════════════════════════════════════════════════════
#  主影片合成
# ════════════════════════════════════════════════════════════
def create_video(product: dict, output_path: str) -> float:
    from moviepy.editor import AudioFileClip, concatenate_videoclips

    font_path = find_font()
    scenes    = build_scenes(product)
    keyword   = product.get("keyword","寵物用品")
    name      = product.get("name","")

    print(f"  [Img] 抓取商品圖...")
    prod_img = get_product_img(keyword, name)

    print(f"  [Img] 預抓 B-roll 圖庫（{len([s for s in scenes if s['type']=='broll'])} 張）...")
    broll_imgs = fetch_broll_images(keyword, count=6)
    broll_idx  = 0

    clips = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, scene in enumerate(scenes):
            tp = scene.get("type","product")
            print(f"  ── 場景 {i+1}/{len(scenes)}  [{tp}]  {scene.get('title') or scene.get('text_main','')[:25]}")

            audio_path = f"{tmpdir}/a{i:02d}.mp3"
            tts(scene["narration"], audio_path)
            aud_dur = AudioFileClip(audio_path).duration

            # ── B-roll 場景 ──────────────────────────────
            if tp == "broll":
                total_dur = aud_dur + 0.5
                b_img = broll_imgs[broll_idx % len(broll_imgs)] if broll_imgs else None
                broll_idx += 1
                effect = scene.get("effect", MOTION_EFFECTS[i % len(MOTION_EFFECTS)])
                vclip = motion_clip(
                    b_img, total_dur, effect,
                    text_main=scene.get("text_main",""),
                    text_sub=scene.get("text_sub",""),
                    font_path=font_path,
                )

            # ── 結尾畫面 ─────────────────────────────────
            elif scene.get("is_end"):
                total_dur = aud_dur + 0.8
                slide = product_slide(prod_img, None, scene["lines"],
                                      font_path, is_end=True)
                vclip = kenburns(slide, total_dur, z_s=1.0, z_e=1.04)

            # ── 商品投影片 ───────────────────────────────
            else:
                total_dur = aud_dur + 0.6
                zoom_in = (i % 2 == 0)
                slide = product_slide(
                    prod_img, prod_img, scene.get("lines",[]),
                    font_path, title=scene.get("title"),
                    score=scene.get("score"),
                )
                vclip = kenburns(slide, total_dur,
                                 z_s=1.00 if zoom_in else 1.06,
                                 z_e=1.06 if zoom_in else 1.00)

            # 音軌
            aud = AudioFileClip(audio_path)
            vclip = vclip.set_audio(aud.subclip(0, min(aud.duration, total_dur)))

            # 轉場
            if i > 0:               vclip = vclip.crossfadein(0.35)
            if i < len(scenes)-1:   vclip = vclip.crossfadeout(0.35)

            clips.append(vclip)
            print(f"     ✓ {total_dur:.1f}s")

        total = sum(c.duration for c in clips)
        print(f"\n  [合成] 總長 {total:.0f}s（{total/60:.1f} 分），渲染中...")
        final = concatenate_videoclips(clips, method="compose", padding=-0.35)
        final.write_videofile(
            output_path, fps=FPS, codec="libx264",
            audio_codec="aac", bitrate="3500k",
            verbose=False, logger=None,
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
        print("[Video] 找不到文章摘要，跳過"); return []

    with open(files[0], encoding="utf-8") as f:
        articles = json.load(f)

    if not articles:
        try:
            from pipeline.config import PRODUCT_DATABASE
            today  = datetime.now().strftime("%Y%m%d")
            offset = int(hashlib.md5(today.encode()).hexdigest(),16) % len(PRODUCT_DATABASE)
            p = PRODUCT_DATABASE[offset]
            articles = [{"title":p["name"],"keyword":p["keyword"],
                         "price":str(p["price_twd"]),"rating":str(p["rating"]),"affiliate_url":""}]
        except Exception as e:
            print(f"[Video] 備用失敗：{e}"); return []

    date_str = datetime.now().strftime("%Y%m%d")
    a = articles[0]
    product = {
        "name":         a.get("title","寵物商品評測"),
        "keyword":      a.get("keyword","寵物用品"),
        "price_twd":    a.get("price","299"),
        "rating":       a.get("rating","4.8"),
        "sold_monthly": "1000+",
        "affiliate_url": a.get("affiliate_url",""),
    }

    out_vid   = str(VIDEOS_DIR / f"{date_str}_01.mp4")
    out_thumb = str(THUMBS_DIR / f"{date_str}_01.jpg")

    print(f"\n{'='*55}")
    print(f"  商品：{product['name'][:38]}")
    print(f"  關鍵字：{product['keyword']}")
    print(f"{'='*55}")

    try:
        dur = create_video(product, out_vid)
        print(f"\n  ✓ 影片：{out_vid}")
        print(f"  ✓ 長度：{dur:.0f}s（{dur/60:.1f} 分鐘）")

        fp = find_font()
        pi = get_product_img(product["keyword"], product["name"])
        if pi and fp:
            generate_thumbnail(product, pi, out_thumb, fp)

        kw = product["keyword"]
        return [{
            "path": out_vid, "thumb_path": out_thumb,
            "title": f"【老實說評測】{product['name'][:20]} 值不值得買？",
            "keyword": kw,
            "description": (
                f"今天完整評測「{product['name'][:30]}」！\n"
                f"評分 {product['rating']}/5，月銷 {product['sold_monthly']} 件。\n\n"
                f"🛒 蝦皮優惠連結：{product['affiliate_url']}\n"
                f"📖 完整評測文章：https://a12012300-ux.github.io\n\n"
                f"⏱ 時間章節：\n"
                f"0:00 你也遇過這困擾嗎？\n"
                f"0:30 今日評測商品介紹\n"
                f"1:10 外觀 & 品質細節\n"
                f"1:50 真實優點（不業配）\n"
                f"2:30 需要注意的地方\n"
                f"3:10 價格分析值不值得？\n"
                f"3:45 最終評分 & 推薦\n\n"
                f"#Purrfectlycute #{kw} #寵物推薦 #台灣寵物 #寵物評測 #老實說"
            ),
        }]
    except Exception as e:
        print(f"  [Error] {e}")
        import traceback; traceback.print_exc()
        return []


if __name__ == "__main__":
    run_video_maker()
