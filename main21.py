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


if __name__ == "__main__":
    main()
