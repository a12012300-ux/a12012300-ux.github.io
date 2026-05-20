"""
每日 Email 通知 v3
- 寄送 Dcard版 + IG + Threads 完整貼文文字
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
    """回傳 title -> meta 對照表"""
    meta_path = BASE_DIR / "articles_meta.json"
    if not meta_path.exists():
        return {}
    with open(meta_path, encoding="utf-8") as f:
        data = json.load(f)
    return {m["title"]: m for m in data}


def build_dcard_text(article: dict) -> str:
    """生成 Dcard 貼文（第三方實測角度、長版、有共情）"""
    title    = article.get("title", "")
    keyword  = article.get("keyword", "寵物")
    post_url = article.get("post_url", BLOG_BASE_URL)
    price    = article.get("price", "")
    rating   = article.get("rating", "4.8")
    price_note = f"NT${price}" if price else "價格合理"

    # 各分類：踩雷背景 + 實測過程 + 優缺點 + 互動問句
    templates = {
        "貓砂": f"""身為三貓家庭，貓砂這件事我研究了快兩年

試過礦砂、豆腐砂、水晶砂、木屑砂⋯
每一款都有讓我崩潰的地方：
・礦砂：粉塵太多，貓咪打噴嚏
・豆腐砂：結塊不紮實，鏟起來整個散掉
・水晶砂：不透明不好判斷有沒有尿

後來認真做功課，找到這款試了三個月

---

實測心得：

✅ 真的好的地方
・除臭力是目前用過最強的，早上起床聞不到
・結塊紮實，鏟起來乾淨俐落，不碎
・粉塵比礦砂少很多，貓咪接受度高

❌ 老實說的缺點
・價格比普通貓砂貴一些（{price_note}）
・6L 包裝，三隻貓大概用一個月

整體評分 {rating}/5，我自己是不會換了

詳細比較和哪裡買最便宜：
{post_url}

你們家都用什麼砂？有什麼推薦的嗎？""",

        "貓糧": f"""養了五年貓，乾糧換過不下十款

剛開始養的時候什麼都不懂，就買超市看到的
後來貓咪皮膚開始過敏，毛也變得很粗
去看獸醫，醫生說可能是糧的問題

從那次之後我開始認真研究成分

---

挑乾糧我現在看三件事：
1. 蛋白質來源（肉要排第一，不能是「肉粉」）
2. 是否含穀物（我的貓對玉米過敏）
3. 含水量（貓天生喝水少，糧的含水也很重要）

這款用了兩個月的心得：

✅ 明顯改善的地方
・毛色比之前亮很多，朋友都說摸起來不一樣
・便便味道變淡了（這個很主觀但我真的有感）
・挑食的貓吃得很開心，沒有剩

❌ 缺點
・價格偏高（{price_note}），對多貓家庭負擔不小
・包裝不夠密封，開封後要另外裝罐

整體 {rating}/5，不是最便宜但我覺得值得

成分分析和比價：
{post_url}

你們現在給貓吃什麼糧？換過幾次？""",

        "狗糧": f"""我家狗狗腸胃從小就很敏感

只要換糧或吃到不適合的食物
隔天一定軟便甚至拉肚子
帶去看醫生，醫生說要找「腸胃友善」的配方

試過四五款之後整理一下心得

---

腸胃敏感的狗挑糧，我建議看這些：
・益生菌或膳食纖維是否添加
・有無低敏蛋白（鮭魚、羊肉比雞肉好）
・換糧要慢慢換，不能一次換完

這款用了兩個月觀察：

✅ 有感的改善
・軟便次數明顯減少，大概從每週3次降到幾乎沒有
・食慾變好，每次吃完還會去舔碗
・毛色也比之前亮，意外的驚喜

❌ 客觀說缺點
・{price_note} 對大型犬來說一個月飼料費不少
・大包裝不夠密封，需要自備夾鏈

評分 {rating}/5，腸胃敏感狗主人可以參考

詳細評測和成分解析：
{post_url}

你家狗有腸胃敏感的問題嗎？都怎麼處理？""",

        "自動餵食器": f"""朝九晚五上班族，養貓最怕的就是加班

以前每次要加班，第一個想到的是：貓咪飼料夠嗎？
拜託過鄰居幫忙，但一直麻煩別人真的很不好意思
後來決定入手自動餵食器

試了兩款之後，說說真實心得

---

