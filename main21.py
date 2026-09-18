import os
from datetime import datetime, timezone, timedelta

from google import genai
from products import products

def load_history():

    try:
        with open(
            "data/history.txt",
            "r",
            encoding="utf-8"
        ) as f:
            return f.read()

    except:
        return ""


def save_history(content):

    with open(
        "data/history.txt",
        "a",
        encoding="utf-8"
    ) as f:

        f.write(content)
        f.write("\n\n")


def get_today():

    tz_taiwan = timezone(
        timedelta(hours=8)
    )

    return datetime.now(
        tz_taiwan
    ).strftime("%m/%d")


def select_product():

    tz_taiwan = timezone(
        timedelta(hours=8)
    )

    day_index = (
        datetime.now(tz_taiwan).weekday()
        % len(products)
    )

    return products[day_index]


def generate_horoscope_content():

    api_key = os.getenv(
    "GEMINI_API_KEY"
    )

    if not api_key:
    raise ValueError(
        "找不到 GEMINI_API_KEY"
    )

    client = genai.Client(
        api_key=api_key
    )

    today = get_today()

    history = load_history()

    prompt = f"""
你是一位Threads星座爆文創作者。

今天日期：

{today}

以下是歷史內容：

{history}

規則：

1. 禁止重複歷史內容
2. 使用繁體中文
3. 適合Threads
4. 有互動感
5. 字數420字內

請產生：

標題
愛情配對
友情配對
職場配對

最後加入留言引導。
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text


def main():

    print("================================")
    print("Threads Horoscope Bot V2")
    print("================================")

    today = get_today()

    product = select_product()

    history = load_history()

    print("日期:", today)
    print("商品:", product["name"])
    print("歷史內容長度:", len(history))

    print("系統初始化完成")
    print("Gemini功能已載入")


if __name__ == "__main__":
    main()
