"""用法:
  python feedback/collect_insights.py backfill   # 一次性:把過去貼文補進 data/posts(系列由標題判斷)
  python feedback/collect_insights.py reclassify # 不連網:用最新規則重新歸類歷史貼文
  python feedback/collect_insights.py snapshot   # 每天跑:替到期的貼文抓 24h/72h/168h 成效快照

需要的 token 權限:threads_basic + threads_manage_insights(讀文章清單與成效)。
"""
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.dirname(__file__))
from store import (DATA, POSTS_DIR, _write_json, parse_ts, read_insights,  # noqa: E402
                   read_posts, threads_len, utcnow_iso, write_insight)

API = "https://graph.threads.net/v1.0"
METRICS_FULL = "views,likes,replies,reposts,quotes,shares"
METRICS_SAFE = "views,likes,replies,reposts,quotes"   # shares 文件標示為開發中,失敗就退回
BUCKETS = (168, 72, 24)                                # 小時,由大到小
MAX_AGE_DAYS = 21                                      # 超過就不再抓
ACCOUNT_DIR = DATA / "account"                         # 每天一個檔:追蹤人數與連結點擊


def classify(text):
    """從標題把歷史貼文歸到系列。規則依你實際貼文的標題格式(含舊版格式)。"""
    t = (text or "")[:60]
    if "英文佳句" in t:
        return "english"
    if "新聞" in t:
        return "news"
    if "配對" in t:
        if "生肖" in t:
            return "main9"
        if "星座" in t:
            return "main7"
    if "12星座運勢" in t:          # 舊版 Main6 標題(阿拉伯數字 12)
        return "main6_old"
    if "運勢" in t:
        if "生肖" in t:
            return "main8"
        if "星座" in t:
            return "main6"
    return "other"


def reclassify():
    """不呼叫 API:用目前的 classify 規則,重新替歷史貼文歸類。"""
    n = 0
    for p in read_posts():
        if p.get("backfilled"):
            new = classify(p.get("text"))
            if new != p["series"]:
                p["series"] = new
                _write_json(POSTS_DIR / f"{p['post_id']}.json", p)
                n += 1
    print(f"✅ 重新歸類 {n} 篇")


def fetch_insights(post_id, token):
    for metrics in (METRICS_FULL, METRICS_SAFE):
        r = requests.get(f"{API}/{post_id}/insights",
                         params={"metric": metrics, "access_token": token}, timeout=30)
        if r.status_code == 200:
            out = {}
            for m in r.json().get("data", []):
                vals = m.get("values") or []
                if vals:
                    out[m["name"]] = vals[0].get("value", 0)
                elif "total_value" in m:
                    out[m["name"]] = m["total_value"].get("value", 0)
            return out
        print(f"⚠️ insights {post_id} ({metrics}) → {r.status_code} {r.text[:200]}")
    return None


def backfill(token, user_id, days=100):
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    known = {p["post_id"] for p in read_posts()}
    url = f"{API}/{user_id}/threads"
    params = {"fields": "id,text,timestamp,permalink,is_reply", "limit": 50,
              "since": since, "access_token": token}
    added = 0
    while url:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 400 and params and "is_reply" in params["fields"]:
            params["fields"] = "id,text,timestamp,permalink"   # is_reply 欄位不被接受時退回
            continue
        r.raise_for_status()
        j = r.json()
        for it in j.get("data", []):
            if it.get("is_reply") or it["id"] in known:
                continue
            text = it.get("text") or ""
            _write_json(POSTS_DIR / f"{it['id']}.json", {
                "post_id": it["id"], "series": classify(text),
                "ts": parse_ts(it["timestamp"]).astimezone(timezone.utc).isoformat(timespec="seconds"),
                "text": text, "reply_id": None, "reply_text": None,
                "self_reply": None,          # 歷史貼文不知道自回有沒有成功
                "arm": {}, "model": None, "chars": threads_len(text),
                "backfilled": True,
            })
            added += 1
        url, params = j.get("paging", {}).get("next"), None   # next 網址已含所有參數
    print(f"✅ backfill 新增 {added} 篇")


def snapshot_account(token, user_id):
    """每天記一次帳號層級數字。followers_count 官方沒有歷史查詢,只能自己每天存一筆。
    clicks(連結點擊,依網址分列)存「昨天(台灣時間)」整天,各天互不重疊,可直接相加。"""
    tz8 = timezone(timedelta(hours=8))
    today = datetime.now(tz8).replace(hour=0, minute=0, second=0, microsecond=0)
    yday = today - timedelta(days=1)
    row = {"date": today.date().isoformat(), "ts": utcnow_iso(),
           "clicks_for_date": yday.date().isoformat()}
    url = f"{API}/{user_id}/threads_insights"
    r = requests.get(url, params={"metric": "followers_count", "access_token": token}, timeout=30)
    if r.status_code == 200:
        for m in r.json().get("data", []):
            if m.get("name") == "followers_count":
                row["followers_count"] = (m.get("total_value") or {}).get("value")
    else:
        print(f"⚠️ followers_count → {r.status_code} {r.text[:200]}")
    r = requests.get(url, params={"metric": "clicks", "since": int(yday.timestamp()),
                                  "until": int(today.timestamp()), "access_token": token}, timeout=30)
    if r.status_code == 200:
        row["clicks_raw"] = r.json().get("data", [])
    else:
        print(f"⚠️ clicks → {r.status_code} {r.text[:200]}")
    _write_json(ACCOUNT_DIR / f"{row['date']}.json", row)
    print(f"✅ 帳號快照 {row['date']}: followers_count={row.get('followers_count')}")


def snapshot(token, max_age_days=MAX_AGE_DAYS):
    done = {(i["post_id"], i["bucket"]) for i in read_insights()}
    now = datetime.now(timezone.utc)
    n = 0
    for p in read_posts():
        age_h = (now - parse_ts(p["ts"])).total_seconds() / 3600
        if max_age_days and age_h > max_age_days * 24:
            continue
        bucket = next((b for b in BUCKETS if age_h >= b and (p["post_id"], b) not in done), None)
        if bucket is None:
            continue
        m = fetch_insights(p["post_id"], token)
        time.sleep(1)
        if m is None:
            continue
        write_insight({"post_id": p["post_id"], "bucket": bucket,
                       "age_h": round(age_h, 1), "ts": utcnow_iso(), **m})
        n += 1
    print(f"✅ 寫入 {n} 筆快照")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    if mode == "reclassify":
        reclassify()
        sys.exit(0)
    token = os.environ["THREADS_ACCESS_TOKEN"]
    if mode == "backfill":
        backfill(token, os.environ["THREADS_USER_ID"])
        snapshot(token, max_age_days=None)   # 歷史貼文不限天數,一律補抓
    else:
        snapshot(token)
    try:
        snapshot_account(token, os.environ["THREADS_USER_ID"])
    except Exception as e:   # 帳號快照失敗不該讓整個流程失敗
        print(f"⚠️ 帳號快照失敗: {e}")
