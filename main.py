import os
import requests
from datetime import datetime, timezone, timedelta  # 1. 引入時間套件
from google import genai

# 1. 呼叫 Gemini AI 生成每日 12 星座運勢
def generate_horoscope_content():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("❌ 找不到 GEMINI_API_KEY 環境變數")
        
    client = genai.Client(api_key=api_key)
    
    # 2. 取得台灣目前日期 (UTC+8)
    tw_time = datetime.now(timezone.utc) + timedelta(hours=8)
    today_str = tw_time.strftime("%m/%d")  # 格式如：08/20
    
    # 3. 使用 f-string 動態插入日期，並要求增加字數與細節
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
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",  # 建議使用穩定版本模型名稱
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
