"""
pipeline/get_youtube_token.py
【只需在本機跑一次】取得 YouTube Refresh Token
跑完後把 refresh_token 存到 GitHub Secrets: YOUTUBE_REFRESH_TOKEN

使用步驟：
1. 先去 Google Cloud Console 建立 OAuth2 憑證
2. 把 client_id 和 client_secret 填到下方
3. 執行：python pipeline/get_youtube_token.py
4. 瀏覽器會自動開啟，登入 Google 帳號授權
5. 把印出的 refresh_token 存到 GitHub Secrets
"""

CLIENT_ID     = "你的_CLIENT_ID.apps.googleusercontent.com"
CLIENT_SECRET = "你的_CLIENT_SECRET"

# ── 以下不需要修改 ─────────────────────────────────────────────
import json, webbrowser
from urllib.parse import urlencode
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import urllib.request

SCOPES       = "https://www.googleapis.com/auth/youtube.upload"
REDIRECT_URI = "http://localhost:8080"
AUTH_URL     = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL    = "https://oauth2.googleapis.com/token"

auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params   = parse_qs(urlparse(self.path).query)
        auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h1>授權成功！回到終端機看 refresh token</h1>")

    def log_message(self, *args):
        pass


def main():
    params = {
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         SCOPES,
        "access_type":   "offline",
        "prompt":        "consent",
    }
    url = f"{AUTH_URL}?{urlencode(params)}"
    print(f"  開啟瀏覽器授權...")
    webbrowser.open(url)

    # 等待回調
    server = HTTPServer(("localhost", 8080), CallbackHandler)
    server.handle_request()

    if not auth_code:
        print("  [!] 未取得授權碼")
        return

    # 換取 token
    data = urlencode({
        "code":          auth_code,
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri":  REDIRECT_URI,
        "grant_type":    "authorization_code",
    }).encode()

    req  = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read())

    refresh_token = result.get("refresh_token", "")
    if refresh_token:
        print("\n" + "="*55)
        print("  ✅ 成功取得 Refresh Token！")
        print("="*55)
        print(f"\n  REFRESH_TOKEN:\n  {refresh_token}\n")
        print("  請把上方 token 加到 GitHub Secrets：")
        print("  Key:   YOUTUBE_REFRESH_TOKEN")
        print(f"  Value: {refresh_token}")
        print("\n  同時加入：")
        print(f"  YOUTUBE_CLIENT_ID     = {CLIENT_ID}")
        print(f"  YOUTUBE_CLIENT_SECRET = {CLIENT_SECRET}")
        print("="*55)
    else:
        print(f"  [!] 失敗：{result}")


if __name__ == "__main__":
    main()
