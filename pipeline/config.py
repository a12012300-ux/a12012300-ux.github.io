"""
Pipeline 設定：所有關鍵字、聯盟連結、API 設定
適用於 GitHub Actions 雲端環境
"""
import os

# Anthropic Claude API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Instagram Graph API
IG_USER_ID       = os.environ.get("IG_USER_ID", "")
IG_ACCESS_TOKEN  = os.environ.get("IG_ACCESS_TOKEN", "")

# Threads API
THREADS_USER_ID      = os.environ.get("THREADS_USER_ID", "")
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")

# 每日發文數量（控制 API 成本）
ARTICLES_PER_DAY = int(os.environ.get("ARTICLES_PER_DAY", "5"))

# 每日社群發文數量（不要刷太多，2~3 篇即可）
SOCIAL_POSTS_PER_DAY = int(os.environ.get("SOCIAL_POSTS_PER_DAY", "3"))

# 路徑設定（相對於 pet-blog 根目錄）
PIPELINE_DIR  = "pipeline"
ARTICLES_DIR  = "pipeline/output/articles"
DATA_DIR      = "pipeline/output/data"

# 部落格網址
BLOG_BASE_URL = "https://a12012300-ux.github.io"

# 蝦皮聯盟短連結（有佣金追蹤）
SHOPEE_AFFILIATE_LINKS = {
    "自動餵食器": "https://s.shopee.tw/1BJAnzgFQR",
    "寵物碗":     "https://s.shopee.tw/17DPqkgnE",
    "貓咪罐頭":   "https://s.shopee.tw/BQdc9k3SH",
    "寵物外出包":  "https://s.shopee.tw/Lk3oSjQ7K",
    "貓砂":       "https://s.shopee.tw/W3U0limmN",
    "寵物保健":   "https://s.shopee.tw/10zkbvsLyN",
    "狗糧":       "https://s.shopee.tw/BQdcOvWfE",
    "貓糧":       "https://s.shopee.tw/17DQ5wA0D",
    "狗罐頭":     "https://s.shopee.tw/W3U10uFzK",
    "狗窩":       "https://s.shopee.tw/Lk3ohutKJ",
    "寵物洗毛精":  "https://s.shopee.tw/4LGCa5CSpl",
    "狗狗牽繩":   "https://s.shopee.tw/4AwmNmD6Ak",
    "貓窩":       "https://s.shopee.tw/40dMBTDjVj",
    "寵物玩具":   "https://s.shopee.tw/5ApJZc9I8y",
    "貓零食":     "https://s.shopee.tw/50VtNJ9vTx",
    "狗零食":     "https://s.shopee.tw/5q50MrbDSY",
    "貓抓板":     "https://s.shopee.tw/5flaAYbqnX",
    # ── 第三批（2026-05-14 新增）────────────────────────────
    "梳毛刷":     "https://s.shopee.tw/2LV8KP4qqr",
    "指甲剪":     "https://s.shopee.tw/2BBi865UBq",
    "寵物牙膏":   "https://s.shopee.tw/20sHvn67Wp",
    "尿布墊":     "https://s.shopee.tw/3B4FJw1gA4",
    "寵物雨衣":   "https://s.shopee.tw/30kp7d2JV3",
    "暖墊":       "https://s.shopee.tw/7pq4sXehok",
    "狗玩具":     "https://s.shopee.tw/7fWegEfL9j",
    "寵物推車":   "https://s.shopee.tw/5VSA6FnaYK",
    "寵物圍欄":   "https://s.shopee.tw/5L8jtwoDtJ",
    "除臭噴劑":   "https://s.shopee.tw/5q50UrmJsQ",
    # ── 第四批（2026-05-14 新增 50 個）──────────────────────
    "貓咪跳台":   "https://s.shopee.tw/9pb9GVDrMr",
    "自動貓砂盆":  "https://s.shopee.tw/9KesfaFlNm",
    "寵物胸背帶":  "https://s.shopee.tw/9UyIrtF82p",
    "貓咪項圈":   "https://s.shopee.tw/9022GyH23k",
    "狗狗項圈":   "https://s.shopee.tw/9ALSTHGOin",
    "寵物涼墊":   "https://s.shopee.tw/2LV8KjRMeJ",
    "寵物烘毛機":  "https://s.shopee.tw/1Vw1LCUXLA",
    "狗狗嗅聞墊":  "https://s.shopee.tw/1Lcb8tVAg9",
    "貓咪隧道":   "https://s.shopee.tw/1qYrjoTGfG",
    "狗狗飛盤":   "https://s.shopee.tw/1gFRXVTu0F",
    "寵物安全帶":  "https://s.shopee.tw/50VtVdztgG",
    "貓咪化毛膏":  "https://s.shopee.tw/5ApJhwzGLJ",
    "狗狗護掌膏":  "https://s.shopee.tw/4ft3721AME",
    "寵物洗耳液":  "https://s.shopee.tw/4qCTJL0X1H",
    "寵物除蚤":   "https://s.shopee.tw/4LGCiQ2R2C",
    "狗狗拔河繩":  "https://s.shopee.tw/7fWegYXbZQ",
    "貓咪薄荷":   "https://s.shopee.tw/7pq4srWyET",
    "寵物濕紙巾":  "https://s.shopee.tw/7KtoHwYsFO",
    "狗狗關節":   "https://s.shopee.tw/7VDEUFYEuR",
    "貓咪益生菌":  "https://s.shopee.tw/70GxtKa8vM",
    "狗狗益生菌":  "https://s.shopee.tw/7fWegZPhwa",
    "寵物維他命":  "https://s.shopee.tw/7pq4ssP4bd",
    "貓咪定位器":  "https://s.shopee.tw/7KtoHxQycY",
    "狗狗定位器":  "https://s.shopee.tw/7VDEUGQLHb",
    "寵物攝影機":  "https://s.shopee.tw/5flaItXK0G",
    "貓咪飲水機":  "https://s.shopee.tw/4VZculDVKh",
    "狗狗飲水器":  "https://s.shopee.tw/3LNfWcHwhU",
    "寵物保鮮罐":  "https://s.shopee.tw/3Vh5ivHJMX",
    "零食分裝袋":  "https://s.shopee.tw/3g0VvEGg1a",
    "貓咪背包":   "https://s.shopee.tw/3qJw7XG2gd",
    "寵物冷感背心": "https://s.shopee.tw/gMuLjIkyX",
    "貓咪玩具球":  "https://s.shopee.tw/1BJAweGqxe",
    "除毛滾輪":   "https://s.shopee.tw/10zkkLHUId",
    "寵物餵藥器":  "https://s.shopee.tw/BQdkoKezU",
    "狗狗響片":   "https://s.shopee.tw/17DYVLIKT",
    "貓咪護膚":   "https://s.shopee.tw/BQdkoysOa",
    "眼淚痕清潔":  "https://s.shopee.tw/17DYVzVjZ",
    "狗狗驅蟲":   "https://s.shopee.tw/W3U9Qxbig",
    "貓咪驅蟲":   "https://s.shopee.tw/Lk3x7yF3f",
    "寵物體重計":  "https://s.shopee.tw/4qCTJOh6vY",
    "伸縮牽繩":   "https://s.shopee.tw/5ApJi1PDLN",
    "貓咪沐浴乳":  "https://s.shopee.tw/4ft376R7MI",
    "狗狗沐浴乳":  "https://s.shopee.tw/4qCTJPQU1L",
    "寵物噴水瓶":  "https://s.shopee.tw/4LGCiUSO2G",
    "逗貓棒羽毛":  "https://s.shopee.tw/4VZcunRkhJ",
    "寵物游泳圈":  "https://s.shopee.tw/4AwmWCF0Ne",
    "狗狗零食機":  "https://s.shopee.tw/40dMJtFdid",
    "寵物計步器":  "https://s.shopee.tw/5ApJi2BCLs",
    "處方貓糧":   "https://s.shopee.tw/50VtVjBpgr",
    "老犬關節糧":  "https://s.shopee.tw/4qCTJQCT1q",
}

