"""
build_feed.py
=============
每日重建 feed.xml（RSS 2.0）
讓 Google / Feedly / 閱讀器知道有新文章，加速收錄

執行：python pipeline/build_feed.py
"""
import sys, json, html as _html
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from datetime import datetime

ROOT     = Path(__file__).parent.parent
META_PATH = ROOT / "articles_meta.json"
FEED_PATH = ROOT / "feed.xml"
BASE_URL  = "https://a12012300-ux.github.io"


def rfc822(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return d.strftime("%a, %d %b %Y 09:00:00 +0800")
    except Exception:
        return datetime.now().strftime("%a, %d %b %Y 09:00:00 +0800")


def build_feed():
    if not META_PATH.exists():
        print("  [Feed] articles_meta.json 不存在，跳過")
        return

    meta    = json.loads(META_PATH.read_text(encoding="utf-8"))
    articles = sorted(meta, key=lambda x: x.get("date", ""), reverse=True)[:30]

    items = ""
    for a in articles:
        title   = _html.escape(a.get("title", ""))
        fname   = a.get("filename", "")
        link    = f"{BASE_URL}/posts/{fname}"
        desc    = _html.escape(a.get("description", ""))
        date    = rfc822(a.get("date", ""))
        keyword = _html.escape(a.get("keyword", "寵物"))
        image   = a.get("social_image_url") or a.get("image_url", "")
        rating  = a.get("rating", "4.8")
        price   = a.get("price", "")

        # 豐富描述（含價格與評分）
        rich_desc = desc
        if price:
            rich_desc += f" NT${price}，評分 {rating}/5。"
        rich_desc = _html.escape(rich_desc)

        enclosure = (f'\n    <enclosure url="{image}" type="image/jpeg"/>'
                     if image else "")
        items += f"""  <item>
    <title>{title}</title>
    <link>{link}</link>
    <guid isPermaLink="true">{link}</guid>
    <description>{rich_desc}</description>
    <pubDate>{date}</pubDate>
    <category>{keyword}</category>{enclosure}
  </item>
"""

    today_rfc = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")
    # 找一張代表圖
    logo_img = ""
    for a in articles:
        img = a.get("social_image_url") or a.get("image_url", "")
        if img and img.startswith("http"):
            logo_img = img
            break

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:atom="http://www.w3.org/2005/Atom"
     xmlns:media="http://search.yahoo.com/mrss/"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>毛孩研究室 | 台灣寵物用品評測</title>
    <link>{BASE_URL}</link>
    <atom:link href="{BASE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
    <description>真實飼主評測台灣寵物用品，比較蝦皮/momo/PChome最低價，每日更新。</description>
    <language>zh-TW</language>
    <lastBuildDate>{today_rfc}</lastBuildDate>
    <managingEditor>bot@maohao.tw (毛孩研究室)</managingEditor>
    <webMaster>bot@maohao.tw (毛孩研究室)</webMaster>
    <ttl>1440</ttl>
    <image>
      <url>{logo_img or BASE_URL + '/posts/social/card-044442.jpg'}</url>
      <title>毛孩研究室</title>
      <link>{BASE_URL}</link>
      <width>144</width>
      <height>144</height>
    </image>
{items}  </channel>
</rss>"""

    FEED_PATH.write_text(feed, encoding="utf-8")
    print(f"  [Feed] feed.xml 更新完成（{len(articles)} 篇文章）→ {FEED_PATH.name}")


if __name__ == "__main__":
    build_feed()
