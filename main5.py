import os
import time  
import requests
from datetime import datetime, timezone, timedelta
from google import genai

# 1. 呼叫 Gemini AI 生成每日 12 新聞
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
你是一位風格謹慎、精通國際事件新聞的語錄型專家。
請為 Threads 社群平台撰寫一則繁體中文「今日新聞短評總整理」。

【合規與內容安全防線（極重要，必須嚴格遵守）】
1. 客觀中立：絕不包含歧視（性別、種族、宗教、地域等）、仇恨言論、恐攻與暴力宣揚、無根據的污衊或個人攻擊。
2. 事實至上：僅引述具備時間、地點、人物、事件的主流權威媒體事實，嚴禁無中生有、捏造內容或轉述未經證實的謠言（內容不實）。
3. 政治與敏感議題去情緒化：涉及政治、國際衝突或社會事件時，僅客觀陳述「發生了什麼事」，不使用煽動性、極端或帶有強烈立場的用語。

【貼文要求】
1. 總結今天一大早的國際與台灣頭條新聞重點（須涵蓋主要事件、人物、地點和時間）。
2. 開頭要有一句超吸睛的標題，格式必須為："{today_str}今日國際與台灣新聞焦點: "。
3. 使用簡短的文字與討喜的 Emoji 排版，方便手機快速閱讀。
4. 結尾加上適合今日情境的一句話溫馨提醒。
5. 全部字數（含標點符號、Emoji、特殊字元）必須嚴格控制在 450 字以內。
"""

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt
    )
    return response.text

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
