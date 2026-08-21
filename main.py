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
    
    prompt = f"""請為 Threads 社群平台撰寫一則繁體中文「今日 12 星座運勢短評與幸運指南」。
要求：
1. 全文開頭請精確使用格式：✨【{today_str} 今日十二星座運勢幸運色與數字】✨
2. 使用討喜的 Emoji 與適合手機閱讀的排版。
3. 內容包含：
   - 當日幸運星 Top 3（含理由）。
   - 12 星座簡短點評（含運勢焦點、幸運色與幸運數字）。
   - 一句話溫馨提醒與給予滿滿能量的結尾。
4. 全文字數精確控制在 420 字至 480 字之間。"""
    
    return generate_ai_content(prompt)

def refresh_threads_token():
    """自動刷新 Threads Long-Lived Token (延展 60 天效期)"""
    token = THREADS_ACCESS_TOKEN
    url = "https://graph.threads.net/refresh_access_token"
    params = {"grant_type": "th_refresh_token", "access_token": token}
    try:
        res = requests.get(url, params=params).json()
        if "access_token" in res:
            print("🔄 成功刷新 Threads 長效 Token！")
            return res["access_token"]
    except Exception as e:
        print(f"⚠️ Token 刷新提示: {e}")
    return token

def post_to_threads(text_content):
    """發布貼文至 Threads API"""
    if not THREADS_USER_ID or not THREADS_ACCESS_TOKEN:
        print("❌ 缺少 THREADS_USER_ID 或 THREADS_ACCESS_TOKEN 環境變數，無法發布。")
        return False

    access_token = refresh_threads_token()

    # Step 1: 建立 Media Container
    creation_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    payload = {
        "media_type": "TEXT",
        "text": text_content,
        "access_token": access_token
    }
    
    try:
        res = requests.post(creation_url, data=payload).json()
        creation_id = res.get("id")
        if not creation_id:
            print("❌ 建立 Threads 貼文容器失敗:", res)
            return False
        print(f"✅ 貼文容器建立成功! Container ID: {creation_id}")
    except Exception as e:
        print(f"❌ 建立 Container 失敗: {e}")
        return False

    # 等待 container 準備完成
    time.sleep(5)

    # Step 2: 發布 Container
    publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
    pub_payload = {
        "creation_id": creation_id,
        "access_token": access_token
    }
    
    try:
        pub_res = requests.post(publish_url, data=pub_payload).json()
        published_id = pub_res.get("id")
        if published_id:
            print(f"🎉 成功自動發布貼文至 Threads! Post ID: {published_id}")
            return True
        else:
            print("❌ 發布貼文失敗:", pub_res)
            return False
    except Exception as e:
        print(f"❌ 發布貼文失敗: {e}")
        return False

if __name__ == "__main__":
    tw_time = datetime.now(timezone.utc) + timedelta(hours=8)
    today_str = tw_time.strftime("%m/%d")

    tasks = [
        {
            "name": "星座運勢",
            "prompt": None
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

    total_tasks = len(tasks)

    for index, task in enumerate(tasks, start=1):
        print(f"\n🔮 [{index}/{total_tasks}] 正在處理：{task['name']}...")
        
        if task["prompt"] is None:
            content = generate_horoscope_content()
        else:
            content = generate_ai_content(task["prompt"])
            
        if not content:
            print(f"⚠️ {task['name']} 內容生成失敗，跳過此任務。")
            continue

        if len(content) > 480:
            content = content[:475] + "..."
            
        print("📝 貼文預覽：\n" + "-"*30 + f"\n{content}\n" + "-"*30)
        
        post_to_threads(content)
        
        if index < total_tasks:
            print("⏳ 等待 15 秒後準備處理下一篇...")
            time.sleep(15)

    print("\n🎉 所有 4 篇貼文已全部發布完成！")
