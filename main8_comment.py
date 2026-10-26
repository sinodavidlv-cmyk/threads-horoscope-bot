import os
import time  
import requests
from datetime import datetime, timezone, timedelta
from google import genai
import re

MAX_LEN = 500
RETRY_CODES = {429, 500, 502, 503, 504}
# 模型清單,逗號分隔;沒設環境變數就用你目前正在用的兩個
MODELS = [m.strip() for m in (os.environ.get("GEMINI_MODELS") or
          "gemini-3.8-flash,gemini-3.6-flash").split(",") if m.strip()]


def gen_text(client, prompt, models, tries=3):
    errs = []
    for model in models:
        for attempt in range(tries):
            try:
                res = client.models.generate_content(model=model, contents=prompt)
                text = (res.text or "").strip()
                if text:
                    print(f"✅ 使用模型 {model}")
                    return text
                errs.append(f"{model}:空回應")
                break                                   # 空回應就換下一個模型
            except Exception as e:
                m = re.match(r"\s*(\d{3})", str(e))     # 錯誤訊息開頭是狀態碼,如「503 UNAVAILABLE」
                code = getattr(e, "code", None) or (int(m.group(1)) if m else None)
                print(f"⚠️ {model} 第 {attempt+1}/{tries} 次失敗:{str(e)[:150]}")
                errs.append(f"{model}:{code}")
                if code is not None and code not in RETRY_CODES:
                    break                               # 401/403/404 重試沒用,直接換模型
                if attempt < tries - 1:
                    time.sleep(30 * (attempt + 1))      # 30 秒、60 秒
    raise RuntimeError(f"所有模型都失敗:{errs}")


# 1. 呼叫 Gemini AI 生成每日 12 生肖運勢_
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
{today_str}今日十二生肖運勢:
你是一位風格活潑、精通中西星象的語錄型專家。
請為 Threads 社群平台撰寫一則繁體中文「今日 12 生肖運勢短評總整理」。

要求：
1. 今日十二生肖運勢與今日建議。
2. 簡短100個字元以內相關的今日生肖心理測試, 心理測試要有問有答且有趣, 每一次的測試內容要有變化。
3. 開頭要有一句超吸睛的標題並且要有生肖兩字在裡面。
4. 使用簡短的文字與討喜的 Emoji 排版。
5. 結尾適合當日運勢的一句話溫馨提醒。
6. 全部字數，包括符號、特殊字元都必須嚴格控制在 450 字內，排版適合手機閱讀。
"""

    # 自回留言 Prompt
    reply_prompt = f"""
你是一位講話犀利、喜歡吐槽的 Threads 網友。
請針對今天的生肖運勢，寫一則短小精悍（50字以內）的自回留言，用來吸引讀者留言互動。
要求：
1. 語氣幽默、吐槽或帶有輕微爭議點（例如：吐槽某個生肖今天的運勢或建議）。
2. 強烈引導讀者 Tag 朋友或留言（例如：「@你身邊生肖是羊的朋友」、「覺得準的留言1」）。
3. 不要寫任何標題，直接輸出留言文字即可。
"""
    main_text = None
    for attempt in range(1, 4):
        text = gen_text(client, prompt, MODELS).replace('\n\n', '\n').strip()
        if len(text) <= MAX_LEN:
            main_text = text
            break
        print(f"⚠️ 第 {attempt} 次主文 {len(text)} 字,超過 {MAX_LEN},重新生成")
        time.sleep(15)
    if main_text is None:
        raise RuntimeError(f"主文連續超過 {MAX_LEN} 字")

    time.sleep(10)   # 兩次呼叫之間留間隔
    reply_text = gen_text(client, reply_prompt, MODELS[::-1]).strip()
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
        res = requests.get(url, params=params, timeout=30).json()
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
    
    res = requests.post(create_url, data=payload, timeout=30).json()
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
    
    reply_res = requests.post(create_url, data=reply_container_payload, timeout=30).json()    
    reply_creation_id = reply_res.get("id")
    if reply_creation_id:
        time.sleep(5)
        pub_reply_res = requests.post(publish_url, data={"creation_id": reply_creation_id, "access_token": access_token}, timeout=30).json()
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
    if os.environ.get("DRY_RUN") == "1":
        print("DRY_RUN=1,不發送")
        raise SystemExit(0)
    if not post_to_threads(content, reply_comment):
        raise SystemExit(1)
