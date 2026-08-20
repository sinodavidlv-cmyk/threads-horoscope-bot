import os
import time
from datetime import datetime, timezone, timedelta
import requests

# 取得環境變數
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
THREADS_USER_ID = os.environ.get("THREADS_USER_ID")
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")

def generate_ai_content(prompt_text):
    """呼叫 Gemini API 生成通用內容"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"❌ AI 內容生成失敗: {e}")
        return None

def generate_horoscope_content():
    """專門生成星座運勢的函式"""
    tw_time = datetime.now(timezone.utc) + timedelta(hours=8)
    today_str = tw_time.strftime("%m/%d")
    
    prompt = f"""請幫我生成今日十二星座運勢，請包含以下元素：
1. 開頭請用 "{today_str} 今日十二星座運勢:"
2. 包含每一個星座的今日運勢簡短分析與幸運指數/建議。
3. 文末附上一句專屬祝福語。
4. 全文嚴格限制在 400 字以內，善用 Emoji 標籤與換行。"""
    
    return generate_ai_content(prompt)

def post_to_threads(text_content):
    """發布貼文至 Threads API"""
    if not THREADS_USER_ID or not THREADS_ACCESS_TOKEN:
        print("❌ 缺少 Threads 認證資訊，無法發布。")
        return

    # Step 1: 建立 Media Container
    creation_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    payload = {
        "media_type": "TEXT",
        "text": text_content,
        "access_token": THREADS_ACCESS_TOKEN
    }
    
    try:
        res = requests.post(creation_url, data=payload)
        res.raise_for_status()
        creation_id = res.json().get("id")
        print(f"✅ Container 建立成功，ID: {creation_id}")
    except Exception as e:
        print(f"❌ 建立 Container 失敗: {e}")
        return

    # 等待 container 準備完成
    time.sleep(5)

    # Step 2: 發布 Container
    publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
    publish_payload = {
        "creation_id": creation_id,
        "access_token": THREADS_ACCESS_TOKEN
    }
    
    try:
        pub_res = requests.post(publish_url, data=publish_payload)
        pub_res.raise_for_status()
        print(f"🎉 貼文發布成功！ID: {pub_res.json().get('id')}")
    except Exception as e:
        print(f"❌ 發布貼文失敗: {e}")

if __name__ == "__main__":
    # 1. 取得台灣目前日期 (UTC+8)
    tw_time = datetime.now(timezone.utc) + timedelta(hours=8)
    today_str = tw_time.strftime("%m/%d")

    # 2. 定義 4 個發布任務
    tasks = [
        {
            "name": "星座運勢",
            "prompt": None  # 代表使用 generate_horoscope_content()
        },
        {
            "name": "星座配對",
            "prompt": f"""根據今日的星座運勢去搭配出今日最佳的配對運勢: 與其他星座的配對情況，請分成在愛情、友情和職場關係方面這三大類.最後結尾加一句根據今日運勢專屬的祝福語. 全文嚴格限制在400字以內.開頭請用 "{today_str} 今日十二星座最佳配對:" """
        },
        {
            "name": "生肖運勢",
            "prompt": f"""今日十二生肖運勢與建議. 然後加一個今日十二生肖運勢的簡短100個字元相關的生肖心理測試 , 心理測試要有問有答且有趣,最後結尾加一句根據今日運勢專屬的祝福語. 上述請依序排列並將全文嚴格限制在400字以內 . 開頭請用 "{today_str} 今日十二生肖運勢:" """
        },
        {
            "name": "生肖三合六合",
            "prompt": f"""今日十二生肖三合六合貴人與建議. 全文嚴格限制在400字以內 . 開頭請用 "{today_str} 今日十二生肖三合六合:" """
        }
    ]

    # 3. 計算總數並執行發布迴圈
    total_tasks = len(tasks)

    for index, task in enumerate(tasks, start=1):
        print(f"\n🔮 [{index}/{total_tasks}] 正在處理：{task['name']}...")
        
        # (A) 即時生成 AI 內容
        if task["prompt"] is None:
            content = generate_horoscope_content()
        else:
            content = generate_ai_content(task["prompt"])
            
        if not content:
            print(f"⚠️ {task['name']} 內容生成失敗，跳過此任務。")
            continue

        # (B) 安全字數裁切（防止超過 500 字元限制）
        if len(content) > 480:
            content = content[:475] + "..."
            
        print("📝 貼文預覽：\n" + "-"*30 + f"\n{content}\n" + "-"*30)
        
        # (C) 呼叫 Threads 發布 API
        post_to_threads(content)
        
        # (D) 冷卻等待機制（最後一篇無需等待）
        if index < total_tasks:
            print("⏳ 等待 15 秒後準備處理下一篇...")
            time.sleep(15)

    print("\n🎉 所有 4 篇貼文已全部發布完成！")