選自動餵食器我覺得要注意：
・是否支援 WiFi 遠端控制（出門在外才能調整）
・馬達聲音（有些深夜運轉會吵到人睡覺）
・防卡糧設計（不然凌晨沒出料你不知道）
・容量（要能撐幾天）

這款用了三個月：

✅ 讓我最滿意的地方
・手機 App 可以即時查看剩餘飼料量
・出料聲音很小，貓咪睡旁邊都沒被嚇到
・WiFi 掉線會推播通知，不會無聲無息失效
・容量夠，出差三天不用擔心

❌ 真實缺點
・初次設定 App 有點複雜，花了半小時
・{price_note} 比普通碗貴，但用了就回不去了

評分 {rating}/5，上班族飼主強推

詳細測試和功能說明：
{post_url}

你們有用自動餵食器嗎？什麼牌子覺得好用？""",

        "寵物外出包": f"""帶貓出門這件事，我買錯了三次才找到對的

第一款：太小，8公斤的貓擠進去一直叫
第二款：通風不夠，夏天差點中暑
第三款：拉鍊品質差，出門途中差點讓貓逃跑

每次買都要重新適應，貓咪壓力也大

---

後來認真研究，發現好的外出包要看這幾點：
・內部空間夠不夠站立（貓蹲著坐著都要能轉身）
・通風設計（夏天悶熱是大問題）
・視野（能看到外面的貓反而比較不焦慮）
・承重（大貓要特別注意）

這款太空艙造型用了三個月：

✅ 真實好評
・透明上蓋設計，牠可以看外面，整趟出門叫聲少80%
・空間大，我家8公斤大橘自在轉身沒問題
・肩背+手提兩用，搭捷運換肩膀很方便
・側邊通風孔設計，夏天悶熱改善很多

❌ 缺點也說
・透明蓋比較重，單手開關需要練習
・{price_note} 不算便宜，但我覺得值得

評分 {rating}/5，帶貓出門的轉捩點

詳細評測和尺寸建議：
{post_url}

你們帶毛孩出門都用什麼？有遇過我這種慘劇嗎 😂""",

        "寵物洗毛精": f"""給毛孩洗澡，我家是每兩週一次的頻率

換過好幾款洗毛精，遇過一些問題：
・某款洗完皮膚發紅（可能過敏）
・某款香味太重，牠洗完一直去磨蹭牆壁
・某款清潔力太強，毛洗完很乾很粗

後來認真看成分，找到這款試了兩個月

---

我挑洗毛精現在看這些成分：
・是否含 SLS（月桂醇硫酸鈉，刺激性強）
・pH 值是否適合寵物（偏中性～弱鹼）
・香精含量（太重的貓狗會不舒服）

這款的實測：

✅ 讓我繼續回購的原因
・洗完毛很柔順，梳毛的時候好梳很多
・氣味淡雅不嗆，牠洗完沒有躁動的反應
・起泡力適中，沖洗很乾淨不留殘留感
・皮膚沒有出現過敏反應（用了兩個月觀察）

❌ 客觀說缺點
・{price_note} 比超市款貴
・瓶蓋設計不夠好倒，容易一次倒太多

評分 {rating}/5，皮膚敏感毛孩可以試試

成分解析和比較：
{post_url}

你們多久幫毛孩洗一次澡？用什麼牌子？""",

        "寵物保健": f"""毛孩保健品這個坑，我踩了不少

剛開始養的時候什麼都想給牠補
益生菌、護毛、護腎、關節保健⋯
每個月光保健品就花了一兩千

後來去問獸醫，才知道很多東西根本不需要
有些還可能補過頭反而有問題

---

獸醫說的原則：
・健康的成年寵物，基本上不需要額外補充
・有需求的才補（腸胃差→益生菌、毛質差→Omega-3）
・優先食物補充，保健品是輔助不是主力

這款我試過有感的：

✅ 真的有差的地方
・益生菌：腸胃問題明顯改善，軟便次數降低
・Omega-3：毛色變亮，約一個月開始有感
・劑量好控制，不用自己算體重換算

❌ 老實說
・{price_note} 不算便宜，要長期吃才有效果
・不是每隻寵物都有反應，體質不同

評分 {rating}/5，有針對性需求再買比較值得

哪些值得買的分析：
{post_url}

你們有在給毛孩補保健品嗎？有感嗎？""",

        "貓咪罐頭": f"""幫貓選主食罐這件事，我研究了半年

