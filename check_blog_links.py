import sys, re, glob, os
sys.stdout.reconfigure(encoding='utf-8')

posts = glob.glob('posts/*.html')
print(f"共 {len(posts)} 篇文章\n")
for f in sorted(posts)[:3]:
    print(f"=== {os.path.basename(f)} ===")
    with open(f, encoding='utf-8') as fp:
        html = fp.read()
    links = re.findall(r'href="([^"]+)"', html)
    shopee_links = [l for l in links if 'shopee' in l.lower() or 's.shopee' in l.lower()]
    other_links = [l for l in links if l.startswith('http') and 'shopee' not in l.lower()]
    print(f"蝦皮連結: {shopee_links}")
    print(f"其他外連: {other_links}")
    print()
