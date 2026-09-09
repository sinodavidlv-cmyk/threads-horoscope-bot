import os
import time  
import requests
from datetime import datetime, timezone, timedelta
from google import genai

# 1. 呼叫 Gemini AI 生成每日 12 星座運勢與熱門留言_
def generate_horoscope_content():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("❌ 找不到 GEMINI_API_KEY 環境變數")

    client = genai.Client(api_key=api_key)

    tz_taiwan = timezone(timedelta(hours=8))
    today_str = datetime.now(tz_taiwan).strftime("%m/%d")

# 隨機角色與語氣池
    personas = [
        "毒舌傲嬌系星座專家，講話一針見血但其實很準。",
        "瘋狂迷因連發的社群小編，喜歡用網路流行語對話。",
        "黑色幽默派的厭世導師，把運勢講得像人生災難現場但很好笑。",
        "高情商的溫暖心靈導師，喜歡用微酸帶甜的語氣虧人。"
    ]
    current_persona = random.choice(personas)

    # 主貼文 Prompt（100% 保留你原本的要求與格式，僅動態注入人設）
    prompt = f"""
你是一位擁有以下風格的專家：【{current_persona}】。
請為 Threads 社群平台撰寫一則繁體中文「今日 12 星座短評總整理」。

要求：
1. 今日十二星座與其星象的運勢,幸運顏色和幸運數字。
2. 開頭要有一句超吸睛的標題，並且標題開頭請用格式 "{today_str}今日12星座運勢,幸運色和數字: "。
3. 使用簡短精簡的文字與討喜的 Emoji 排版（每個星座評語不超過 15 個字）。
4. 結尾適合當日運勢的一句話溫馨提醒。
5. 全部字數，包括符號、特殊字元都必須嚴格控制在 400 字內，排版適合手機閱讀。
"""

    # 隨機自回留言切入角度
    reply_prompts = [
        "請針對今天的星座運勢，寫一則短小精悍（50字以內）的自回留言。語氣要像個愛吐槽的網友，並強烈引導讀者留言（例如：@你身邊最倒楣的朋友）。不要寫任何標題，直接輸出留言文字即可。",
        "請寫一則 Threads 上的熱門第一樓留言（50字以內），吐槽今天某個運勢最慘的星座，並叫大家留言卡位。不要寫任何標題，直接輸出留言文字即可。",
        "請寫一則幽默的自回互動留言（50字以內），問大家今天是不是也跟某個星座一樣心情很爛，引導洗版留言。不要寫任何標題，直接輸出留言文字即可。"
    ]
    reply_prompt = random.choice(reply_prompts)   

    for attempt in range(3):
        try:
            res_main = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )
            res_reply = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=reply_prompt
            )
            
            main_text = res_main.text.replace('\n\n', '\n').strip()
            reply_text = res_reply.text.strip()
            
            return main_text, reply_text
        except Exception as e:
            if attempt == 2:
                raise e
            time.sleep(10)

# 2. 自動刷新 Threads Long-Lived Token
def refresh_threads_token():
    token = os.environ.get("THREADS_ACCESS_TOKEN")
    url = "https://graph.threads.net/refresh_access_token"
    params = {
        "grant_type": "th_refresh_token",
        "access_token": token
    }
    try:
        res = requests.get(url, params=params, timeout=15).json()
        if "access_token" in res:
            print("🔄 成功刷新 Threads 長效 Token！")
            return res["access_token"]
    except Exception as e:
        print(f"⚠️ Token 刷新提示: {e}")
    return token

# 3. 發布貼文與自動自回至 Threads API
def post_to_threads(text_content, reply_content):
    user_id = os.environ.get("THREADS_USER_ID")
    access_token = refresh_threads_token()
    
    # 建立主貼文容器
    create_url = f"https://graph.threads.net/v1.0/{user_id}/threads"
    payload = {
        "media_type": "TEXT",
        "text": text_content,
        "access_token": access_token
    }
    
    res = requests.post(create_url, data=payload, timeout=15).json()
    creation_id = res.get("id")
    
    if not creation_id:
        print("❌ 建立 Threads 貼文容器失敗:", res)
        return False
        
    print(f"✅ 主貼文容器建立成功! Container ID: {creation_id}")
    print("⏳ 等待 Meta 後端同步資料 (10秒)...")
    time.sleep(10)

    # 發布主貼文
    publish_url = f"https://graph.threads.net/v1.0/{user_id}/threads_publish"
    pub_payload = {
        "creation_id": creation_id,
        "access_token": access_token
    }
    
    pub_res = requests.post(publish_url, data=pub_payload, timeout=30).json()
    published_id = pub_res.get("id")
    
    if not published_id:
        print("❌ 發布主貼文失敗:", pub_res)
        return False

    print(f"🎉 成功自動發布貼文至 Threads! Post ID: {published_id}")
    
    # 自動發布第一條留言
    print("💬 開始自動發布第一樓留言...")
    time.sleep(5)
    
    reply_container_payload = {
        "media_type": "TEXT",
        "text": reply_content,
        "reply_to_id": published_id,
        "access_token": access_token
    }
    
    reply_res = requests.post(create_url, data=reply_container_payload).json()
    reply_creation_id = reply_res.get("id")
    
    if reply_creation_id:
        time.sleep(5)
        pub_reply_res = requests.post(publish_url, data={"creation_id": reply_creation_id, "access_token": access_token}).json()
        if pub_reply_res.get("id"):
            print(f"🔥 成功自動在第一樓留言！Reply ID: {pub_reply_res.get('id')}")
        else:
            print("⚠️ 留言發布失敗:", pub_reply_res)
            
    return True

if __name__ == "__main__":
    print("🔮 [測試版本] 開始生成今日星座貼文與熱門留言...")
    content, reply_comment = generate_horoscope_content()
    print("📝 生成貼文預覽：\n" + "-"*30 + f"\n{content}\n" + "-"*30)
    print(f"💬 自回留言預覽：{reply_comment}")
    post_to_threads(content, reply_comment)
