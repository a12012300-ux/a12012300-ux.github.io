# 社群媒體自動發文設定指南

## 需要設定的 GitHub Secrets

前往：`你的 GitHub repo` → Settings → Secrets and variables → Actions → New repository secret

### 必填（Claude AI）
| Secret 名稱 | 說明 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API Key（從 console.anthropic.com 取得） |

### Threads 自動發文
| Secret 名稱 | 說明 |
|---|---|
| `THREADS_USER_ID` | 你的 Threads 用戶 ID |
| `THREADS_ACCESS_TOKEN` | Threads API 存取 Token |

### Instagram 自動發文
| Secret 名稱 | 說明 |
|---|---|
| `IG_USER_ID` | Instagram Business 帳號 ID |
| `IG_ACCESS_TOKEN` | Meta 長效存取 Token（60天有效） |

---

## Threads API 申請步驟

1. 前往 https://developers.facebook.com/
2. 建立 Meta Developer App（選 Other → Consumer）
3. 在 App 中加入「Threads API」產品
4. 產生 User Access Token
5. 換成長效 Token（有效期 60 天）

**取得 Threads User ID：**
```
curl -s "https://graph.threads.net/v1.0/me?fields=id,username&access_token=YOUR_TOKEN"
```

---

## Instagram Business API 申請步驟

1. 將 Instagram 帳號切換成「商業帳號」或「創作者帳號」
2. 建立一個 Facebook 粉絲專頁並連結到 IG 帳號
3. 前往 https://developers.facebook.com/ 建立 App
4. 加入「Instagram Graph API」產品
5. 申請 `instagram_basic` + `instagram_content_publish` 權限

**取得 IG User ID：**
```
curl "https://graph.facebook.com/v19.0/me/accounts?access_token=YOUR_PAGE_TOKEN"
# 找到 instagram_business_account id
```

---

## Token 到期處理

Instagram 和 Threads 的 Token 有效期為 60 天。

建議：每 50 天手動更新一次 Token，並更新 GitHub Secrets。

未來版本將加入自動 Token 刷新功能。

---

## 手動觸發測試

設定完成後，可以手動觸發測試：

1. 前往 GitHub repo → Actions → 每日自動發文
2. 點擊「Run workflow」
3. 輸入文章數量（預設5篇）
4. 點擊「Run workflow」按鈕

觀察 Actions 日誌確認每個步驟是否成功。