貓咪天生就不愛喝水，如果主食是乾糧
長期下來泌尿系統很容易出問題
獸醫建議可以搭配主食罐增加含水量

但罐頭種類真的太多，完全不知道從哪選起

---

我現在挑主食罐看這幾點：
・蛋白質含量（越高越好，最好超過10%）
・是否添加增稠劑（鹿角菜膠對貓不好）
・水分含量（主食罐至少要75%以上）
・貓咪接不接受（再好的成分不吃也沒用）

這款試了一個月的心得：

✅ 好評的地方
・三隻挑食程度不同的貓，全部接受，沒有剩
・成分乾淨，主要原料是真正的魚肉和雞肉
・含水量高，吃完喝水次數有減少（間接觀察）
・方便的易開蓋，不需要開罐器

❌ 缺點
・{price_note} 一天一罐，一個月飼料費不少
・香味比較重，開罐後冰箱味道明顯

評分 {rating}/5，挑食貓的好選擇

成分分析和多貓家庭評估：
{post_url}

你們家貓吃乾糧還是主食罐？有推薦的牌子嗎？""",

        "狗罐頭": f"""狗罐頭的成分差異，大到讓我很驚訝

以前都覺得罐頭就是罐頭，差不多的東西
直到朋友建議我去看成分表
才發現有些牌子第一個原料是「水」，然後才是肉

這個讓我開始認真研究

---

挑狗罐頭，我覺得要看：
・第一原料是肉還是水（水排第一要小心）
・是否含人工色素和防腐劑
・蛋白質含量比例
・鈉含量（長期吃高鈉對腎臟不好）

這款試了六週：

✅ 讓我持續回購的原因
・成分表乾淨，主要原料是雞胸肉
・我家狗狗平常不太感興趣的食物，這款牠很積極
・便便成形好、氣味沒有比平常重
・適合當乾糧拌飯，增加食慾

❌ 缺點
・{price_note} 長期餵食費用不低
・包裝開封後要盡快用完，密封性普通

評分 {rating}/5，對成分有要求的狗主人可以試試

詳細成分比較：
{post_url}

你們狗狗吃什麼罐頭？有踩過雷嗎？""",

        "狗零食": f"""用零食訓練狗狗，選對了效率差很多

我家柴犬叫阿柴，訓練起來很有主見
一般飼料做獎勵完全沒有反應，叫牠坐下就是不理你

後來才知道訓練用的零食有幾個關鍵要素

---

訓練用零食要注意：
・氣味要夠香（讓狗覺得超值得）
・體積要小（一次給太多熱量超標）
・不能太硬（要能快速吃完繼續訓練）
・成分要乾淨（長期吃的東西不能太多添加物）

這款試了兩個月的訓練成效：

✅ 訓練效果
・阿柴聞到這款馬上眼神發亮，專注度提升很多
・體積小，一次訓練用個5-6顆不怕熱量過多
・軟硬適中，吃完繼續訓練不耽誤
・成分主要是雞肉，沒有奇怪添加物

❌ 缺點
・{price_note} 一包量不算多，訓練密集的話消耗快
・氣味比較重，零食袋要密封收好

評分 {rating}/5，有在做訓練的狗主人推薦

成分分析和其他推薦款：
{post_url}

你們用什麼零食訓練狗狗？訓練到什麼程度了？""",

        "貓零食": f"""我家貓超挑嘴，零食踩雷率大概有六成

拆開包裝聞一聞就走開、吃兩口就不吃了
或是很愛吃但吃完腸胃不好——這些我都遇過

後來開始認真看成分，篩選標準也越來越嚴

---

我現在挑貓零食的標準：
・蛋白質來源要是真正的肉，不是「肉粉」
・不含人工香料（貓對真實肉味最有反應）
・牛磺酸要有（貓的必需胺基酸）
・鈉含量不能太高（零食要控制）

這款試了一個月：

✅ 讓我繼續買的原因
・三款口味都試過，每次打開袋子牠就衝過來
・吃完沒有軟便或嘔吐的狀況（之前某款讓牠吐過）
・成分表前三名都是真實魚肉和雞肉
・包裝密封好，開封後還是很新鮮

❌ 老實說缺點
・{price_note} 比超市零食貴一些
・包裝設計比較難撕開

評分 {rating}/5，挑食貓的飼主可以試試

成分詳解和其他推薦款：
{post_url}

