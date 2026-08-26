import requests, json, os

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def generate_post(trending_item):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    headers = {"Authorization": f"Bearer {GEMINI_API_KEY}"}
    payload = {
        "contents": [{
            "parts": [{
                "text": f"請把以下熱門話題改寫成幽默、互動式 Threads 貼文，200字以內：{trending_item}"
            }]
        }]
    }
    res = requests.post(url, headers=headers, json=payload)
    data = res.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

if __name__ == "__main__":
    with open("trending.json", "r", encoding="utf-8") as f:
        trending = json.load(f)
    posts = []
    for item in trending["google"][:3] + [p["title"] for p in trending["reddit"][:3]]:
        posts.append(generate_post(item))
    with open("posts.json", "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
