import os
import time  
import requests
from datetime import datetime, timezone, timedelta
from google import genai

# 1. 呼叫 Gemini AI 生成每日 12 星座配對運勢
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
你是一位講話精闢、帶有一點幽默感與犀利洞察力的 Threads 星座語錄大師。
請為 Threads 撰寫一則繁體中文「今日 12 星座最佳配對與火花解析」。

【消除 AI 感與爆發互動規則】
1. 人性化語氣：拒絕教科書式的罐頭評語！請用 Threads 爆款貼文最愛的「語錄體」或「扎心金句」，文字要接地氣、有共鳴感。
2. 製造話題與對立：說明配對時，除了寫優點，也要加入趣味的「相處地雷」或「吐槽點」（例如：愛情是天作之合，但小心吵架時兩個都硬脾氣）。
3. 強力引導互動（鉤子）：結尾必須包含高轉發、高留言的行動呼籲（Call to Action），引導讀者標記朋友或留言自首。

【貼文要求】
1. 開頭標題：格式必須為 "{today_str}今日十二星座最佳配對: "，後面接一句超吸睛的犀利金句。
2. 配對內容：精簡列出今日「愛情」、「友情」、「職場」的最佳配對組合，並附上各一組「互動火花/吐槽短評」。
3. 討喜排版：使用簡短文字與 Emoji，嚴禁密密麻麻的文字塊，適合手機快速瀏覽。
4. 結尾 Call to Action（三選一或綜合）：
   - 「標記你身邊那個 [特定星座]，告訴他今天對我好一點！」
   - 「底下留言你的星座，看看今天有沒有你的天命神隊友出沒👇」
5. 字數限制：全部字數（含標點符號、Emoji、特殊字元）必須嚴格控制在 420 字以內，留出閱讀呼吸感。
"""

    response = client.models.generate_content(
        model="gemini-3.6-flash",
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
