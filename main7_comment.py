import os
import time  
import requests
from datetime import datetime, timezone, timedelta
from google import genai
import random
from google.genai import errors

# 獨立的 Gemini 安全呼叫函式 (含 Fallback 與 Exponential Backoff)
def safe_generate(client, prompt, system_instruction=None):
    # 定義嘗試的模型順序
    models_to_try = [
        "gemini-2.5-flash",  # 主要模型
        "gemini-3.8-flash"   # 備援模型
    ]
    
    last_error = None

    for model_name in models_to_try:
        print(f"🔄 嘗試使用模型生成: {model_name}...")
        
        # 每個模型給予 3 次重試機會 (Exponential Backoff: 2s, 4s, 8s)
        for attempt in range(3):
            try:
                kwargs = {"contents": prompt}
                if system_instruction:
                    kwargs["config"] = genai.types.GenerateContentConfig(
                        system_instruction=system_instruction
                    )
                    
                response = client.models.generate_content(
                    model=model_name,
                    **kwargs
                )
                print(f"✅ 使用 {model_name} 成功生成內容！")
                return response.text.strip()

            except errors.APIError as e:
                last_error = e
                wait_time = 2 ** (attempt + 1)  # 2秒, 4秒, 8秒
                print(f"⚠️ [{model_name}] 遇到 API 錯誤 (Code: {e.code})，{wait_time} 秒後重試 (第 {attempt + 1}/3 次)...")
                time.sleep(wait_time)
                
            except Exception as e:
                # 非 API 相關的致命程式碼錯誤，不浪費時間重試直接丟出
                print(f"❌ 發生非 API 錯誤: {e}")
                raise e

        print(f"🚨 模型 {model_name} 嘗試 3 次均失敗，準備切換至下一個備援模型...\n")

    # 若所有模型皆失敗，拋出最後錯誤
    raise RuntimeError(f"❌ 所有 Gemini 模型均呼叫失敗！最後錯誤: {last_error}")


# 1. 呼叫 Gemini AI 生成每日 12 星座配對運勢
def generate_horoscope_content():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("❌ 找不到 GEMINI_API_KEY 環境變數")

    client = genai.Client(api_key=api_key)

    tz_taiwan = timezone(timedelta(hours=8))
    today_str = datetime.now(tz_taiwan).strftime("%m/%d")

    current_product = {"name": "", "url": ""}

    prompt = f"""
你是一位講話精闢、帶有一點幽默感與犀利洞察力的 Threads 星座語錄大師。
請為 Threads 撰寫一則繁體中文「今日 12 星座最佳配對與火花解析」。

【貼文要求】
1. 開頭標題：格式必須為 "{today_str}今日十二星座最佳配對: "，後面接一句超吸睛的犀利金句。
2. 配對內容：精簡列出今日「愛情」、「友情」、「職場」的最佳配對組合，並附上各一組「互動火花/吐槽短評」。
3. 討喜排版：使用簡短文字與 Emoji，嚴禁密密麻麻的文字塊，適合手機快速瀏覽。
4. 結尾 Call to Action（三選一或綜合）：
   - 「標記你身邊那個 [特定星座]，告訴他今天對我好一點！」
   - 「底下留言你的星座，看看今天有沒有你的天命神隊友出沒👇」
5. 字數限制：全部字數（含標點符號、Emoji、特殊字元）必須嚴格控制在 420 字以內，留出閱讀呼吸感。
"""

    _style = random.choice([
        "【視角：職場慣老闆】冷血吐槽工作上的星座盲點，帶點諷刺幽默。",
        "【視角：戀愛腦翻車】犀利吐槽感情中盲目的星座，語氣像在吃瓜。",
        "【視角：迷信大師】一本正經地胡說八道，把運勢講得很玄但很好笑。",
        "【視角：衝浪幹話王】用最直白的一句話幹話，激起群憤或共鳴，但留言要避免涉及 人身攻擊、政治、宗教，專注在「共同經驗」或「輕鬆互動」。"
    ])

    reply_prompt = f"""
你是一位講話極度犀利、常在 Threads 抓馬區出沒的狠人網友。
請針對今天的星座運勢，寫一則短小精悍（50字以內）的自回留言。

【本篇限定風格】
{_style}

【絕對必填規則（缺一不可）】
1. 拒絕 AI 罐頭感：嚴禁使用「今天」、「各位」、「真的」、「笑死」等機器人開頭或贅字，要像真人打字一樣口語、隨性。
2. 毒舌吐槽：必須針對某個星座開砲、掀底牌或製造輕微的爭議與對立。
3. 強烈互動鉤子：結尾必須自然地引導讀者標記朋友或留言自首（例如：「@身邊那個死不認錯的雙子」或「留言區開放受害者報數👇」）。
"""

    # 主文與留言分開生成，互不干擾
    print("📝 開始生成主文...")
    raw_main = safe_generate(client, prompt)
    main_text = raw_main.replace('\n\n', '\n').strip()

    print("💬 開始生成第一樓留言...")
    reply_text = safe_generate(client, reply_prompt)

    return main_text, reply_text

# 2. 自動刷新 Threads Long-Lived Token
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
    
    res = requests.post(create_url, data=payload).json()
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
