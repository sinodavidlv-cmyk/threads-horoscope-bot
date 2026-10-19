"""資料層:貼文紀錄、臂(arm)選擇、發文閘門。只用標準函式庫。

資料檔一律「一貼文一檔」,避免多支 workflow 同時 push 時發生合併衝突。
  data/posts/<post_id>.json            發文當下寫入
  data/insights/<post_id>__<bucket>.json   成效快照(bucket = 24 / 72 / 168 小時)
  data/arms.json                        每週由 update_arms.py 重算,發文腳本只讀不寫
"""
import hashlib
import json
import os
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(os.environ.get("FEEDBACK_DATA_DIR", "data"))
POSTS_DIR = DATA / "posts"
INSIGHTS_DIR = DATA / "insights"
ARMS_FILE = DATA / "arms.json"


def utcnow_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_ts(s):
    """吃 Threads 的 2026-10-06T13:21:56+0000,也吃 isoformat 的 +00:00。"""
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return datetime.fromisoformat(s)


def _write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def _read_dir(d):
    out = []
    if d.exists():
        for p in sorted(d.glob("*.json")):
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                print(f"⚠️ 壞檔略過: {p}")
    return out


def read_posts():
    return _read_dir(POSTS_DIR)


def read_insights():
    return _read_dir(INSIGHTS_DIR)


def write_insight(row):
    _write_json(INSIGHTS_DIR / f"{row['post_id']}__{row['bucket']}.json", row)


# ---- Threads 字數:500 上限,emoji 以 UTF-8 位元組計(官方文件)。
# 這裡逐碼點把 emoji 區段算成位元組數,ZWJ 組合 emoji 的總位元組與官方算法相同,
# 箭頭等少數符號會略多算,偏保守,不會超限。
_EMOJI = re.compile(
    "[\U0001F000-\U0001FFFF\u2600-\u27BF\u2B00-\u2BFF\u2190-\u21FF"
    "\u2300-\u23FF\u203C\u2049\u2122\u2139\uFE0F\u200D]"
)


def threads_len(text):
    return sum(len(c.encode("utf-8")) if _EMOJI.match(c) else 1 for c in text)


def record_post(series, main_id, text, reply_id=None, reply_text=None,
                arm=None, model=None):
    """發文成功後立刻呼叫。arm 例:{"persona": "a1b2c3d4"}"""
    _write_json(POSTS_DIR / f"{main_id}.json", {
        "post_id": main_id,
        "series": series,
        "ts": utcnow_iso(),
        "text": text,
        "reply_id": reply_id,
        "reply_text": reply_text,
        "self_reply": bool(reply_id),
        "arm": arm or {},
        "model": model,
        "chars": threads_len(text),
        "backfilled": False,
    })


# ---- 臂的選擇 ----
def arm_key(option):
    return hashlib.sha1(option.encode("utf-8")).hexdigest()[:8]


def _arms():
    try:
        return json.loads(ARMS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def choose(dim, options):
    """依 arms.json 的權重抽一個選項,回傳 (選項, arm_key)。
    沒有權重資料的選項(含新加的)權重 = 1.0(中性),所以新選項一定會被試到。
    權重已正規化成平均 1。"""
    keys = [arm_key(o) for o in options]
    w = _arms().get("dims", {}).get(dim, {})
    weights = [max(float(w.get(k, 1.0)), 0.01) for k in keys]
    i = random.choices(range(len(options)), weights=weights)[0]
    return options[i], keys[i]


def gate(series, default=1.0):
    """放在腳本最前面。依本週配額機率決定今天這個系列發不發;不發就乾淨退出(exit 0)。"""
    p = float(_arms().get("series_prob", {}).get(series, default))
    r = random.random()
    if r > p:
        print(f"🚦 gate: {series} p={p:.2f} r={r:.2f} → 今天略過")
        sys.exit(0)
    print(f"🚦 gate: {series} p={p:.2f} r={r:.2f} → 發文")
