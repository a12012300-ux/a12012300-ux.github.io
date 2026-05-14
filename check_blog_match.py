import sys, json, re, glob
sys.stdout.reconfigure(encoding='utf-8')

with open('articles_meta.json', encoding='utf-8') as f:
    meta = json.load(f)

print("=== 部落格文章對照 ===\n")
for i, m in enumerate(meta, 1):
    post_path = f"posts/{m['filename']}"
    exists = __import__('os').path.exists(post_path)

    if exists:
        with open(post_path, encoding='utf-8') as f:
            html = f.read()
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE|re.DOTALL)
        article_h1 = re.sub(r'<[^>]+>', '', h1.group(1)).strip() if h1 else '無H1'
        links = re.findall(r'href="(https://s\.shopee\.tw/[^"]+)"', html)
        affiliate = links[0] if links else '無聯盟連結'
    else:
        article_h1 = '❌ 檔案不存在'
        affiliate = ''

    print(f"{i}. 標題：{m['title'][:35]}")
    print(f"   H1  ：{article_h1[:35]}")
    print(f"   連結：{affiliate}")
    print(f"   分類：{m['label']} / {m['keyword']}")
    match = m['keyword'] in m['title'] or m['label'] in article_h1
    print(f"   符合：{'✅' if exists else '❌ 檔案遺失'}")
    print()
