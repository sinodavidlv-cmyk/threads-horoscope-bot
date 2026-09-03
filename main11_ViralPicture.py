import os
import xml.etree.ElementTree as ET
import requests

THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def fetch_google_trends():
  try:
    res = requests.get(
        'https://trends.google.com.tw/trending/rss?geo=TW',
        headers={'User-Agent': 'Mozilla/5.0'},
    )
    root = ET.fromstring(res.content)
    return [item.find('title').text for item in root.findall('.//item')][:5]
  except Exception:
    return ['熱門話題']

def fetch_reddit_trending():
    url = "https://www.reddit.com/r/popular.json"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            return []
        data = res.json()
        if not isinstance(data, dict) or "data" not in data or "children" not in data["data"]:
            return []
        return [item["data"]["title"] for item in data["data"]["children"][:5]]
    except Exception:
        return []

def score_topic(topic):
    score = 0
    if len(topic) <= 10: score += 2
    if any(word in topic for word in ["爆", "笑", "戰", "梗"]): score += 3
    return score

def generate_prompt(topic):
    return f"""
請根據今日話題「{topic}」，生成一張最有爆紅潛力的圖片構想。
圖片需具備：
1. 強烈情緒共鳴（搞笑、感動或荒謬）
2. 明顯反差（可愛 vs. 戰鬥、嚴肅 vs. 輕鬆）
3. 二創潛力（可改字、可模仿）
4. 互動性（引導留言或投票）
請輸出：
- 爆紅標題（10字內）
- 圖片主題描述（30字內）
- 互動問題（如「你挺哪一派？」）
"""

def post_to_threads(content):
    url = "https://graph.threads.net/v1.0/me/threads"
    headers = {"Authorization": f"Bearer {THREADS_ACCESS_TOKEN}"}
    payload = {"text": content}
    res = requests.post(url, headers=headers, data=payload)
    return res.json()

if __name__ == "__main__":
    google = fetch_google_trends()
    reddit = fetch_reddit_trending()
    all_topics = google + reddit
    best_topic = sorted(all_topics, key=score_topic, reverse=True)[0]

    prompt = generate_prompt(best_topic)
    caption = f"🔥 今日爆紅話題：{best_topic}\n互動問題：你挺哪一派？ #爆紅 #梗圖"

    result = post_to_threads(caption)
    print("Posted:", result)
