import requests

def fetch_google_trends():
    # 使用 Google Trends API (需第三方套件 pytrends)
    from pytrends.request import TrendReq
    pytrends = TrendReq(hl='en-US', tz=360)
    # 指定台灣地區，抓 AI 的搜尋趨勢
    pytrends.build_payload(kw_list=['AI'], geo='TW', timeframe='now 7-d')
    trending = pytrends.interest_over_time()
    # 取前五個欄位名稱（關鍵字）
    return trending.columns.tolist()[:5]

def fetch_reddit_trending():
    url = "https://www.reddit.com/r/popular.json"
    headers = {"User-Agent": "Mozilla/5.0"}  # 必須加上 User-Agent
    res = requests.get(url, headers=headers)

    if res.status_code == 200:
        data = res.json()
        posts = []
        for item in data["data"]["children"][:5]:
            posts.append({
                "title": item["data"]["title"],
                "url": item["data"]["url"]
            })
        return posts
    else:
        # 如果失敗就回傳空清單，避免 JSONDecodeError
        return []

if __name__ == "__main__":
    google_trends = fetch_google_trends()
    reddit_trends = fetch_reddit_trending()
    with open("trending.json", "w", encoding="utf-8") as f:
        import json
        json.dump({"google": google_trends, "reddit": reddit_trends}, f, ensure_ascii=False, indent=2)
