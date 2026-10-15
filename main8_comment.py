import os
import re
import sys
import time
import random
import requests
from datetime import datetime, timezone, timedelta

MAX_LEN = 500
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL = os.environ.get("MISTRAL_MODEL", "mistral-medium-latest")
THREADS_BASE = "https://graph.threads.net/v1.0"
DRY_RUN = os.environ.get("DRY_RUN") == "1"

# 每天抽一個主題,讓心理測試有變化(自己擴充)
THEMES = [
    "選擇題:雨天的反應", "二選一:早餐偏好", "情境題:突然多出一天假",
    "顏色聯想", "數字直覺", "動物聯想", "週末安排", "收到訊息的反應",
    "迷路時的第一反應", "手機電量剩10%時的選擇",
]


def mistral(prompt, temperature, max_tokens):
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("❌ 找不到 MISTRAL_API_KEY 環境變數")
    r = requests.post(
        MISTRAL_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": MODEL, "messages": [{"role": "user", "content": prompt}],
              "temperature": temperature, "max_tokens": max_tokens},
        timeout=60,
    )
    r.raise_for_status()
    choice = r.json()["choices"][0]
    if choice.get("finish_reason") == "length":
        raise RuntimeError("輸出被 max_tokens 截斷")
    return choice["message"]["content"].strip()


def clean(text):
    text = re.sub(r"\*\*|__|`", "", text)             # 去掉 Markdown 粗體/程式碼符號
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)  # 去掉標題井號
    return text.replace("\n\n", "\n").strip()


def generate_horoscope_content():
    tz_taiwan = timezone(timedelta(hours=8))
    today_str = datetime.now(tz_taiwan).strftime("%m/%d")
    theme = random.choice(THEMES)

    prompt = f"""
{today_str}今日十二生肖運勢:
你是一位風格活潑、精通中西星象的語錄型專家。
請為 Threads 社群平台撰寫一則繁體中文「今日 12 生肖運勢短評總整理」。

要求：
1. 今日十二生肖運勢與今日建議。
2. 簡短100個字元以內相關的今日生肖心理測試, 心理測試要有問有答且有趣。今天的測試主題:{theme}。
3. 開頭要有一句超吸睛的標題。
4. 使用簡短的文字與討喜的 Emoji 排版。
5. 結尾適合當日運勢的一句話溫馨提醒。
6. 全部字數，包括符號、特殊字元都必須嚴格控制在 450 字內，排版適合手機閱讀。
7. 只輸出純文字，不要使用 Markdown(不要 ** 或 # 符號)。
"""

    reply_prompt = """
你是一位講話犀利、喜歡吐槽的 Threads 網友。
請針對今天的生肖運勢，寫一則短小精悍（50字以內）的自回留言，用來吸引讀者留言互動。
要求：
1. 語氣幽默、吐槽或帶有輕微爭議點（例如：吐槽某個生肖今天的運勢或建議）。
2. 強烈引導讀者 Tag 朋友或留言（例如：「@你身邊生肖是羊的朋友」、「覺得準的留言1」）。
3. 不要寫任何標題，直接輸出留言文字即可。
4. 只輸出純文字，不要使用 Markdown。
"""

    last_err = None
    for attempt in range(1, 4):
        try:
            main_text = clean(mistral(prompt, 0.8, 1500))
            if len(main_text) > MAX_LEN:
                last_err = f"主文 {len(main_text)} 字,超過 {MAX_LEN}"
                print(f"⚠️ 第 {attempt} 次:{last_err},重新生成")
                continue
            reply_text = clean(mistral(reply_prompt, 0.9, 300))
            return main_text, reply_text
        except Exception as e:
            last_err = e
            print(f"⚠️ 第 {attempt} 次生成失敗:{e}")
            time.sleep(10)
    raise RuntimeError(f"生成失敗:{last_err}")


def refresh_threads_token():
    token = os.environ["THREADS_ACCESS_TOKEN"]
    try:
        res = requests.get(
            "https://graph.threads.net/refresh_access_token",
            params={"grant_type": "th_refresh_token", "access_token": token},
            timeout=30,
        ).json()
    except Exception as e:
        print("⚠️ Token 刷新請求失敗:", type(e).__name__)   # 不印 e,避免帶出含 token 的 URL
        return token
    if "access_token" in res:
        same = res["access_token"] == token
        print(f"🔄 Token 刷新成功|新舊 token 相同:{same}|expires_in={res.get('expires_in')}")
        return res["access_token"]
    print("⚠️ Token 刷新失敗:", res)
    return token


def wait_ready(container_id, headers, tries=12, delay=5):
    for _ in range(tries):
        r = requests.get(f"{THREADS_BASE}/{container_id}",
                         params={"fields": "status,error_message"},
                         headers=headers, timeout=30).json()
        status = r.get("status")
        if status == "FINISHED":
            return True
        if status in ("ERROR", "EXPIRED"):
            print("❌ container 狀態異常:", r)
            return False
        if status is None:            # 查不到狀態欄位,退回保守等待
            time.sleep(30)
            return True
        time.sleep(delay)
    return False


def create_and_publish(user_id, headers, text, reply_to_id=None):
    data = {"media_type": "TEXT", "text": text}
    if reply_to_id:
        data["reply_to_id"] = reply_to_id
    res = requests.post(f"{THREADS_BASE}/{user_id}/threads",
                        headers=headers, data=data, timeout=30).json()
    cid = res.get("id")
    if not cid:
        print("❌ 建立 container 失敗:", res)
        return None
    if not wait_ready(cid, headers):
        return None
    # 注意:publish 失敗不要自動重試,避免重複發文
    pub = requests.post(f"{THREADS_BASE}/{user_id}/threads_publish",
                        headers=headers, data={"creation_id": cid}, timeout=30).json()
    pid = pub.get("id")
    if not pid:
        print("❌ 發布失敗:", pub)
    return pid


def post_to_threads(text_content, reply_content):
    user_id = os.environ["THREADS_USER_ID"]
    token = refresh_threads_token()
    headers = {"Authorization": f"Bearer {token}"}

    post_id = create_and_publish(user_id, headers, text_content)
    if not post_id:
        return False
    print(f"🎉 主貼文已發布:{post_id}")

    time.sleep(5)
    reply_id = create_and_publish(user_id, headers, reply_content, reply_to_id=post_id)
    if reply_id:
        print(f"🔥 自回留言已發布:{reply_id}")
    else:
        print("⚠️ 自回留言失敗(主貼文已成功,不視為整體失敗)")
    return True


if __name__ == "__main__":
    print("🔮 開始生成今日生肖貼文與自回留言...")
    content, reply_comment = generate_horoscope_content()
    print("📝 貼文預覽(%d 字):\n%s\n%s\n%s" % (len(content), "-" * 30, content, "-" * 30))
    print(f"💬 自回留言預覽:{reply_comment}")
    if DRY_RUN:
        print("DRY_RUN=1,不發送")
        sys.exit(0)
    if not post_to_threads(content, reply_comment):
        sys.exit(1)      # 讓 GitHub Actions 顯示紅燈並寄通知
