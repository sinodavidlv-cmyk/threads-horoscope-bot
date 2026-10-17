import os
import re
import time
import requests
from google import genai
from google.genai import types
from datetime import datetime, timezone, timedelta

# 模型可用環境變數 GEMINI_MODEL 覆寫，不改程式碼就能換（預設沿用你原本的設定）
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
MAX_POST_CHARS = 400      # 你的 prompt 規定的上限
THREADS_LIMIT = 450       # Threads 單則文字硬上限


def _ask(client, prompt, use_search=False):
    """呼叫 Gemini。use_search=True 時啟用 Google 搜尋 grounding，回傳最終文字。"""
    config = None
    if use_search:
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
    res = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=config,
    )
    return (res.text or "").strip()


def _extract(tag, text):
    """從 <tag>...</tag> 取出內容；找不到就報錯，避免把搜尋過程的碎話發出去。"""
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.S)
    if not m:
        raise ValueError(f"模型輸出缺少 <{tag}> 標籤：{text[:100]}")
    return m.group(1).strip()


# 1. 呼叫 Gemini 生成每日新聞
def generate_news_content():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("❌ 找不到 GEMINI_API_KEY 環境變數")

    client = genai.Client(api_key=api_key)

    # 台灣時間 (UTC+8) 的今天日期（原本算了 today_str 但從沒放進 prompt）
    tz_taiwan = timezone(timedelta(hours=8))
    today_full = datetime.now(tz_taiwan).strftime("%Y年%m月%d日")

    prompt = f"""
今天是 {today_full}（台灣時間）。
你是一位非常懂 Threads 演算法與社群互動的編輯。
請先使用 Google 搜尋，查詢今天或最近 24 小時內的重要新聞，
再從搜尋結果中挑選「最容易引發一般人討論」的一則新聞。
貼文內容只能根據你實際搜尋到的內容撰寫，不得憑記憶或想像補充細節；
如果找不到能確認的事實，就換一則新聞。

【絕對禁忌：主題多樣化過濾機制】
1. 絕對禁止連續兩天挑選同性質的主題（例如：遠距辦公 WFH、房市買房、薪水通膨、AI 取代工作）。如果昨天的主題是職場工作模式，今天必須強制切換到「科技奇觀、生活冷知識、社會奇聞、國際趣聞、環保消費、娛樂文化」等完全不同的領域。
2. 拒絕老掉牙的萬年口水題。請挑選「讓人看了會想留言：『蛤？真的假的？』」的新聞。

【合規與內容安全防線（極重要，必須嚴格遵守）】
1. 客觀中立：絕不包含歧視（性別、種族、宗教、地域等）、仇恨言論、恐攻與暴力宣揚、無根據的污衊或個人攻擊。
2. 事實至上：僅引述具備時間、地點、人物、事件的主流權威媒體事實，嚴禁無中生有、捏造內容或轉述未經證實的謠言（內容不實）。
3. 政治與敏感議題去情緒化：涉及政治、國際衝突或社會事件時，僅客觀陳述「發生了什麼事」，不使用煽動性、極端或帶有強烈立場的用語。


不要寫新聞摘要。
不要用新聞主播口吻。
不要列點整理新聞。
請用 Threads 使用者的聊天語氣撰寫。
 
【輸出格式】
 
開頭：
用一句能引起好奇心或共鳴的話開場。
 
中段：
用100字內說明：
1. 發生什麼事
2. 為什麼重要
3. 對一般人有什麼影響
 
結尾：
提出一個容易讓人留言的問題。
 
【重要規則】
 
1. 總字數控制400字內
2. 使用自然口語
3. 不要說教
4. 不要寫「歡迎留言」
5. 不要寫「大家怎麼看」
6. 問題必須具體
7. 問題要有選擇困難或價值觀衝突
8. 可以適度使用 Emoji
9. 不要出現新聞網址
10. 不要出現新聞來源
 
【錯誤示範】
 
聯合國大會召開...
美股收盤...
今日重點如下...
 
【正確示範風格】
 
最近很多人喊買不起房，
但如果房價明天直接跌20%，
你真的會立刻買嗎？
 
美國Fed最新態度可能影響未來利率走向，
房貸族、投資人都在盯著看。
 
如果未來一年只能選一個：
A. 房價跌20%
B. 薪水漲20%
你選哪一個？

以上全部字數（含標點符號、Emoji、特殊字元）必須嚴格控制在 450 字以內。

【最終輸出方式】
搜尋與思考過程不要輸出。最後只輸出貼文本身，並用 <post> 與 </post> 標籤包住，標籤外不要有任何文字。
"""

    for attempt in range(3):
        try:
            raw_main = _ask(client, prompt, use_search=True)
            main_text = _extract("post", raw_main).replace("\n\n", "\n").strip()

            if len(main_text) > MAX_POST_CHARS:
                raise ValueError(f"主貼文過長：{len(main_text)} 字")

            # 自回留言：這次把主貼文內容一起給模型（原版沒給，留言與貼文無關）
            reply_prompt = f"""
你是一位擅長提高 Threads 留言互動率的社群小編。
 
以下是剛發出的主貼文：
-----
{main_text}
-----

請根據這則主貼文內容產生一則50字內的自留言。
 
規則：
 
1. 不要說認同+1
2. 不要求按讚
3. 不要求追蹤
4. 要延伸話題
5. 要讓讀者想回覆
6. 像朋友聊天
 
範例：
 
「最有趣的是，我發現身邊的人幾乎都選薪水漲，但真正存下來的其實不多😂」
 
或
 
「我原本也選A，但想想如果薪水漲20%好像更快樂？」
 
只輸出留言內容。
要求：
【合規與內容安全防線（極重要，必須嚴格遵守）】
1. 客觀中立：絕不包含歧視（性別、種族、宗教、地域等）、仇恨言論、恐攻與暴力宣揚、無根據的污衊或個人攻擊。
2. 事實至上：僅引述具備時間、地點、人物、事件的主流權威媒體事實，嚴禁無中生有、捏造內容或轉述未經證實的謠言（內容不實）。
3. 政治與敏感議題去情緒化：涉及政治、國際衝突或社會事件時，僅客觀陳述「發生了什麼事」，不使用煽動性、極端或帶有強烈立場的用語。
4. 語氣幽默、吐槽或帶有輕微爭議點（例如：吐槽新聞裡的荒謬現象）。
5. 強烈引導讀者 Tag 朋友或留言（例如：「@你覺得今天的新聞報導是真實且極具參考價值的朋友」、「覺得準的留言1」）。
6. 不要寫任何標題，直接輸出留言文字即可。
"""
            reply_text = _ask(client, reply_prompt)
            if not reply_text or len(reply_text) > THREADS_LIMIT:
                raise ValueError(f"留言長度異常：{len(reply_text)} 字")

            return main_text, reply_text
        except Exception as e:
            print(f"⚠️ 生成失敗（第 {attempt + 1} 次）：{e}")
            if attempt == 2:
                raise
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
        pub_reply_res = requests.post(
            publish_url,
            data={"creation_id": reply_creation_id, "access_token": access_token},
            timeout=30,
        ).json()
        if pub_reply_res.get("id"):
            print(f"🔥 成功自動在第一樓留言！Reply ID: {pub_reply_res.get('id')}")
        else:
            print("⚠️ 留言發布失敗:", pub_reply_res)
    else:
        print("⚠️ 留言容器建立失敗:", reply_res)

    return True


if __name__ == "__main__":
    print("🔮 [測試版本] 開始生成今日國際與台灣新聞貼文與熱門留言...")
    content, reply_comment = generate_news_content()
    print("📝 生成貼文預覽：\n" + "-" * 30 + f"\n{content}\n" + "-" * 30)
    print(f"💬 自回留言預覽：{reply_comment}")
    post_to_threads(content, reply_comment)
