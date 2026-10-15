import os
import time  
import requests
from datetime import datetime, timezone, timedelta
from google import genai

# 1. 呼叫 Mistral AI 生成每日 12 生肖運勢（使用 REST API）
def generate_horoscope_content():
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("❌ 找不到 MISTRAL_API_KEY 環境變數")

    # 計算台灣時間 (UTC+8) 的當日日期
    tz_taiwan = timezone(timedelta(hours=8))
    today_str = datetime.now(tz_taiwan).strftime("%m/%d")

    prompt = f"""
{today_str}今日十二生肖運勢:
你是一位風格活潑、精通中西星象的語錄型專家。
請為 Threads 社群平台撰寫一則繁體中文「今日 12 生肖運勢短評總整理」。

要求：
1. 今日十二生肖運勢與今日建議。
2. 簡短100個字元以內相關的今日生肖心理測試, 心理測試要有問有答且有趣, 每一次的測試內容要有變化。
3. 開頭要有一句超吸睛的標題。
4. 使用簡短的文字與討喜的 Emoji 排版。
5. 結尾適合當日運勢的一句話溫馨提醒。
6. 全部字數，包括符號、特殊字元都必須嚴格控制在 450 字內，排版適合手機閱讀。
"""

    reply_prompt = f"""
你是一位講話犀利、喜歡吐槽的 Threads 網友。
請針對今天的生肖運勢，寫一則短小精悍（50字以內）的自回留言，用來吸引讀者留言互動。
要求：
1. 語氣幽默、吐槽或帶有輕微爭議點（例如：吐槽某個生肖今天的運勢或建議）。
2. 強烈引導讀者 Tag 朋友或留言（例如：「@你身邊生肖是羊的朋友」、「覺得準的留言1」）。
3. 不要寫任何標題，直接輸出留言文字即可。
"""

    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    # model 可依你的帳號權限與需求調整
    model = "mistral-medium-latest"

    for attempt in range(3):
        try:
            # 主文
            payload_main = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                # 可視需要設定 max_tokens, temperature 等
                "temperature": 0.8,
                "max_tokens": 800
            }
            r_main = requests.post(url, json=payload_main, headers=headers, timeout=30)
            r_main.raise_for_status()
            data_main = r_main.json()

            # 回文
            payload_reply = {
                "model": model,
                "messages": [
                    {"role": "user", "content": reply_prompt}
                ],
                "temperature": 0.9,
                "max_tokens": 200
            }
            r_reply = requests.post(url, json=payload_reply, headers=headers, timeout=30)
            r_reply.raise_for_status()
            data_reply = r_reply.json()

            # 解析回傳（兼容常見 response schema）
            def extract_text(resp_json):
                # 常見：choices[0].message.content
                try:
                    return resp_json["choices"][0]["message"]["content"].strip()
                except Exception:
                    # 若不同結構，嘗試更多字段
                    try:
                        return resp_json["choices"][0]["text"].strip()
                    except Exception:
                        return ""

            main_text = extract_text(data_main).replace('\n\n', '\n').strip()
            reply_text = extract_text(data_reply).strip()

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
