import requests

def fetch_google_trends():
    # 範例：使用 Google Trends API (需第三方套件 pytrends)
    from pytrends.request import TrendReq
    pytrends = TrendReq(hl='en-US', tz=360)
    pytrends.build_payload(kw_list=['news'])
    trending = pytrends.trending_searches(pn='taiwan')
    return trending[0].tolist()[:5]  # 取前五名

def fetch_reddit_trending():
    url = "https://www.reddit.com/r/popular.json"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    data = res.json()
    posts = []
    for item in data["data"]["children"][:5]:
        posts.append({
            "title": item["data"]["title"],
            "url": item["data"]["url"]
        })
    return posts

if __name__ == "__main__":
    google_trends = fetch_google_trends()
    reddit_trends = fetch_reddit_trending()
    with open("trending.json", "w", encoding="utf-8") as f:
        import json
        json.dump({"google": google_trends, "reddit": reddit_trends}, f, ensure_ascii=False, indent=2)
