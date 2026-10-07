import os
import time  
import requests
import random
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
        "請使用口語化、像朋友在群組抱怨或吐槽的語氣，夾雜 1-2 個網路流行短語。排版隨性一點，不要過於死板。",
        "請使用精簡強烈的短句風格，字數偏少（大約 200-250 字），標點符號可以簡化，營造冷冷淡淡但命中率極高的幽默感。",
        "請使用帶有一點溫暖陪伴、偶爾吐槽的社群貼文風格，段落之間用空白行隔開，讓手機閱讀時很有呼吸感。",
        "毒舌傲嬌系星座專家，講話一針見血但其實很準。",
        "瘋狂迷因連發的社群小編，喜歡用網路流行語對話。",
        "黑色幽默派的厭世導師，把運勢講得像人生災難現場但很好笑。",
        "高情商的溫暖心靈導師，喜歡用微酸帶甜的語氣虧人。"
    ]
    current_persona = random.choice(personas)

    # 主貼文 Prompt（100% 保留你原本的要求與格式，僅動態注入人設）
    prompt = f"""
你是一位講話精闢、語氣扎心又極具幽默感的 Threads 星座語錄專家。

風格要求：{current_persona}

請為 Threads 平台撰寫一則繁體中文「{today_str} 12 星座地雷與運勢地獄梗」。

目標：極大化「轉發率（Repost）」與「留言區戰翻率」，吸引更多星座迷追蹤。文風必須完全像真人朋友在 Threads 上發廢文/抱怨，絕對拒絕 AI 罐頭文。

排版與結構要求：
1.  開頭標題：格式必須為 "{today_str}今日十二星座運勢: "，後面接一句超吸睛的犀利金句。（例如：「今日最容易讓身邊人集體抓狂的星座出爐」）。
2. 【焦點警示】：挑出 1~2 個今日「最慘/最欠罵」的苦主星座做重點吐槽，並附上幸運色與數字。
3. 【12 星座精簡警示】：其餘星座以極度接地氣、毒舌且精闢的一句話列出（聚焦於「相處地雷」或「今日最爽/最慘時刻」）。
4. 【Threads 爆款互動結尾】：結尾不要任何溫馨提醒，改成一句能引發「強烈共鳴自首」或「Tag 朋友出來面對」的爭議性問句。
5. 【平台格式與字數限制】：
   - 全文（含標點、符號、空格）必須嚴格控制在 420 字以內，以確保不超過 Threads 平台限制，且必須保持文句完整，絕對不能切斷句子。
   - 適度使用換行與簡潔符號，打造適合手機快速滑過的排版。
"""

    # 隨機自回留言切入角度
    reply_prompts = [
        "請針對今天的星座運勢，寫一則短小精悍（50字以內）的自回留言。語氣要像個愛吐槽的網友，並強烈引導讀者留言。",
        "請寫一則 Threads 上的熱門第一樓留言（50字以內），吐槽今天某個運勢最慘的星座，並叫大家留言卡位。但留言要避免涉及人身攻擊、政治、宗教敏感話題。",
        "請寫一則幽默的自回互動留言（50字以內），問大家今天是不是也跟某個星座一樣心情很爛，引導洗版留言。但留言要避免涉及人身攻擊、政治、宗教敏感話題。",
        "請寫一則幽默共感：用輕鬆的比喻或小笑話，引起大家共鳴的自回互動留言（50字以內）。",
        "請寫一則拋出問題：提出簡單選擇題或開放式問題，讓大家忍不住回覆的自回互動留言（50字以內）。",
        "請寫一則讚美＋延伸：先肯定原貼文，再加一個延伸話題的自回互動留言（50字以內）。",
        "請寫一則生活連結：把貼文跟大家日常經驗連結，容易引起共鳴的自回互動留言（50字以內）。",
    ]
    reply_prompt = random.choice(reply_prompts)

    models_to_try = ["gemini-3.8-flash", "gemini-2.0-flash"]

    for attempt in range(8):
        for model_name in models_to_try:
            try:
                # 修正第一處：主貼文
                res_main = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )

                time.sleep(2)  # 緩衝間隔，降低伺服器瞬時壓力
                # 修正第二處：自回留言
                res_reply = client.models.generate_content(
                    model=model_name,
                    contents=reply_prompt
                )

                if not getattr(res_main, "text", None):
                    raise ValueError(f"Empty response from {model_name}")
                if not getattr(res_reply, "text", None):
                    raise ValueError(f"Empty reply response from {model_name}")

                main_text = res_main.text.replace('\n\n', '\n').strip()
                reply_text = res_reply.text.strip()
                return main_text, reply_text

            except Exception as e:
                print(f"⚠️ Model={model_name}, attempt={attempt + 1}, error={e}")
        
        backoff = min(300, (2 ** attempt) * 15)
        print(f"⏳ 等待 {backoff} 秒後重試...")
        time.sleep(backoff)

    raise RuntimeError("Gemini API remained unavailable after retries")

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
    
    reply_res = requests.post(create_url, data=reply_container_payload, timeout=15).json()
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
    # 隨機延遲 0 到 180 秒（0 到 3 分鐘），打破固定的秒數/整點觸發特徵   
    import random
    import time
    
    delay_seconds = random.randint(0, 180)
    print(f"⏳ [排程隱匿] 隨機延遲等待 {delay_seconds} 秒後開始執行...", flush=True)
    time.sleep(delay_seconds)
    
    print("🔮 [測試版本] 開始生成今日星座貼文與熱門留言...")
    content, reply_comment = generate_horoscope_content()
    print("📝 生成貼文預覽：\n" + "-"*30 + f"\n{content}\n" + "-"*30)
    print(f"💬 自回留言預覽：{reply_comment}")
    post_to_threads(content, reply_comment)
