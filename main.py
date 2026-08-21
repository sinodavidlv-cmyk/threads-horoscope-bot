import os
import time  
import requests
from datetime import datetime, timezone, timedelta
from google import genai

# 1. 呼叫 Gemini AI 生成每日 12 星座運勢
def generate_horoscope_content():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("❌ 找不到 GEMINI_API_KEY 環境變數")

    client = genai.Client(api_key=api_key)

    # 1. 先計算台灣時間 (UTC+8) 的當日日期
    tz_taiwan = timezone(timedelta(hours=8))
    today_str = datetime.now(tz_taiwan).strftime("%m/%d")

    # 2. 將 prompt 改為 f-string (注意 prompt = f""" 的小寫 f)
    # 並直接把 {today_str} 帶入 Prompt 內
    prompt = f"""
你是一位講話精闢、語氣扎心又幽默的 Threads 星座語錄專家。
請為 Threads 社群平台撰寫一則繁體中文「今日 12 星座運勢與地雷警示」。

要求：
1. 開頭標題格式必須為 "{today_str}今日12星座運勢,幸運色和數字: "，後面接一句超吸睛的犀利金句或爭議性觀點。
2. 內容打破傳統，加入「吐槽點/相處地雷」與「毒舌金句」，語氣要接地氣、像真人朋友在聊天，嚴禁教科書式的溫馨罐頭句。
3. 簡短列出 12 星座今日運勢，每個星座用一句話精闢點出「今日最慘/最爽的事」或「要小心哪種人」。
4. 結尾不要寫溫馨提醒！改為一句「引導戰翻/Tag朋友/自首留言」的強烈互動問句（例如：@你身邊最容易踩這地雷的朋友 / 哪一個星座今天又在發瘋？留言自首）。
5. 全部字數，包括符號、特殊字元都必須嚴格控制在 450 字內，排版適合手機閱讀。
"""

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt
            )
            return response.text
        except Exception as e:
            if attempt == 2:
                raise e
            time.sleep(3)

# 2. 自動刷新 Threads Long-Lived Token (延展 60 天效期)
def refresh_threads_token():
    token = os.environ.get("THREADS_ACCESS_TOKEN")
    url = "https://graph.threads.net/refresh_access_token"
    params = {
        "grant_type": "th_refresh_token",
        "access_token": token
    }
    try:
        res = requests.get(url, params=params).json()
        if "access_token" in res:
            print("🔄 成功刷新 Threads 長效 Token！")
            return res["access_token"]
    except Exception as e:
        print(f"⚠️ Token 刷新提示: {e}")
    return token

# 3. 發布貼文至 Threads API
def post_to_threads(text_content):
    user_id = os.environ.get("THREADS_USER_ID")
    access_token = refresh_threads_token()
    
    # 步驟 A: 建立貼文 Media Container
    create_url = f"https://graph.threads.net/v1.0/{user_id}/threads"
    payload = {
        "media_type": "TEXT",
        "text": text_content,
        "access_token": access_token
    }
    
    res = requests.post(create_url, data=payload).json()
    creation_id = res.get("id")
    
    if not creation_id:
        print("❌ 建立 Threads 貼文容器失敗:", res)
        return False
        
    print(f"✅ 貼文容器建立成功! Container ID: {creation_id}")
    print("⏳ 等待 Meta 後端同步資料 (10秒)...")
    time.sleep(10)
    # 步驟 B: 發布容器
    publish_url = f"https://graph.threads.net/v1.0/{user_id}/threads_publish"
    pub_payload = {
        "creation_id": creation_id,
        "access_token": access_token
    }
    
    pub_res = requests.post(publish_url, data=pub_payload).json()
    published_id = pub_res.get("id")
    
    if published_id:
        print(f"🎉 成功自動發布貼文至 Threads! Post ID: {published_id}")
        return True
    else:
        print("❌ 發布貼文失敗:", pub_res)
        return False

if __name__ == "__main__":
    print("🔮 開始生成今日星座貼文...")
    content = generate_horoscope_content()
    print("📝 生成貼文預覽：\n" + "-"*30 + f"\n{content}\n" + "-"*30)
    post_to_threads(content)
