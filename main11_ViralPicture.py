import os
import xml.etree.ElementTree as ET
import requests

THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def fetch_google_trends():
    """抓取台灣 Google 趨勢熱門話題"""
    try:
        res = requests.get('https://trends.google.com.tw/trending/rss?geo=TW', headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if res.status_code != 200:
            return []
        root = ET.fromstring(res.content)
        titles = []
        for item in root.findall('.//item'):
            title_elem = item.find('title')
            if title_elem is not None and title_elem.text:
                titles.append(title_elem.text)
        return titles[:5]
    except Exception as e:
        print(f"Fetch Google Trends Error: {e}")
        return []

def fetch_reddit_trending():
    """抓取 Reddit 熱門話題"""
    url = "https://www.reddit.com/r/popular.json"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            return []
        data = res.json()
        if not isinstance(data, dict) or "data" not in data or "children" not in data["data"]:
            return []
        return [item["data"]["title"] for item in data["data"]["children"][:5] if "data" in item and "title" in item["data"]]
    except Exception as e:
        print(f"Fetch Reddit Error: {e}")
        return []

def score_topic(topic):
    """評分話題吸引力"""
    score = 0
    if len(topic) <= 15:
        score += 2
    if any(word in topic for word in ["爆", "笑", "戰", "梗", "熱", "台灣"]):
        score += 3
    return score

def generate_viral_content_with_gemini(topic):
    """若要串接 Gemini API 產生吸睛文案與構想可在此實作"""
    # 範例結構：呼叫 google-generativeai SDK 或透過 REST API 讓 Gemini 產出貼文內容
    prompt = f"請根據今日話題「{topic}」，寫一篇 Threads 爆紅短文，並附帶互動問題與 Hashtag。"
    # 實作您的 Gemini 呼叫邏輯...
    return f"🔥 今日爆紅話題：{topic}\n\n這波你怎麼看？\n互動問題：你挺哪一派？\n#爆紅 #話題 #{topic[:5]}"

def post_to_threads(content):
    """發布貼文至 Threads API"""
    if not THREADS_ACCESS_TOKEN:
        print("Error: THREADS_ACCESS_TOKEN is missing.")
        return None
        
    url = "https://graph.threads.net/v1.0/me/threads"
    headers = {"Authorization": f"Bearer {THREADS_ACCESS_TOKEN}"}
    payload = {
        "media_type": "TEXT",
        "text": content
    }
    try:
        res = requests.post(url, headers=headers, data=payload, timeout=15)
        return res.json()
    except Exception as e:
        print(f"Post to Threads Error: {e}")
        return None

if __name__ == "__main__":
    google_topics = fetch_google_trends()
    reddit_topics = fetch_reddit_trending()
    all_topics = google_topics + reddit_topics
    
    if not all_topics:
        print("未抓取到任何有效話題，程式終止。")
    else:
        best_topic = sorted(all_topics, key=score_topic, reverse=True)[0]
        print(f"選出最佳話題: {best_topic}")
        
        # 產生貼文內容
        caption = generate_viral_content_with_gemini(best_topic)
        
        # 發布
        result = post_to_threads(caption)
        print("Posted Result:", result)
