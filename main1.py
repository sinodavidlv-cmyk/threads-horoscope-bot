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
你是一位講話精闢、語氣扎心又極具幽默感的 Threads 星座語錄專家。
請為 Threads 平台撰寫一則繁體中文「{today_str} 12 星座地雷與運勢地獄梗」。

目標：極大化「轉發率（Repost）」與「留言區戰翻率」，吸引更多星座迷追蹤。文風必須完全像真人朋友在 Threads 上發廢文/抱怨，絕對拒絕 AI 罐頭感。

排版與結構要求：
1. 【開頭 Hook】：第一行直接放最具爭議、最扎心的爆款金句（例如：「今日最容易讓身邊人集體抓狂的星座出爐了」），緊接著一行標註日期的簡短標題（format: {today_str} 星座地雷警示）。
2. 【焦點警示】：挑出 1~2 個今日「最慘/最欠罵」的苦主星座做重點吐槽，並附上幸運色與數字。
3. 【12 星座精簡警示】：其餘星座以極度接地氣、毒舌且精闢的一句話列出（聚焦於「相處地雷」或「今日最爽/最慘時刻」）。
4. 【Threads 爆款互動結尾】：結尾不要任何溫馨提醒，改成一句能引發「強烈共鳴自首」或「Tag 朋友出來面對」的爭議性問句。
5. 【平台格式與字數限制】：
   - 全文（含標點、符號、空格）必須嚴格控制在 420 字以內，以確保不超過 Threads 平台限制，且必須保持文句完整，絕對不能切斷句子。
   - 適度使用換行與簡潔符號，打造適合手機快速滑過的排版。
"""

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
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
        print(f"⚠️ Token 刷新發生錯誤: {e}")
        raise ValueError("無法取得或刷新 Threads Access Token，請檢查環境變數。")

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
    
    res = requests.post(create_url, json=payload).json()
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
    
    pub_res = requests.post(publish_url, json=pub_payload).json()
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
