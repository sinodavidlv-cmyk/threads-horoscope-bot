import os
import requests
from datetime import datetime, timezone, timedelta  # 1. 引入時間套件
from google import genai

# 1. 通用 AI 生成函式（新增此函式來處理所有不同主題）
def generate_ai_content(prompt):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("❌ 找不到 GEMINI_API_KEY 環境變數")
        
    client = genai.Client(api_key=api_key)
    
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )
    return response.text

# 原本的第 1 篇生成函式（可保留）
def generate_horoscope_content():
    tw_time = datetime.now(timezone.utc) + timedelta(hours=8)
    today_str = tw_time.strftime("%m/%d")
    
    prompt = f"""
    你是一位風格活潑、精通星象的語錄型專家。
    請為 Threads 社群平台撰寫一則繁體中文「今日 12 星座運勢短評與幸運指南」。

    要求：
    1. 全文開頭請精確使用格式：✨【{today_str} 今日十二星座運勢幸運色與數字】✨
    2. 使用討喜的 Emoji 與適合手機閱讀的排版。
    3. 內容包含：
       - 當日幸運星 Top 3（含理由）。
       - 12 星座簡短點評（含運勢焦點、幸運色與幸運數字）。
       - 一句話溫馨提醒與給予滿滿能量的結尾。
    4. 【字數重點】：請將總字數充實控制在「420 字至 480 字之間」（切勿超過 Threads 500 字限制，但也避免內容過短）。
    """
    return generate_ai_content(prompt)

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
    import time

    # 取得台灣目前日期 (UTC+8)
    tw_time = datetime.now(timezone.utc) + timedelta(hours=8)
    today_str = tw_time.strftime("%m/%d")

    # 1. 將 4 篇提示詞全部透過 generate_ai_content() 丟給 AI 生成
    posts = [
        generate_horoscope_content(),  # 第 1 篇：AI 星座運勢
        
        # 第 2 篇：最佳配對
        generate_ai_content(f"""根據今日的星座運勢去搭配出今日最佳的配對運勢: 與其他星座的配對情況，請分成在愛情、友情和職場關係方面這三大類.最後結尾加一句根據今日運勢專屬的祝福語. 全文嚴格限制在450字以內.開頭請用"{today_str} 今日十二星座最佳配對:" """),
        
        # 第 3 篇：生肖運勢與心理測試
        generate_ai_content(f"""今日十二生肖運勢與建議. 然後加一個今日十二生肖運勢的簡短100個字元相關的生肖心理測試, 心理測試要有問有答且有趣,最後結尾加一句根據今日運勢專屬的祝福語. 上述請依序排列並將全文嚴格限制在450字以內.開頭請用"{today_str} 今日十二生肖運勢:" """),
        
        # 第 4 篇：生肖三合六合
        generate_ai_content(f"""給我今日十二生肖三合與六合的關係，請分為人際互動,婚姻匹配與事業這三大類.最後結尾加一句根據今日運勢專屬的祝福語.上述請依序排列並將全文嚴格限制在450字以內.並將最終的答案融入以下元素: 1. 善用 Emoji 標籤與換行，拒絕長篇大論；首圖(Emoji)要做得美觀且資訊清楚。 2.場景敘事：用最近時事的具體生活情境來描述。 3.創造互動： 在文末點名（例：@身邊最衰的朋友）或使用投票功能，誘發留言與轉發。 4.情緒共鳴： 加入幽默或吃瓜的個人風格. 5. 開頭請用"{today_str} 今日十二生肖最佳配對:" """)
    ]

    total_posts = len(posts)

    # 2. 使用迴圈依序發布
    for index, content in enumerate(posts, start=1):
        print(f"\n🔮 [{index}/{total_posts}] 開始處理第 {index} 篇貼文...")
        print("📝 貼文預覽：\n" + "-"*30 + f"\n{content}\n" + "-"*30)
        
        # 呼叫發文函式
        post_to_threads(content)
        
        # 3. 冷卻機制：若不是最後一篇，等待 5 秒避免觸發 API 頻率限制
        if index < total_posts:
            print("⏳ 等待 5 秒後準備發送下一篇...")
            time.sleep(20)

    print("\n🎉 所有 4 篇貼文已全部發布完成！")