你家貓最愛什麼口味的零食？有什麼讓牠瘋狂的推薦嗎？""",
    }

    # 有對應模板就用，否則用通用模板
    if keyword in templates:
        return templates[keyword]

    # 通用模板（其他分類）
    price_note = f"NT${price}" if price else "價格合理"
    return f"""研究了一陣子的{keyword}，整理一下實測心得

用過幾款之後，發現選{keyword}有幾個關鍵點很多人沒注意到
踩過一些雷，也找到讓我滿意的選擇

---

實測這款兩個月的心得：

✅ 真的好的地方
・品質穩定，每次使用體驗都一致
・CP 值高，{price_note} 在這個品質算合理
・毛孩接受度高，沒有排斥反應

❌ 缺點老實說
・不是完美的產品，某些細節還可以改善
・特定需求的飼主可能需要再評估

整體評分 {rating}/5

詳細比較和評測：
{post_url}

你們有用過嗎？或是有其他推薦的款式？"""


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
    today    = datetime.now().strftime("%Y-%m-%d")

    # 從 social.py 取新版貼文產生器
    try:
        from pipeline.social import build_ig_caption, build_threads_text
    except Exception:
        build_ig_caption = build_threads_text = None

    # ── 組 email 正文 ────────────────────────────────────────
    msg = MIMEMultipart("mixed")
    msg["From"]    = GMAIL_USER
    msg["To"]      = GMAIL_USER
    msg["Subject"] = (
        f"[毛孩研究室] {today} 每日貼文包"
        f" — {len(articles)} 篇文章 + Dcard文章 + 圖文卡片"
    )

    divider = "━" * 48

    body_lines = [
        "🐾 毛孩研究室 每日自動發文包",
        f"日期：{today}  |  今日 {len(articles)} 篇新文章",
        "",
        f"📖 部落格首頁：{BLOG_BASE_URL}",
        "",
        divider,
        "  使用說明",
        divider,
        "1. 每篇文章有三版貼文：Dcard版 + IG版 + Threads版",
        "2. Dcard版：直接複製貼到 dcard.tw 寵物版",
        "3. 對應的圖文卡片 JPEG 在附件（依序標號）",
        "4. 發 IG 時選圖文卡片 + 貼 IG版文字",
        "5. 發 Threads 時貼 Threads版文字（可附圖）",
        "",
    ]

    attached_images = []  # (filename, bytes)

    for idx, a in enumerate(articles[:5], 1):  # 最多 5 篇
        title   = a.get("title", "")
        keyword = a.get("keyword", "寵物")
        aff_url = a.get("affiliate_url", "")
        rating  = a.get("rating", "4.8")
        price   = a.get("price", "")

        # 從 meta 取得文章 URL 和社群卡片路徑
        meta     = meta_map.get(title, {})
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
                    attached_images.append(
                        (f"圖文卡片_{idx:02d}_{keyword}.jpg", cf.read())
                    )

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

        card_note  = (
            f"（圖文卡片：附件 圖文卡片_{idx:02d}_{keyword}.jpg）"
            if social_card_fname else "（圖文卡片未產生）"
        )
        dcard_text = build_dcard_text(article_data)

        body_lines += [
            divider,
            f"  第 {idx} 篇  |  {title[:42]}",
            divider,
            f"文章連結：{post_url}",
            f"圖文卡片：{card_note}",
            "",
            "▶ Dcard 版貼文（複製貼上即可）",
            "  發文位置：dcard.tw -> 寵物版 -> 發表文章",
            f"  標題建議：{title[:40]}",
            "─ ─ ─ ─ ─ ─ ─ ─",
            dcard_text,
            "",
            "▶ IG 版貼文（發 Instagram 用）",
            "─ ─ ─ ─ ─ ─ ─ ─",
            ig_text,
            "",
            "▶ Threads 版貼文（發 Threads 用）",
            "─ ─ ─ ─ ─ ─ ─ ─",
            threads_text,
            "",
        ]

    body_lines += (
        [divider, "今日所有文章：", ""]
        + [f"  {i}. {a.get('title', '')}" for i, a in enumerate(articles, 1)]
        + ["", "祝收益節節高升！", "毛孩研究室 自動化系統"]
    )

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
        print(
            f"  [Email] 已寄送到 {GMAIL_USER}"
            f"（含 {len(attached_images)} 張圖文卡片）"
        )
    except Exception as e:
        print(f"  [Email] 寄送失敗：{e}")


if __name__ == "__main__":
    run_notify()