# 商品資料庫（每關鍵字多個商品，避免每天重複）
PRODUCT_DATABASE = [
    # 自動餵食器
    {"keyword": "自動餵食器", "name": "寵物自動餵食器 WiFi遠端控制", "price_twd": 899, "sold_monthly": 3200, "rating": "4.8"},
    {"keyword": "自動餵食器", "name": "定時自動餵食機貓狗通用 APP操控", "price_twd": 1099, "sold_monthly": 2800, "rating": "4.7"},
    {"keyword": "自動餵食器", "name": "雙碗智能自動餵食器 語音錄音款", "price_twd": 1299, "sold_monthly": 1900, "rating": "4.9"},

    # 寵物碗
    {"keyword": "寵物碗", "name": "PETKIT智能寵物碗防打翻慢食碗", "price_twd": 599, "sold_monthly": 2100, "rating": "4.6"},
    {"keyword": "寵物碗", "name": "電動貓咪飲水機靜音過濾器", "price_twd": 699, "sold_monthly": 3100, "rating": "4.7"},
    {"keyword": "寵物碗", "name": "不鏽鋼寵物碗防滑雙碗架組", "price_twd": 349, "sold_monthly": 4200, "rating": "4.5"},

    # 貓咪罐頭
    {"keyword": "貓咪罐頭", "name": "Inaba 雞肉貓咪罐頭 85g×24入", "price_twd": 480, "sold_monthly": 5600, "rating": "4.9"},
    {"keyword": "貓咪罐頭", "name": "Natural10 天然無穀貓罐頭主食罐 12入", "price_twd": 720, "sold_monthly": 2300, "rating": "4.8"},
    {"keyword": "貓咪罐頭", "name": "CIAO 日本原裝貓罐頭鮪魚口味 24入", "price_twd": 560, "sold_monthly": 3800, "rating": "4.7"},

    # 寵物外出包
    {"keyword": "寵物外出包", "name": "Catidea太空艙寵物外出包透視款", "price_twd": 1299, "sold_monthly": 1800, "rating": "4.8"},
    {"keyword": "寵物外出包", "name": "可折疊寵物推車外出包兩用款", "price_twd": 1599, "sold_monthly": 1200, "rating": "4.6"},
    {"keyword": "寵物外出包", "name": "航空規格寵物登機外出包 S號", "price_twd": 899, "sold_monthly": 2400, "rating": "4.7"},

    # 貓砂
    {"keyword": "貓砂", "name": "Unicharm消臭大師豆腐貓砂 7L", "price_twd": 299, "sold_monthly": 7200, "rating": "4.8"},
    {"keyword": "貓砂", "name": "IRIS礦砂結團貓砂 5kg", "price_twd": 249, "sold_monthly": 5100, "rating": "4.6"},
    {"keyword": "貓砂", "name": "水晶矽砂貓砂 3.8L 超強除臭款", "price_twd": 399, "sold_monthly": 3300, "rating": "4.7"},

    # 貓零食
    {"keyword": "貓零食", "name": "CIAO 啾嚕流質零食貓咪14入", "price_twd": 259, "sold_monthly": 8900, "rating": "4.9"},
    {"keyword": "貓零食", "name": "Inaba 日本原裝貓咪條狀零食 50入", "price_twd": 399, "sold_monthly": 6200, "rating": "4.8"},
    {"keyword": "貓零食", "name": "凍乾鮭魚貓咪零食 天然無添加 50g", "price_twd": 349, "sold_monthly": 2800, "rating": "4.7"},

    # 寵物玩具
    {"keyword": "寵物玩具", "name": "貓咪電動逗貓棒自動旋轉 USB充電", "price_twd": 249, "sold_monthly": 4100, "rating": "4.6"},
    {"keyword": "寵物玩具", "name": "羽毛電動逗貓棒 貓咪互動玩具", "price_twd": 189, "sold_monthly": 5300, "rating": "4.5"},
    {"keyword": "寵物玩具", "name": "狗狗嗅聞墊 益智慢食訓練玩具", "price_twd": 299, "sold_monthly": 3600, "rating": "4.7"},

    # 貓窩
    {"keyword": "貓窩", "name": "可折疊寵物貓窩四季通用 M號", "price_twd": 329, "sold_monthly": 4800, "rating": "4.7"},
    {"keyword": "貓窩", "name": "甜甜圈貓窩保暖絨毛款 L號", "price_twd": 459, "sold_monthly": 3200, "rating": "4.8"},
    {"keyword": "貓窩", "name": "吊床式貓咪墊 窗台固定款", "price_twd": 399, "sold_monthly": 2100, "rating": "4.6"},

    # 貓抓板
    {"keyword": "貓抓板", "name": "瓦楞紙貓抓板大號附貓薄荷", "price_twd": 159, "sold_monthly": 6700, "rating": "4.8"},
    {"keyword": "貓抓板", "name": "S型貓抓板磨爪板 麻繩款", "price_twd": 299, "sold_monthly": 3900, "rating": "4.7"},
    {"keyword": "貓抓板", "name": "立式貓抓柱貓抓板組合 60cm", "price_twd": 599, "sold_monthly": 2200, "rating": "4.6"},

    # 狗零食
    {"keyword": "狗零食", "name": "狗狗訓練零食雞肉乾 200g", "price_twd": 199, "sold_monthly": 5400, "rating": "4.7"},
    {"keyword": "狗零食", "name": "Natural10全天然凍乾狗零食 100g", "price_twd": 349, "sold_monthly": 2600, "rating": "4.8"},
    {"keyword": "狗零食", "name": "牛肉乾條狗狗零食 台灣製 150g", "price_twd": 229, "sold_monthly": 4100, "rating": "4.6"},

    # 狗罐頭
    {"keyword": "狗罐頭", "name": "無穀鮮肉主食狗罐頭 12入", "price_twd": 680, "sold_monthly": 2900, "rating": "4.7"},
    {"keyword": "狗罐頭", "name": "希爾斯處方狗罐頭腸胃護理款", "price_twd": 890, "sold_monthly": 1800, "rating": "4.9"},
    {"keyword": "狗罐頭", "name": "皇家室內狗罐頭 12入 低卡配方", "price_twd": 750, "sold_monthly": 2100, "rating": "4.7"},

    # 狗糧
    {"keyword": "狗糧", "name": "希爾斯完美消化狗糧 1.58kg", "price_twd": 980, "sold_monthly": 2300, "rating": "4.8"},
    {"keyword": "狗糧", "name": "皇家成犬狗糧 3kg 關節保護配方", "price_twd": 1190, "sold_monthly": 3100, "rating": "4.7"},
    {"keyword": "狗糧", "name": "Natural10超級食物無穀狗糧 2kg", "price_twd": 1380, "sold_monthly": 1700, "rating": "4.9"},

    # 貓糧
    {"keyword": "貓糧", "name": "皇家室內貓乾糧 2kg", "price_twd": 850, "sold_monthly": 4200, "rating": "4.7"},
    {"keyword": "貓糧", "name": "Royal Canin 波斯貓專用貓糧 2kg", "price_twd": 980, "sold_monthly": 2800, "rating": "4.8"},
    {"keyword": "貓糧", "name": "Natural10 無穀天然貓糧 1.8kg", "price_twd": 1200, "sold_monthly": 1900, "rating": "4.9"},

    # 狗狗牽繩
    {"keyword": "狗狗牽繩", "name": "反光夜間安全牽繩伸縮5米", "price_twd": 299, "sold_monthly": 3800, "rating": "4.6"},
    {"keyword": "狗狗牽繩", "name": "防暴衝P字鍊訓練牽繩組合", "price_twd": 399, "sold_monthly": 2400, "rating": "4.7"},
    {"keyword": "狗狗牽繩", "name": "雙頭牽繩防打結款 多色可選", "price_twd": 199, "sold_monthly": 4600, "rating": "4.5"},

    # 寵物洗毛精
    {"keyword": "寵物洗毛精", "name": "貓咪溫和無淚配方洗毛精 500ml", "price_twd": 349, "sold_monthly": 3100, "rating": "4.7"},
    {"keyword": "寵物洗毛精", "name": "狗狗除臭殺菌洗毛精 750ml", "price_twd": 399, "sold_monthly": 2800, "rating": "4.6"},
    {"keyword": "寵物洗毛精", "name": "天然草本寵物乾洗噴霧 300ml", "price_twd": 289, "sold_monthly": 2300, "rating": "4.5"},

    # 寵物保健
    {"keyword": "寵物保健", "name": "維克免疫力關節保健品 貓狗通用", "price_twd": 890, "sold_monthly": 1900, "rating": "4.8"},
    {"keyword": "寵物保健", "name": "益生菌腸道保健粉 貓咪專用 30包", "price_twd": 650, "sold_monthly": 2400, "rating": "4.7"},
    {"keyword": "寵物保健", "name": "Omega3魚油軟膠囊 狗狗毛髮保健", "price_twd": 780, "sold_monthly": 1700, "rating": "4.6"},

    # 狗窩
    {"keyword": "狗窩", "name": "防水耐抓狗狗墊 可拆洗 L號", "price_twd": 599, "sold_monthly": 2700, "rating": "4.6"},
    {"keyword": "狗窩", "name": "記憶棉寵物床墊 多尺寸 XL號", "price_twd": 899, "sold_monthly": 1800, "rating": "4.7"},
    {"keyword": "狗窩", "name": "圓形狗窩保暖抗菌款 可機洗", "price_twd": 449, "sold_monthly": 3300, "rating": "4.5"},

    # 梳毛刷
    {"keyword": "梳毛刷", "name": "寵物除毛梳雙面針梳 貓狗通用", "price_twd": 199, "sold_monthly": 4200, "rating": "4.7"},
    {"keyword": "梳毛刷", "name": "自清式寵物梳毛刷 按壓除毛款", "price_twd": 299, "sold_monthly": 3100, "rating": "4.8"},
    {"keyword": "梳毛刷", "name": "橡膠除毛手套梳 貓咪按摩梳", "price_twd": 159, "sold_monthly": 5600, "rating": "4.6"},

    # 指甲剪
    {"keyword": "指甲剪", "name": "寵物指甲剪貓狗專用 附銼刀", "price_twd": 149, "sold_monthly": 3800, "rating": "4.6"},
    {"keyword": "指甲剪", "name": "LED燈寵物指甲剪 安全防剪過深", "price_twd": 299, "sold_monthly": 2100, "rating": "4.8"},
    {"keyword": "指甲剪", "name": "電動磨甲器 靜音寵物磨爪機", "price_twd": 399, "sold_monthly": 1800, "rating": "4.7"},

    # 寵物牙膏
    {"keyword": "寵物牙膏", "name": "寵物牙膏牙刷組 雞肉口味貓狗用", "price_twd": 199, "sold_monthly": 2900, "rating": "4.6"},
    {"keyword": "寵物牙膏", "name": "指套牙刷寵物潔牙組 3入", "price_twd": 149, "sold_monthly": 3400, "rating": "4.5"},
    {"keyword": "寵物牙膏", "name": "天然酵素寵物牙膏 無氟配方 60g", "price_twd": 249, "sold_monthly": 2200, "rating": "4.7"},

    # 尿布墊
    {"keyword": "尿布墊", "name": "寵物尿布墊超吸收 L號 50入", "price_twd": 299, "sold_monthly": 6800, "rating": "4.7"},
    {"keyword": "尿布墊", "name": "可洗式寵物尿墊 防水四層 XL號", "price_twd": 399, "sold_monthly": 3200, "rating": "4.6"},
    {"keyword": "尿布墊", "name": "炭黑除臭尿布墊 狗狗如廁訓練墊 100入", "price_twd": 499, "sold_monthly": 4100, "rating": "4.8"},

    # 寵物雨衣
    {"keyword": "寵物雨衣", "name": "狗狗雨衣四腳防水反光款 M號", "price_twd": 349, "sold_monthly": 2300, "rating": "4.6"},
    {"keyword": "寵物雨衣", "name": "透明帽寵物雨衣 一件式好穿脫", "price_twd": 249, "sold_monthly": 3100, "rating": "4.5"},
    {"keyword": "寵物雨衣", "name": "加厚防風寵物雨衣 柴犬法鬥款", "price_twd": 499, "sold_monthly": 1700, "rating": "4.7"},

    # 暖墊
    {"keyword": "暖墊", "name": "寵物電熱毯USB加熱保暖墊 自動恆溫", "price_twd": 599, "sold_monthly": 2800, "rating": "4.7"},
    {"keyword": "暖墊", "name": "自發熱寵物保暖墊 不需插電 M號", "price_twd": 299, "sold_monthly": 4200, "rating": "4.5"},
    {"keyword": "暖墊", "name": "記憶棉加熱寵物床墊 四季通用 L號", "price_twd": 799, "sold_monthly": 1900, "rating": "4.8"},

    # 狗玩具
    {"keyword": "狗玩具", "name": "狗狗耐咬磨牙玩具 天然橡膠 M號", "price_twd": 199, "sold_monthly": 5300, "rating": "4.6"},
    {"keyword": "狗玩具", "name": "益智漏食球 狗狗慢食訓練玩具", "price_twd": 249, "sold_monthly": 3800, "rating": "4.7"},
    {"keyword": "狗玩具", "name": "發聲玩具組 狗狗毛絨玩偶 3件組", "price_twd": 299, "sold_monthly": 4100, "rating": "4.5"},

    # 寵物推車
    {"keyword": "寵物推車", "name": "折疊寵物推車四輪避震 15kg以下", "price_twd": 1999, "sold_monthly": 1200, "rating": "4.7"},
    {"keyword": "寵物推車", "name": "太空艙寵物推車透明款 貓狗通用", "price_twd": 2499, "sold_monthly": 800, "rating": "4.8"},
    {"keyword": "寵物推車", "name": "輕量鋁合金寵物推車 單手收折款", "price_twd": 2999, "sold_monthly": 600, "rating": "4.9"},

    # 寵物圍欄
    {"keyword": "寵物圍欄", "name": "寵物圍欄8片組 可自由組合擴充", "price_twd": 799, "sold_monthly": 2600, "rating": "4.6"},
    {"keyword": "寵物圍欄", "name": "加高寵物柵欄 防跳脫款 120cm", "price_twd": 1299, "sold_monthly": 1500, "rating": "4.7"},
    {"keyword": "寵物圍欄", "name": "木質寵物圍欄 北歐風室內狗柵欄", "price_twd": 1599, "sold_monthly": 1100, "rating": "4.8"},

    # 除臭噴劑
    {"keyword": "除臭噴劑", "name": "寵物除臭噴劑 天然酵素消臭 500ml", "price_twd": 249, "sold_monthly": 4500, "rating": "4.7"},
    {"keyword": "除臭噴劑", "name": "貓咪尿液除臭噴霧 地毯布面專用", "price_twd": 299, "sold_monthly": 3200, "rating": "4.8"},
    {"keyword": "除臭噴劑", "name": "寵物空間除臭芳香噴劑 薰衣草香", "price_twd": 199, "sold_monthly": 3800, "rating": "4.5"},
]
