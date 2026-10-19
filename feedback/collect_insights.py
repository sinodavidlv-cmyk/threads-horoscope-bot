"""用法:
  python feedback/collect_insights.py backfill   # 一次性:把過去貼文補進 data/posts(系列由標題判斷)
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
from store import (POSTS_DIR, _write_json, parse_ts, read_insights,  # noqa: E402
                   read_posts, threads_len, utcnow_iso, write_insight)

API = "https://graph.threads.net/v1.0"
METRICS_FULL = "views,likes,replies,reposts,quotes,shares"
METRICS_SAFE = "views,likes,replies,reposts,quotes"   # shares 文件標示為開發中,失敗就退回
BUCKETS = (168, 72, 24)                                # 小時,由大到小
MAX_AGE_DAYS = 21                                      # 超過就不再抓


def classify(text):
    """從標題把歷史貼文歸到系列。規則依你五支腳本的標題格式。"""
    t = (text or "")[:60]
    if "十二星座最佳配對" in t:
        return "main7"
    if "十二星座運勢" in t:
        return "main6"
    if "十二生肖最佳配對" in t:
        return "main9"
    if "十二生肖運勢" in t:
        return "main8"
    return "other"   # 新聞貼文沒有固定標題,先歸 other;之後可在 main10 加固定前綴再改規則


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
    token = os.environ["THREADS_ACCESS_TOKEN"]
    mode = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    if mode == "backfill":
        backfill(token, os.environ["THREADS_USER_ID"])
        snapshot(token, max_age_days=None)   # 歷史貼文不限天數,一律補抓
    else:
        snapshot(token)
