import requests, json, os

THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")

def post_to_threads(content):
    url = "https://graph.threads.net/v1.0/me/threads"
    headers = {"Authorization": f"Bearer {THREADS_ACCESS_TOKEN}"}
    payload = {"text": content}
    res = requests.post(url, headers=headers, data=payload)
    return res.json()

if __name__ == "__main__":
    with open("posts.json", "r", encoding="utf-8") as f:
        posts = json.load(f)
    for post in posts:
        result = post_to_threads(post)
        print("Posted:", result)
