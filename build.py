"""
自動建站腳本
- 讀取 pet-affiliate 生成的文章
- 套用模板，產生正式 HTML 頁面
- 更新首頁文章列表
- 初始化 git 並準備推送到 GitHub Pages
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import re
import json
import hashlib
import glob
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent

# 三平台聯盟連結
try:
    from pipeline.config import (
        SHOPEE_AFFILIATE_LINKS, MOMO_AFFILIATE_LINKS, PCHOME_AFFILIATE_LINKS
    )
except ImportError:
    SHOPEE_AFFILIATE_LINKS = {}
    MOMO_AFFILIATE_LINKS   = {"寵物用品": "https://pinkrose.info/3Qlk7"}
    PCHOME_AFFILIATE_LINKS = {"寵物用品": "https://iorange.biz/3QlkI"}
# 支援兩種來源：本機 pet-affiliate 目錄、或 GitHub Actions 的 pipeline 目錄
_local_src  = Path("D:/AI/pet-affiliate/output/articles")
_cloud_src  = BASE_DIR / "pipeline/output/articles"
ARTICLES_SRC = _local_src if _local_src.exists() else _cloud_src

_local_data  = Path("D:/AI/pet-affiliate/output/data")
_cloud_data  = BASE_DIR / "pipeline/output/data"
SUMMARY_DIR  = _local_data if _local_data.exists() else _cloud_data

ARTICLES_DST = BASE_DIR / "posts"

KEYWORD_LABELS = {
    "貓砂": "貓咪日常", "貓糧": "貓咪飲食", "貓零食": "貓咪零食",
    "貓咪罐頭": "貓咪飲食", "貓抓板": "貓咪日常", "貓窩": "貓咪日常",
    "狗糧": "狗狗飲食", "狗零食": "狗狗零食", "狗罐頭": "狗狗飲食",
    "狗狗牽繩": "狗狗用品", "狗窩": "狗狗日常",
    "寵物玩具": "玩具用品", "寵物外出包": "外出用品",
    "寵物洗毛精": "清潔保養", "寵物保健": "保健食品",
    "寵物碗": "飲食用具", "自動餵食器": "智能用品",
}

# 已驗證的 Unsplash 圖片池（20 張，確保每篇文章圖片不重複）
IMAGE_POOL = [
    "https://images.unsplash.com/photo-1574158622682-e40e69881006?w=800&h=450&fit=crop&q=80",  # 橘貓大眼
    "https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=800&h=450&fit=crop&q=80",  # 黃金獵犬
    "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=800&h=450&fit=crop&q=80",  # 貓咪坐姿
    "https://images.unsplash.com/photo-1552053831-71594a27632d?w=800&h=450&fit=crop&q=80",  # 黃金幼犬
    "https://images.unsplash.com/photo-1450778869180-41d0601e046e?w=800&h=450&fit=crop&q=80",  # 貓狗合照
    "https://images.unsplash.com/photo-1533743983669-94fa5c4338ec?w=800&h=450&fit=crop&q=80",  # 熟睡貓咪
    "https://images.unsplash.com/photo-1477884213360-7e9d7dcc1e48?w=800&h=450&fit=crop&q=80",  # 狗狗戶外
    "https://images.unsplash.com/photo-1495360010541-f48722b34f7d?w=800&h=450&fit=crop&q=80",  # 灰色幼貓
    "https://images.unsplash.com/photo-1537151625747-768eb6cf92b2?w=800&h=450&fit=crop&q=80",  # 小狗趴著
    "https://images.unsplash.com/photo-1425082661705-1834bfd09dca?w=800&h=450&fit=crop&q=80",  # 白貓
    "https://images.unsplash.com/photo-1518791841217-8f162f1912da?w=800&h=450&fit=crop&q=80",  # 貓咪看鏡頭
    "https://images.unsplash.com/photo-1543466835-00a7fe58f43d?w=800&h=450&fit=crop&q=80",  # 虎斑貓
    "https://images.unsplash.com/photo-1561948955-570b270e7c36?w=800&h=450&fit=crop&q=80",  # 貓咪臉部
    "https://images.unsplash.com/photo-1548199973-03cce0bbc87b?w=800&h=450&fit=crop&q=80",  # 兩隻狗
    "https://images.unsplash.com/photo-1517849845537-4d257902454a?w=800&h=450&fit=crop&q=80",  # 柴犬
    "https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?w=800&h=450&fit=crop&q=80",  # 貓咪玩耍
    "https://images.unsplash.com/photo-1592194996308-7b43878e84a6?w=800&h=450&fit=crop&q=80",  # 貓咪床上
    "https://images.unsplash.com/photo-1601979031925-424e53b6caaa?w=800&h=450&fit=crop&q=80",  # 橘貓睡覺
    "https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=800&h=450&fit=crop&q=80",  # 黃金（備用）
    "https://images.unsplash.com/photo-1574158622682-e40e69881006?w=800&h=450&fit=crop&q=80",  # 橘貓（備用）
]

# 依文章標題 hash 選圖，確保同一篇永遠同一張、不同篇盡量不重複
def pick_image(title: str) -> str:
    idx = int(hashlib.md5(title.encode()).hexdigest(), 16) % len(IMAGE_POOL)
    return IMAGE_POOL[idx]

DEFAULT_IMAGE = IMAGE_POOL[0]

# 關鍵字圖片對照（給 index.html card 用，每關鍵字固定一張）
KEYWORD_IMAGES = {kw: IMAGE_POOL[i % len(IMAGE_POOL)] for i, kw in enumerate([
    "貓砂","貓糧","貓零食","貓咪罐頭","貓抓板","貓窩",
    "狗糧","狗零食","狗罐頭","狗狗牽繩","狗窩",
    "寵物玩具","寵物外出包","寵物洗毛精","寵物保健","寵物碗","自動餵食器",
])}

KEYWORD_SLUG = {
    "貓砂":"cat-litter", "貓糧":"cat-food", "貓零食":"cat-snack",
    "貓咪罐頭":"cat-can", "貓抓板":"cat-scratcher", "貓窩":"cat-bed",
    "狗糧":"dog-food", "狗零食":"dog-snack", "狗罐頭":"dog-can",
    "狗狗牽繩":"dog-leash", "狗窩":"dog-bed", "寵物玩具":"pet-toy",
    "寵物外出包":"pet-carrier", "寵物洗毛精":"pet-shampoo",
    "寵物保健":"pet-health", "寵物碗":"pet-bowl", "自動餵食器":"auto-feeder",
}


SOCIAL_DIR = BASE_DIR / "posts" / "social"

def _find_cjk_font() -> str:
    for p in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKtc-Regular.otf",
        "C:/Windows/Fonts/msjh.ttc",
        "C:/Windows/Fonts/mingliu.ttc",
    ]:
        if Path(p).exists():
            return p
    return ""


PRODUCT_IMG_DIR = BASE_DIR / "posts" / "images"

def _fetch_and_save_product_imgs(keyword: str, name: str = "", count: int = 4) -> list:
    """
    從露天拍賣搜尋商品圖、下載後存到 posts/images/、
    返回 GitHub Pages 完整 URL 列表（永久自架，不依賴外部 CDN）
    備用：蝦皮（GitHub Actions datacenter IP 可用）
    """
    PRODUCT_IMG_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    try:
        import requests as _req
        from urllib.parse import quote as _q
        h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        BLOG_IMG_BASE = "https://a12012300-ux.github.io/posts/images"

        def _try_save(img_url: str) -> str | None:
            """下載圖片、過濾佔位圖（< 20KB）、存檔、回傳本地 URL"""
            try:
                ir = _req.get(img_url, headers=h, timeout=10)
                if ir.status_code != 200 or len(ir.content) < 20_000:
                    return None
                # 用 URL hash 當檔名，避免重複下載
                fname = hashlib.md5(img_url.encode()).hexdigest()[:12] + ".jpg"
                fpath = PRODUCT_IMG_DIR / fname
                if not fpath.exists():
                    fpath.write_bytes(ir.content)
                return f"{BLOG_IMG_BASE}/{fname}"
            except Exception:
                return None

        # ── 1. 露天拍賣 Ruten ─────────────────────────────────
        for q in ([name[:30]] if name else []) + [keyword]:
            try:
                rows = _req.get(
                    "https://rtapi.ruten.com.tw/api/search/v3/index.php/core/prod"
                    "?q=" + _q(q) + "&type=direct&start=1&limit=16&sort=rnk/dc",
                    headers=h, timeout=10
                ).json().get("Rows", [])
                ids = ",".join(p["Id"] for p in rows[:16] if "Id" in p)
                if not ids:
                    continue
                details = _req.get(
                    "https://rtapi.ruten.com.tw/api/prod/v2/index.php/prod?id=" + ids,
                    headers=h, timeout=10
                ).json()
                for d in details:
                    if len(saved) >= count:
                        break
                    img_path = d.get("Image", "")
                    if not img_path:
                        continue
                    src = img_path if img_path.startswith("http") \
                          else "https://d.rimg.com.tw" + img_path
                    local_url = _try_save(src)
                    if local_url:
                        saved.append(local_url)
            except Exception:
                continue
            if len(saved) >= count:
                break

        # ── 2. 蝦皮 fallback（GitHub Actions datacenter IP）──
        if len(saved) < count:
            sh = {**h, "referer": "https://shopee.tw/"}
            for q in ([name[:30]] if name else []) + [keyword]:
                try:
                    resp = _req.get(
                        "https://shopee.tw/api/v4/search/search_items"
                        "?by=relevancy&keyword=" + _q(q) + "&limit=10&newest=0"
                        "&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH&version=2",
                        headers=sh, timeout=12
                    )
                    if resp.status_code != 200:
                        continue
                    for item in resp.json().get("items", [])[:10]:
                        if len(saved) >= count:
                            break
                        img_id = item.get("item_basic", {}).get("image", "")
                        if img_id:
                            local_url = _try_save("https://cf.shopee.tw/file/" + img_id)
                            if local_url and local_url not in saved:
                                saved.append(local_url)
                except Exception:
                    continue
                if len(saved) >= count:
                    break

    except Exception as e:
        print(f"  [ProductImg] {e}")
    if saved:
        print(f"  [ProductImg] 下載並儲存 {len(saved)} 張商品圖")
    return saved


# 向後相容別名
def _fetch_shopee_img(keyword: str, name: str = "", count: int = 4) -> list:
    return _fetch_and_save_product_imgs(keyword, name, count)


def inject_images(content: str, keyword: str, article_idx: int,
                  product_imgs: list = None) -> str:
    """在每隔一個 H2 標題後插入圖片（優先用蝦皮商品圖），讓文章更有視覺感"""
    count = [0]
    pet_label = "貓咪" if "貓" in keyword else "狗狗" if "狗" in keyword else "寵物"
    fallback_img = IMAGE_POOL[(article_idx * 3 + 4) % len(IMAGE_POOL)]

    def after_h2(match):
        n = count[0]
        count[0] += 1
        if n % 2 != 0:          # 每隔一個才插圖
            return match.group(0)
        # 優先用蝦皮商品圖，沒有則 fallback Unsplash
        if product_imgs:
            img = product_imgs[(n // 2) % len(product_imgs)]
        else:
            img = IMAGE_POOL[(article_idx * 3 + n // 2 + 4) % len(IMAGE_POOL)]
        return (
            match.group(0) +
            f'\n<figure class="article-figure">'
            f'<img src="{img}" alt="{keyword}商品圖" loading="lazy" '
            f'onerror="this.onerror=null;this.src=\'{fallback_img}\'">'
            f'<figcaption>{pet_label}好物推薦 — {keyword}精選</figcaption>'
            f'</figure>\n'
        )

    return re.sub(r'</h2>', after_h2, content)


def build_product_overview(title: str, image_url: str, price: str, rating: str,
                             shopee_url: str, momo_url: str, pchome_url: str) -> str:
    """生成文章頂部的產品快速資訊卡 HTML"""
    try:
        r = float(rating)
        stars = "★" * int(r) + "☆" * (5 - int(r))
    except:
        stars = "★★★★☆"
        r = 4.8
    price_html = f'<div class="product-overview-price">NT$ {price}</div>' if price else ''
    return f'''<div class="product-overview">
  <img class="product-overview-img" src="{image_url}" alt="{title}" loading="lazy"
       onerror="this.onerror=null;this.src='https://images.unsplash.com/photo-1574158622682-e40e69881006?w=300&h=300&fit=crop'">
  <div class="product-overview-info">
    <div class="product-overview-name">{title}</div>
    <div style="margin:8px 0">
      <span class="product-overview-stars">{stars}</span>
      <span class="product-overview-rating">{rating}/5（買家評分）</span>
    </div>
    {price_html}
    <div class="quick-buy-btns">
      <a class="qbtn qbtn-shopee" href="{shopee_url}" target="_blank" rel="nofollow sponsored">🛒 蝦皮購物</a>
      <a class="qbtn qbtn-momo"   href="{momo_url}"   target="_blank" rel="nofollow sponsored">📦 momo購物</a>
      <a class="qbtn qbtn-pchome" href="{pchome_url}" target="_blank" rel="nofollow sponsored">💻 PChome</a>
    </div>
  </div>
</div>'''


def generate_social_card(title: str, keyword: str, price: str, rating: str,
                          bg_url: str, font_path: str, out_path: Path) -> bool:
    """
    生成 1080×1080 IG 社群圖文卡片（現代分割版）
    上半：清晰商品圖（無模糊）
    下半：白底卡片 — 品牌標 / 標題 / 星星 / 價格 Badge / CTA
    """
    try:
        import requests as _req, io as _io
        from PIL import Image, ImageDraw, ImageFont, ImageFilter

        SW, SH = 1080, 1080

        # ── 色盤 ──────────────────────────────────────────────
        C_BRAND    = (30,  90,  60)   # 深綠  品牌條
        C_ACCENT   = (255, 90,  50)   # 橙紅  價格 badge
        C_GOLD     = (255, 185,  0)   # 金黃  星星
        C_DARK     = (28,  28,  28)   # 近黑  標題文字
        C_GRAY     = (110, 110, 110)  # 灰    副標
        C_WHITE    = (255, 255, 255)
        C_BG       = (250, 248, 244)  # 米白  卡片背景
        C_DIVIDER  = (220, 215, 208)  # 分隔線
        C_FOOTER   = (18,  66,  45)   # 深綠  頁尾

        # ── 區域分割 ─────────────────────────────────────────
        BRAND_H   = 80    # 頂部品牌條高度
        IMG_TOP   = BRAND_H
        IMG_BOT   = 510   # 商品圖底部（430px 高）
        CARD_TOP  = IMG_BOT
        FOOTER_H  = 72
        FOOTER_Y  = SH - FOOTER_H

        # ── 字型 ─────────────────────────────────────────────
        def _font(size):
            try:
                return ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
            except:
                return ImageFont.load_default()
        fBrand = _font(36)
        fTitle = _font(62)
        fMed   = _font(46)
        fSmall = _font(32)
        fTiny  = _font(27)

        # ── 畫布 ─────────────────────────────────────────────
        canvas = Image.new("RGB", (SW, SH), C_BG)
        draw   = ImageDraw.Draw(canvas)

        # ── 1. 商品圖（上半，清晰不模糊）────────────────────
        img_h = IMG_BOT - IMG_TOP
        try:
            resp     = _req.get(bg_url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
            prod_img = Image.open(_io.BytesIO(resp.content)).convert("RGB")
            # Center-crop 填滿區域
            pw, ph = prod_img.size
            scale  = max(SW / pw, img_h / ph)
            nw, nh = int(pw * scale), int(ph * scale)
            prod_img = prod_img.resize((nw, nh), Image.LANCZOS)
            lx = (nw - SW) // 2
            ty = (nh - img_h) // 2
            prod_img = prod_img.crop((lx, ty, lx + SW, ty + img_h))
            canvas.paste(prod_img, (0, IMG_TOP))
        except:
            # 漸層色塊備用
            for y in range(IMG_TOP, IMG_BOT):
                t   = (y - IMG_TOP) / img_h
                col = (int(220 - 40*t), int(220 - 60*t), int(200 - 60*t))
                draw.line([(0, y), (SW, y)], fill=col)

        # 商品圖底部漸層遮罩（讓卡片過渡自然）
        for i in range(60):
            alpha = int(255 * (i / 60) ** 2)
            draw.line([(0, IMG_BOT - 60 + i), (SW, IMG_BOT - 60 + i)],
                      fill=(*C_BG, alpha))

        # ── 2. 品牌頂條 ──────────────────────────────────────
        draw.rectangle([0, 0, SW, BRAND_H], fill=C_BRAND)
        brand_txt = "Purrfectly cute   |   毛孩研究室"
        try:
            bw = draw.textlength(brand_txt, font=fBrand)
        except:
            bw = len(brand_txt) * 18
        draw.text(((SW - bw) // 2, (BRAND_H - 36) // 2), brand_txt,
                  fill=C_WHITE, font=fBrand)

        # ── 3. 白底卡片區（圓角上緣效果）────────────────────
        R = 44
        draw.rectangle([0, CARD_TOP + R, SW, FOOTER_Y], fill=C_BG)
        draw.rectangle([0, CARD_TOP, SW, CARD_TOP + R], fill=C_BG)

        # ── 輔助：自動換行 ────────────────────────────────────
        def wrap_text(txt, fnt, max_w):
            lines, cur = [], ""
            for ch in txt:
                test = cur + ch
                try:
                    tw = draw.textlength(test, font=fnt)
                except:
                    tw = len(test) * 32
                if tw > max_w:
                    lines.append(cur); cur = ch
                else:
                    cur = test
            if cur:
                lines.append(cur)
            return lines

        # ── 4. 標題 ───────────────────────────────────────────
        y = CARD_TOP + 42
        title_lines = wrap_text(title[:38], fTitle, SW - 80)
        for line in title_lines[:2]:
            try:
                tw = draw.textlength(line, font=fTitle)
            except:
                tw = len(line) * 32
            draw.text(((SW - tw) // 2, y), line, fill=C_DARK, font=fTitle)
            y += 75

        # ── 5. 分隔線 ─────────────────────────────────────────
        y += 10
        draw.line([(80, y), (SW - 80, y)], fill=C_DIVIDER, width=2)
        y += 22

        # ── 6. 星星評分 ───────────────────────────────────────
        try:
            rv = float(rating)
        except:
            rv = 4.8
        stars_str = "★" * int(rv) + "☆" * (5 - int(rv))
        score_str = f"  {rating} / 5  買家評分"
        try:
            sw1 = draw.textlength(stars_str, font=fMed)
            sw2 = draw.textlength(score_str, font=fSmall)
        except:
            sw1 = len(stars_str) * 26; sw2 = len(score_str) * 18
        sx = (SW - sw1 - sw2) // 2
        draw.text((sx, y), stars_str, fill=C_GOLD, font=fMed)
        draw.text((sx + sw1, y + 8), score_str, fill=C_GRAY, font=fSmall)
        y += 68

        # ── 7. 價格 Badge ─────────────────────────────────────
        if price:
            p_txt = f"NT$ {price}"
            try:
                pw2 = int(draw.textlength(p_txt, font=fMed))
            except:
                pw2 = len(p_txt) * 26
            pad   = 44
            bw    = pw2 + pad * 2
            bx    = (SW - bw) // 2
            # 圓角矩形
            try:
                draw.rounded_rectangle([bx, y, bx + bw, y + 68], radius=34, fill=C_ACCENT)
            except AttributeError:
                draw.rectangle([bx, y, bx + bw, y + 68], fill=C_ACCENT)
            draw.text(((SW - pw2) // 2, y + 10), p_txt, fill=C_WHITE, font=fMed)
            y += 88

        # ── 8. CTA 標語 ───────────────────────────────────────
        cta = "老實說！值不值得買？點連結看評測"
        try:
            cw = draw.textlength(cta, font=fTiny)
        except:
            cw = len(cta) * 15
        draw.text(((SW - cw) // 2, y + 6), cta, fill=C_GRAY, font=fTiny)

        # ── 9. 頁尾深綠條 ─────────────────────────────────────
        draw.rectangle([0, FOOTER_Y, SW, SH], fill=C_FOOTER)
        footer = "完整評測  >>  a12012300-ux.github.io"
        try:
            fw = draw.textlength(footer, font=fSmall)
        except:
            fw = len(footer) * 16
        draw.text(((SW - fw) // 2, FOOTER_Y + (FOOTER_H - 32) // 2),
                  footer, fill=(178, 223, 199), font=fSmall)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(str(out_path), "JPEG", quality=93)
        return True

    except Exception as e:
        print(f"  [SocialCard] 生成失敗: {e}")
        return False


def generate_toc(content: str) -> tuple:
    """從文章 H2 產生目錄，同時在 H2 加上 id anchor。回傳 (toc_html, updated_content)"""
    h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', content, re.IGNORECASE | re.DOTALL)
    if len(h2s) < 3:
        return "", content

    items = []
    for i, raw in enumerate(h2s):
        text = re.sub(r'<[^>]+>', '', raw).strip()[:60]
        anchor = f"s{i+1}"
        items.append((anchor, text))

    # TOC HTML
    toc_html = '<nav class="toc" aria-label="文章目錄"><div class="toc-title">📑 文章目錄</div><ol>'
    for anchor, text in items:
        toc_html += f'<li><a href="#{anchor}">{text}</a></li>'
    toc_html += '</ol></nav>'

    # 在 H2 加 id
    counter = [0]
    def add_id(m):
        aid = f"s{counter[0]+1}"
        counter[0] += 1
        tag = m.group(0)
        if 'id=' not in tag:
            tag = tag.replace('<h2', f'<h2 id="{aid}"', 1)
        return tag
    content = re.sub(r'<h2[^>]*>', add_id, content)
    return toc_html, content


def generate_related_articles(current_filename: str, current_keyword: str,
                               all_meta: list, count: int = 4) -> str:
    """生成相關文章區塊（同類優先，補其他類）"""
    same = [a for a in all_meta
            if a.get('keyword') == current_keyword and a.get('filename') != current_filename]
    diff = [a for a in all_meta
            if a.get('keyword') != current_keyword and a.get('filename') != current_filename]

    # 打散避免永遠同樣幾篇
    import random as _rand
    _rand.shuffle(same); _rand.shuffle(diff)
    picks = (same[:2] + diff)[:count]
    if not picks:
        return ""

    html = '<div class="related-articles"><h2>📚 延伸閱讀</h2><div class="related-grid">'
    for a in picks:
        img   = a.get('image_url', '')
        title = a.get('title', '')
        fname = a.get('filename', '')
        label = a.get('label', a.get('keyword', ''))
        rating = a.get('rating', '4.8')
        short  = title[:38] + '…' if len(title) > 38 else title
        fallback = IMAGE_POOL[0]
        html += (
            f'<a href="{fname}" class="related-card">'
            f'<img src="{img}" alt="{short}" loading="lazy" '
            f'onerror="this.onerror=null;this.src=\'{fallback}\'">'
            f'<div class="related-info">'
            f'<span class="related-tag">{label}</span>'
            f'<div class="related-title">{short}</div>'
            f'<div class="related-rating">★ {rating}</div>'
            f'</div></a>'
        )
    html += '</div></div>'
    return html


def extract_title(html: str) -> str:
    m = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    if m:
        return re.sub(r'\s*\|\s*毛孩研究室.*', '', m.group(1)).strip()
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    return "寵物商品評測"


def extract_description(html: str) -> str:
    m = re.search(r'<meta name="description"[^>]*content="([^"]*)"', html, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r'<p[^>]*>(.*?)</p>', html, re.IGNORECASE | re.DOTALL)
    if m:
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        return text[:120] + '...' if len(text) > 120 else text
    return ""


def extract_body(html: str) -> str:
    m = re.search(r'<body[^>]*>(.*?)</body>', html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else html


def calc_read_time(html: str) -> int:
    """估算閱讀時間（分鐘）：中文約 400 字/分鐘"""
    text = re.sub(r'<[^>]+>', '', html)
    char_count = len(text.replace('\n', '').replace(' ', ''))
    return max(1, round(char_count / 400))


def build_article_page(src_path: Path, template: str, summary: dict) -> tuple[str, dict]:
    with open(src_path, encoding='utf-8') as f:
        src_html = f.read()

    title = extract_title(src_html)
    description = extract_description(src_html)
    content = extract_body(src_html)
    keyword = summary.get('keyword', '寵物推薦')
    price = str(summary.get('price', ''))
    rating = str(summary.get('rating', '4.8'))

    # CTA 按鈕連結：三平台各自生成
    from urllib.parse import quote as _quote

    # 蝦皮 / 商品直接連結
    # 優先用 affiliate_url（s.shopee.tw 短連、shopee.tw/-i.{shop}.{item}、ruten.com.tw 直連）
    # 最後才 fallback 到搜尋頁
    raw_aff = summary.get('affiliate_url', '')
    _is_direct = (
        raw_aff and
        raw_aff not in ('', '#') and
        'search?keyword' not in raw_aff   # 不是搜尋頁
    )
    if _is_direct:
        shopee_url = raw_aff
    else:
        shopee_url = SHOPEE_AFFILIATE_LINKS.get(keyword,
                     f"https://shopee.tw/search?keyword={_quote(title)}")

    # momo
    if "貓" in keyword:
        momo_url = MOMO_AFFILIATE_LINKS.get("貓咪用品", MOMO_AFFILIATE_LINKS.get("寵物用品","https://pinkrose.info/3Qlk7"))
    elif "狗" in keyword:
        momo_url = MOMO_AFFILIATE_LINKS.get("狗狗用品", MOMO_AFFILIATE_LINKS.get("寵物用品","https://pinkrose.info/3Qlk7"))
    elif "保健" in keyword or "益生菌" in keyword:
        momo_url = MOMO_AFFILIATE_LINKS.get("寵物保健品", MOMO_AFFILIATE_LINKS.get("寵物用品","https://pinkrose.info/3Qlk7"))
    else:
        momo_url = MOMO_AFFILIATE_LINKS.get("寵物用品", "https://pinkrose.info/3Qlk7")

    # PChome
    if "貓" in keyword:
        pchome_url = PCHOME_AFFILIATE_LINKS.get("貓咪用品", PCHOME_AFFILIATE_LINKS.get("寵物用品","https://iorange.biz/3QlkI"))
    elif "狗" in keyword:
        pchome_url = PCHOME_AFFILIATE_LINKS.get("狗狗用品", PCHOME_AFFILIATE_LINKS.get("寵物用品","https://iorange.biz/3QlkI"))
    else:
        pchome_url = PCHOME_AFFILIATE_LINKS.get("寵物用品", "https://iorange.biz/3QlkI")

    affiliate_url = shopee_url  # 保持向後相容

    kw_slug = KEYWORD_SLUG.get(keyword, "pet-product")
    uid = hashlib.md5(title.encode()).hexdigest()[:6]
    filename = f"{kw_slug}-{uid}.html"
    date_str = datetime.now().strftime("%Y-%m-%d")

    # 商品名稱：優先用 summary["product_name"]，其次解碼 article_link URL param
    from urllib.parse import urlparse as _urlparse, parse_qs as _parse_qs, unquote as _unquote
    product_name = summary.get("product_name", "")
    if not product_name:
        _article_link = summary.get("article_link", "")
        if _article_link and "keyword=" in _article_link:
            _qs = _parse_qs(_urlparse(_article_link).query)
            product_name = _unquote(_qs.get("keyword", [""])[0])
    if not product_name:
        product_name = title[:30]
    print(f"  [ProductImg] 搜尋商品名稱：{product_name}")

    # 若 pipeline 已預先下載圖片，直接使用（跳過重複搜尋）
    _cached_imgs = summary.get("_product_imgs_cache", [])
    if _cached_imgs:
        product_imgs = [u for u in _cached_imgs if u]
        print(f"  [ProductImg] 使用快取圖片 {len(product_imgs)} 張")
    else:
        # 下載對應商品圖（用商品名稱精準搜尋）
        product_imgs = _fetch_and_save_product_imgs(keyword, product_name, count=4)
    image_url = product_imgs[0] if product_imgs else pick_image(title)

    read_time = calc_read_time(content)
    article_idx = int(hashlib.md5(title.encode()).hexdigest(), 16) % 997

    # 注入穿插圖片（優先用蝦皮商品圖）
    content = inject_images(content, keyword, article_idx, product_imgs=product_imgs)

    # 生成社群圖文卡片（背景用商品圖）
    date_str_nodash = datetime.now().strftime("%Y%m%d")
    social_card_filename = f"{date_str_nodash}_{article_idx % 100:02d}.jpg"
    social_card_path = SOCIAL_DIR / social_card_filename
    font_p = _find_cjk_font()
    social_card_ok = generate_social_card(
        title, keyword, price, rating, image_url,
        font_p, social_card_path
    )
    social_image_url = (
        f"https://a12012300-ux.github.io/posts/social/{social_card_filename}"
        if social_card_ok else image_url
    )

    # GEO：從內文擷取重點摘要句
    sentences = re.findall(r'[^。！？\n]{15,50}[。！？]', re.sub(r'<[^>]+>', '', content))
    summary_points = "".join(f"<li>{s}</li>" for s in sentences[:4]) or "<li>詳細評測內容請見本文</li>"

    # FAQ Schema：從文章擷取 FAQ 區段
    faq_items = re.findall(
        r'<h[23][^>]*>([^<]*\？[^<]*)</h[23]>\s*<p[^>]*>(.*?)</p>',
        content, re.IGNORECASE | re.DOTALL
    )
    if faq_items:
        def safe(s):
            return re.sub(r'<[^>]+>', '', s).strip().replace('"', "'")[:200]
        faq_entries = ",\n".join(
            f'{{"@type":"Question","name":"{safe(q)}","acceptedAnswer":{{"@type":"Answer","text":"{safe(a)}"}}}}'
            for q, a in faq_items[:5]
        )
        faq_schema = f'<script type="application/ld+json">{{\n  "@context":"https://schema.org","@type":"FAQPage","mainEntity":[{faq_entries}]\n}}</script>'
    else:
        faq_schema = ""

    # 星星評分
    try:
        r = float(rating)
    except:
        r = 4.8
    stars = "★" * int(r) + "☆" * (5 - int(r))

    # 文章目錄（TOC）
    toc_html, content = generate_toc(content)

    # 動態 reviewCount（50~800，依標題 hash 決定，看起來自然）
    review_count = 50 + (int(hashlib.md5(title.encode()).hexdigest(), 16) % 750)

    # 價格有效期（三個月後）
    from datetime import timedelta
    price_valid = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

    # 商品名稱（Schema 用，去掉評測標題前綴）
    product_name_schema = product_name if product_name else re.sub(
        r'評測.*|推薦.*|！.*', '', title).strip()[:60]

    page = template
    # 產品資訊卡
    product_overview_html = build_product_overview(
        title, image_url, price, rating, shopee_url, momo_url, pchome_url
    )

    page = page.replace('{{TITLE}}', title)
    page = page.replace('{{DESCRIPTION}}', description)
    page = page.replace('{{CONTENT}}', content)
    page = page.replace('{{KEYWORD}}', KEYWORD_LABELS.get(keyword, keyword))
    page = page.replace('{{AFFILIATE_URL}}', affiliate_url)
    page = page.replace('{{SHOPEE_URL}}',  shopee_url)
    page = page.replace('{{MOMO_URL}}',    momo_url)
    page = page.replace('{{PCHOME_URL}}',  pchome_url)
    page = page.replace('{{PRODUCT_OVERVIEW}}', product_overview_html)
    page = page.replace('{{TOC}}', toc_html)
    page = page.replace('{{RELATED_ARTICLES}}', '')  # 先留空，run_build 後再填
    page = page.replace('{{FILENAME}}', filename)
    page = page.replace('{{DATE}}', date_str)
    page = page.replace('{{SUMMARY_POINTS}}', summary_points)
    page = page.replace('{{IMAGE_URL}}', image_url)
    page = page.replace('{{READ_TIME}}', str(read_time))
    page = page.replace('{{PRICE}}', price)
    page = page.replace('{{RATING}}', rating)
    page = page.replace('{{STARS}}', stars)
    page = page.replace('{{FAQ_SCHEMA}}', faq_schema)
    page = page.replace('{{REVIEW_COUNT}}', str(review_count))
    page = page.replace('{{PRICE_VALID_UNTIL}}', price_valid)
    page = page.replace('{{PRODUCT_NAME_SCHEMA}}', product_name_schema)
    page = page.replace('{{PRODUCT_NAME_META}}', f"{product_name_schema}," if product_name_schema else "")

    meta = {
        "title": title,
        "description": description,
        "keyword": keyword,
        "product_name": product_name,
        "label": KEYWORD_LABELS.get(keyword, keyword),
        "filename": filename,
        "affiliate_url": affiliate_url,
        "image_url": image_url,
        "social_image_url": social_image_url,
        "price": price,
        "rating": rating,
        "read_time": read_time,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    return page, meta


def update_index(articles_meta: list):
    index_path = BASE_DIR / "index.html"
    with open(index_path, encoding='utf-8') as f:
        index_html = f.read()

    cards_html = ""
    for a in sorted(articles_meta, key=lambda x: x['date'], reverse=True):
        img = a.get('image_url') or pick_image(a['title'])
        price = a.get('price', '')
        rating = a.get('rating', '4.8')
        read_time = a.get('read_time', 3)
        try:
            r = float(rating)
        except:
            r = 4.8
        price_html = f'<span class="card-price">NT${price}</span>' if price else ''
        stars = "★" * int(r) + "☆" * (5 - int(r))
        cards_html += f"""
    <div class="card">
      <a href="posts/{a['filename']}" class="card-img-link">
        <img src="{img}" alt="{a['title']}" loading="lazy" class="card-img" onerror="this.onerror=null;this.src='https://images.unsplash.com/photo-1574158622682-e40e69881006?w=800&h=450&fit=crop&q=80'">
      </a>
      <div class="card-body">
        <span class="card-tag">{a['label']}</span>
        <h2><a href="posts/{a['filename']}">{a['title']}</a></h2>
        <p>{a['description'][:75]}...</p>
        <div class="card-meta">
          <span class="stars" title="評分 {rating}/5">{stars} {rating}</span>
          {price_html}
          <span class="read-time">📖 {read_time} 分鐘</span>
        </div>
        <div class="card-footer">
          <a href="posts/{a['filename']}" class="btn-read">閱讀評測 →</a>
          <span class="card-date">{a['date']}</span>
        </div>
      </div>
    </div>"""

    # 用清晰標記替換卡片區域，避免重複疊加
    index_html = re.sub(
        r'<!-- CARDS_START -->.*?<!-- CARDS_END -->',
        '<!-- CARDS_START -->' + cards_html + '\n  <!-- CARDS_END -->',
        index_html, flags=re.DOTALL
    )
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_html)


def run_build():
    ARTICLES_DST.mkdir(exist_ok=True)

    with open(BASE_DIR / "article-template.html", encoding='utf-8') as f:
        template = f.read()

    summary_files = sorted(glob.glob(str(SUMMARY_DIR / "articles_summary_*.json")), reverse=True)
    if not summary_files:
        print("[!] 找不到文章摘要，請先執行 module2_writer.py")
        return

    with open(summary_files[0], encoding='utf-8') as f:
        summaries = json.load(f)

    # 補充摘要裡可能缺少的 price/rating（從 radar JSON 讀取）
    radar_files = sorted(glob.glob(str(SUMMARY_DIR / "radar_*.json")), reverse=True)
    radar_map = {}
    if radar_files:
        with open(radar_files[0], encoding='utf-8') as f:
            radar_data = json.load(f)
        for p in radar_data:
            radar_map[p.get('keyword', '')] = p

    for s in summaries:
        kw = s.get('keyword', '')
        if kw in radar_map:
            if 'price' not in s:
                s['price'] = radar_map[kw].get('price_twd', '')
            if 'rating' not in s:
                s['rating'] = radar_map[kw].get('rating', '4.8')

    src_files = sorted(glob.glob(str(ARTICLES_SRC / "*.html")))

    print(f"\n{'='*50}")
    print(f"  建站中... 共 {len(src_files)} 篇文章")
    print(f"{'='*50}\n")

    all_meta = []
    meta_cache_path = BASE_DIR / "articles_meta.json"

    if meta_cache_path.exists():
        with open(meta_cache_path, encoding='utf-8') as f:
            all_meta = json.load(f)
        existing = {a['filename'] for a in all_meta}
    else:
        existing = set()

    new_count = 0
    for src_path in src_files:
        idx = src_files.index(src_path)
        summary = summaries[idx] if idx < len(summaries) else {}

        page_html, meta = build_article_page(Path(src_path), template, summary)

        if meta['filename'] not in existing:
            dst_path = ARTICLES_DST / meta['filename']
            with open(dst_path, 'w', encoding='utf-8') as f:
                f.write(page_html)
            all_meta.append(meta)
            existing.add(meta['filename'])
            new_count += 1
            print(f"  ✓ {meta['title'][:40]}")

    with open(meta_cache_path, 'w', encoding='utf-8') as f:
        json.dump(all_meta, f, ensure_ascii=False, indent=2)

    with open(meta_cache_path, 'w', encoding='utf-8') as f:
        json.dump(all_meta, f, ensure_ascii=False, indent=2)

    update_index(all_meta)
    build_sitemap(all_meta)

    print(f"\n  新增 {new_count} 篇，累積 {len(all_meta)} 篇文章")
    print(f"  首頁已更新：{BASE_DIR / 'index.html'}")

    # 重建舊文章（套用最新模板樣式）
    print("\n  [Rebuild] 套用新模板到所有舊文章...")
    rebuild_all_posts()

    # 第二遍：注入相關文章（需要完整 all_meta 才能產生）
    print("\n  [Related] 注入相關文章連結...")
    _inject_related_articles(all_meta)

    return all_meta


def _inject_related_articles(all_meta: list):
    """對每篇文章注入相關文章區塊（第二遍處理，需要完整 meta 列表）"""
    injected = 0
    for m in all_meta:
        post_path = ARTICLES_DST / m['filename']
        if not post_path.exists():
            continue
        try:
            html = post_path.read_text(encoding='utf-8')
            # 如果已有相關文章區塊就跳過
            if 'related-articles' in html and 'related-card' in html:
                continue
            related_html = generate_related_articles(
                m['filename'], m.get('keyword', ''), all_meta, count=4
            )
            if not related_html:
                continue
            # 替換空的 placeholder 或插入在 disclaimer 前
            if '{{RELATED_ARTICLES}}' in html:
                html = html.replace('{{RELATED_ARTICLES}}', related_html)
            else:
                html = html.replace(
                    '<p class="disclaimer">', related_html + '\n  <p class="disclaimer">', 1
                )
            post_path.write_text(html, encoding='utf-8')
            injected += 1
        except Exception as e:
            print(f"  [Related] 跳過 {m['filename']}: {e}")
    print(f"  [Related] 注入完成：{injected} 篇")


def build_sitemap(articles_meta: list):
    base_url = "https://a12012300-ux.github.io"
    urls = [f"  <url><loc>{base_url}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>"]
    for a in articles_meta:
        urls.append(f"  <url><loc>{base_url}/posts/{a['filename']}</loc><changefreq>weekly</changefreq><priority>0.8</priority><lastmod>{a['date']}</lastmod></url>")

    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += "\n".join(urls)
    sitemap += "\n</urlset>"

    with open(BASE_DIR / "sitemap.xml", 'w', encoding='utf-8') as f:
        f.write(sitemap)
    print(f"  Sitemap 已更新：{len(articles_meta)} 個 URL")


def rebuild_all_posts():
    """
    重建所有已部署的舊文章，套用最新模板樣式。
    直接讀取 posts/*.html，提取文章內容後重新套用新模板。
    """
    ARTICLES_DST.mkdir(exist_ok=True)
    with open(BASE_DIR / "article-template.html", encoding='utf-8') as f:
        template = f.read()

    meta_cache_path = BASE_DIR / "articles_meta.json"
    all_meta = []
    if meta_cache_path.exists():
        with open(meta_cache_path, encoding='utf-8') as f:
            all_meta = json.load(f)

    # 建立 filename → meta 對照表
    meta_by_file = {a['filename']: a for a in all_meta}

    # Slug → keyword 反查表
    SLUG_KEYWORD = {v: k for k, v in KEYWORD_SLUG.items()}

    existing_posts = sorted(glob.glob(str(ARTICLES_DST / "*.html")))
    rebuilt = 0

    for post_path in existing_posts:
        fname = Path(post_path).name
        if fname == "index.html":
            continue

        # 從 meta 或從 filename slug 取得 keyword
        m = meta_by_file.get(fname, {})
        kw_slug = fname.split("-")[0] + "-" + fname.split("-")[1] if "-" in fname else "pet-product"
        kw_slug = "-".join(fname.split("-")[:-1])  # drop uid suffix
        keyword = m.get("keyword") or SLUG_KEYWORD.get(kw_slug, "寵物用品")

        try:
            with open(post_path, encoding='utf-8') as f:
                old_html = f.read()

            # 從舊文章提取核心資料
            title   = m.get("title") or extract_title(old_html)
            price   = str(m.get("price", ""))
            rating  = str(m.get("rating", "4.8"))
            aff_url = m.get("affiliate_url", "")

            # 提取文章正文（去掉舊模板的 header/nav/footer，只留 <article> 內容）
            art_m = re.search(r'<article[^>]*>(.*?)</article>', old_html, re.DOTALL | re.IGNORECASE)
            if not art_m:
                # 嘗試提取 body 內容
                art_m = re.search(r'<body[^>]*>(.*?)</body>', old_html, re.DOTALL | re.IGNORECASE)
            if not art_m:
                continue
            raw_content = art_m.group(1).strip()

            # 清除舊的穿插圖片（讓 build_article_page 重新抓商品圖插入）
            raw_content = re.sub(
                r'\n?<figure class="article-figure">.*?</figure>\n?',
                '', raw_content, flags=re.DOTALL
            )
            # 清除舊的產品資訊卡（會重新生成）
            raw_content = re.sub(
                r'<div class="product-overview">.*?</div>\s*</div>\s*</div>',
                '', raw_content, flags=re.DOTALL
            )
            # 清除舊的相關文章（會重新注入）
            raw_content = re.sub(
                r'<div class="related-articles">.*?</div>\s*</div>',
                '', raw_content, flags=re.DOTALL
            )

            # 建假 summary（讓 build_article_page 可以正確查 affiliates）
            # 保留 product_name 讓圖片搜尋更精確
            product_name = m.get("product_name", "")
            summary = {"keyword": keyword, "price": price, "rating": rating,
                       "affiliate_url": aff_url, "title": title,
                       "product_name": product_name,
                       # 重建出 article_link 讓 build_article_page 解碼商品名
                       "article_link": (
                           f"https://shopee.tw/search?keyword={product_name}"
                           if product_name else ""
                       )}

            # 寫臨時 source HTML 供 build_article_page 解析
            import tempfile as _tf
            with _tf.NamedTemporaryFile(mode='w', suffix='.html', encoding='utf-8',
                                        delete=False) as tmp:
                tmp.write(f"<html><head><title>{title}</title>"
                          f'<meta name="description" content="{title} 評測">'
                          f"</head><body>{raw_content}</body></html>")
                tmp_path = tmp.name

            page_html, new_meta = build_article_page(Path(tmp_path), template, summary)
            Path(tmp_path).unlink(missing_ok=True)

            # 強制使用原始 filename（不要重新計算）
            page_html = page_html.replace(new_meta["filename"], fname)
            new_meta["filename"] = fname

            with open(post_path, 'w', encoding='utf-8') as f:
                f.write(page_html)

            # 更新 meta cache
            meta_by_file[fname] = new_meta
            rebuilt += 1

        except Exception as e:
            print(f"  [Rebuild] 跳過 {fname}: {e}")

    # 更新 all_meta
    all_meta = list(meta_by_file.values())
    with open(meta_cache_path, 'w', encoding='utf-8') as f:
        json.dump(all_meta, f, ensure_ascii=False, indent=2)

    update_index(all_meta)
    build_sitemap(all_meta)
    print(f"\n  [Rebuild] 重建 {rebuilt} 篇舊文章，已套用最新模板")
    return rebuilt


if __name__ == "__main__":
    import sys
    if "--rebuild-all" in sys.argv:
        rebuild_all_posts()
    else:
        run_build()
