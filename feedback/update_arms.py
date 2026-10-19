"""每週跑一次:讀成效 → 出報告 → 重算 data/arms.json。純 Python,零 LLM 成本。

做三件事:
1. reports/latest.md:各系列/各選項的成效、信賴區間、目前雜訊有多大、要多少篇才分得出 30% 差距。
2. series_prob:各系列「今天要不要發」的機率(Thompson sampling + 探索底線)。
3. dims:各系列內部選項(如 persona)的抽選權重。
獎勵 = log(1 + 72h 瀏覽數)。用 log 是因為瀏覽分布極端右偏,一篇爆文會綁架平均。
"""
import json
import math
import os
import random
import re
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from store import ARMS_FILE, DATA, parse_ts, read_insights, read_posts, utcnow_iso  # noqa: E402

WINDOW_DAYS = int(os.environ.get("WINDOW_DAYS", 75))       # 只看近 N 天,演算法與受眾會漂移
MIN_TOTAL = int(os.environ.get("MIN_TOTAL", 20))           # 成熟貼文少於此數,一律中性不調整
EPSILON = float(os.environ.get("EPSILON", 0.4))            # 探索比例。雜訊大,刻意設高
DAILY_BUDGET = float(os.environ.get("DAILY_BUDGET", 3))    # 全部系列合計「平均每天發幾篇」
MIN_P = float(os.environ.get("MIN_P", 0.15))               # 任何系列的發文機率下限
PRIOR_K = 3.0                                              # 先驗等效樣本數(往全體平均收縮)
MC = 4000
REPORT = Path(os.environ.get("REPORT_FILE", "reports/latest.md"))


def matured_rows():
    """每篇貼文取 72h(沒有就 168h)快照。24h 的不算,還沒穩定。"""
    ins = {}
    for i in read_insights():
        if i["bucket"] in (72, 168):
            key = i["post_id"]
            if key not in ins or i["bucket"] == 72:
                ins[key] = i
    cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    rows = []
    for p in read_posts():
        i = ins.get(p["post_id"])
        if not i or parse_ts(p["ts"]) < cutoff:
            continue
        views = i.get("views", 0)
        replies = i.get("replies", 0)
        # 根貼文的 replies 含你自己的自回:自回成功或不確定(歷史貼文)就扣 1
        ext = max(0, replies - (1 if p.get("self_reply") in (True, None) else 0))
        rows.append({
            "series": p["series"], "arm": p.get("arm") or {}, "views": views,
            "ts": p["ts"], "text": p.get("text") or "",
            "likes": i.get("likes", 0), "ext_replies": ext,
            "shares": i.get("reposts", 0) + i.get("quotes", 0),
            "x": math.log1p(views),
        })
    return rows


def boot_ci_median(xs, n=2000, seed=1):
    if len(xs) < 3:
        return None
    rnd = random.Random(seed)
    meds = sorted(st.median(rnd.choices(xs, k=len(xs))) for _ in range(n))
    return meds[int(0.05 * n)], meds[int(0.95 * n)]


def group_stats(rows):
    xs = [r["x"] for r in rows]
    v = [r["views"] for r in rows]
    tv = sum(v) or 1
    ci = boot_ci_median(xs)
    return {
        "n": len(rows),
        "median_views": st.median(v),
        "ci90_median_views": [round(math.expm1(ci[0])), round(math.expm1(ci[1]))] if ci else None,
        "likes_per_1k": round(1000 * sum(r["likes"] for r in rows) / tv, 2),
        "ext_replies_per_1k": round(1000 * sum(r["ext_replies"] for r in rows) / tv, 2),
        "shares_per_1k": round(1000 * sum(r["shares"] for r in rows) / tv, 2),
        "mean_x": st.fmean(xs), "sum_x": sum(xs),
    }


def pooled_sigma(groups):
    ss, dof = 0.0, 0
    for rows in groups.values():
        xs = [r["x"] for r in rows]
        if len(xs) > 1:
            m = st.fmean(xs)
            ss += sum((x - m) ** 2 for x in xs)
            dof += len(xs) - 1
    return math.sqrt(ss / dof) if dof > 0 else 1.0


def thompson_p_best(stats, mu0, sigma, seed=7):
    """Normal-Normal 近似:後驗均值往全體平均收縮,後驗變異 = σ²/(n+k0)。回傳每臂「最佳」機率。"""
    rnd = random.Random(seed)
    names = list(stats)
    post = {}
    for k in names:
        n, m = stats[k]["n"], stats[k]["mean_x"]
        post[k] = ((n * m + PRIOR_K * mu0) / (n + PRIOR_K), sigma / math.sqrt(n + PRIOR_K))
    wins = dict.fromkeys(names, 0)
    for _ in range(MC):
        wins[max(names, key=lambda k: rnd.gauss(*post[k]))] += 1
    return {k: wins[k] / MC for k in names}


def mix(p_best):
    """探索底線:share = ε/K + (1-ε)·p_best。"""
    K = len(p_best)
    return {k: EPSILON / K + (1 - EPSILON) * p for k, p in p_best.items()}


def required_n(sigma, effect=0.30):
    """每組要幾篇才能以 80% 檢定力、5% 顯著水準分出「中位數差 effect」(對數常態假設)。"""
    d = math.log(1 + effect) / sigma
    return math.ceil(2 * (1.96 + 0.84) ** 2 / d ** 2)


def tw_date(ts):
    return (parse_ts(ts) + timedelta(hours=8)).date().isoformat()


def pct(sorted_v, q):
    return sorted_v[min(len(sorted_v) - 1, int(q * len(sorted_v)))]


def extra_sections(rows, by_series):
    """診斷用段落:長尾、同日發文數、other 內容抽樣。只出報告,不影響 arms.json。"""
    out = ["", "## 長尾:誰有爆文", "",
           "| 系列 | n | 平均瀏覽 | 中位數 | p90 | 最高 | 前10%貼文占該系列瀏覽 |", "|---|---|---|---|---|---|---|"]
    for s, g in sorted(by_series.items()):
        v = sorted(r["views"] for r in g)
        top_n = max(1, len(v) // 10)
        out.append(f"| {s} | {len(v)} | {st.fmean(v):.0f} | {st.median(v):.0f} | {pct(v, .9)} | {v[-1]} | "
                   f"{100 * sum(v[-top_n:]) / (sum(v) or 1):.0f}% |")

    # 同日發文數 vs 每篇瀏覽(用所有貼文算每天篇數,只看成熟貼文的瀏覽)
    cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    day_cnt = defaultdict(int)
    for p in read_posts():
        if parse_ts(p["ts"]) >= cutoff:
            day_cnt[tw_date(p["ts"])] += 1
    buckets = defaultdict(list)
    for r in rows:
        c = day_cnt[tw_date(r["ts"])]
        buckets["5+" if c >= 5 else str(c)].append(r["views"])
    out += ["", "## 同日發文數 vs 每篇瀏覽", "",
            "(注意:發得多的日子,系列組合也不同,所以這是粗略參考,不是因果證據)", "",
            "| 當天發幾篇 | 貼文數 | 每篇瀏覽中位數 | 每篇平均 |", "|---|---|---|---|"]
    for k in sorted(buckets):
        v = buckets[k]
        out.append(f"| {k} | {len(v)} | {st.median(v):.0f} | {st.fmean(v):.0f} |")

    # other 是什麼:標題前綴統計 + 抽樣
    oth = by_series.get("other", [])
    if oth:
        def norm(t):
            return re.sub(r"^\s*\d{1,2}/\d{1,2}\s*(的)?", "", t.strip().replace("\n", " "))[:10]
        freq = defaultdict(int)
        for r in oth:
            freq[norm(r["text"])] += 1
        out += ["", "## other 的內容(標題前綴出現次數,前 10)", ""]
        out += [f"- `{k}` × {v}" for k, v in sorted(freq.items(), key=lambda kv: -kv[1])[:10]]
        rnd = random.Random(5)
        out += ["", "other 隨機抽樣 12 篇開頭:", ""]
        out += [f"- {r['text'].strip().splitlines()[0][:40] if r['text'].strip() else '(空)'}  → {r['views']} 瀏覽"
                for r in rnd.sample(oth, min(12, len(oth)))]
    return out


def account_section():
    """帳號層級:追蹤人數每日走勢與連結點擊。資料來自 collect_insights 每天存的 data/account/。"""
    rows = []
    d = DATA / "account"
    if d.exists():
        for f in sorted(d.glob("*.json")):
            try:
                rows.append(json.loads(f.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                pass
    out = ["", "## 帳號層級(追蹤人數、連結點擊)", ""]
    if not rows:
        return out + ["尚無帳號快照(需要 collect_insights 每天跑,從有這個功能那天開始累積)。"]
    out += ["| 日期 | 追蹤人數 | 較前一筆 |", "|---|---|---|"]
    prev = None
    for r in rows[-21:]:
        fc = r.get("followers_count")
        delta = "" if (prev is None or fc is None) else f"{fc - prev:+d}"
        out.append(f"| {r['date']} | {fc} | {delta} |")
        if fc is not None:
            prev = fc
    fcs = [r["followers_count"] for r in rows if r.get("followers_count") is not None]
    if len(fcs) >= 2:
        out += ["", f"從 {rows[0]['date']} 到 {rows[-1]['date']}:追蹤人數 {fcs[0]} → {fcs[-1]}({fcs[-1] - fcs[0]:+d})。"]
    clicks = defaultdict(int)
    for r in rows:
        for m in r.get("clicks_raw", []):
            for item in m.get("link_total_values", []) or []:
                clicks[item.get("link_url", "?")] += item.get("value", 0)
    if clicks:
        out += ["", "連結點擊(累計,依網址):"]
        out += [f"- {u}: {v}" for u, v in sorted(clicks.items(), key=lambda kv: -kv[1])[:10]]
    else:
        out += ["", "連結點擊:目前沒有紀錄(你的貼文若沒放連結就是 0)。"]
    return out


def main():
    rows = matured_rows()
    lines = [f"# 成效報告 {utcnow_iso()}", "",
             f"成熟貼文(有 72h/168h 快照,近 {WINDOW_DAYS} 天): **{len(rows)}** 篇", ""]
    arms = {"updated": utcnow_iso(), "n_matured": len(rows), "series_prob": {}, "dims": {}}

    by_series = defaultdict(list)
    for r in rows:
        by_series[r["series"]].append(r)
    if not rows:
        lines.append("沒有成熟資料,先跑 backfill 與 snapshot。")
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        return

    sigma = pooled_sigma(by_series)
    mu0 = st.fmean(r["x"] for r in rows)
    stats = {s: group_stats(g) for s, g in by_series.items()}

    lines += [f"對數瀏覽的組內標準差 σ ≈ **{sigma:.2f}**。以此雜訊,分出「中位數差 30%」每組約需 "
              f"**{required_n(sigma, 0.30)}** 篇,分出 65% 約需 **{required_n(sigma, 0.65)}** 篇。", "",
              "## 各系列", "",
              "| 系列 | n | 瀏覽中位數 | 中位數 90%CI | 讚/千瀏覽 | 外部留言/千瀏覽 | 轉發+引用/千瀏覽 |",
              "|---|---|---|---|---|---|---|"]
    for s, v in sorted(stats.items(), key=lambda kv: -kv[1]["median_views"]):
        lines.append(f"| {s} | {v['n']} | {v['median_views']:.0f} | {v['ci90_median_views']} | "
                     f"{v['likes_per_1k']} | {v['ext_replies_per_1k']} | {v['shares_per_1k']} |")

    lines += extra_sections(rows, by_series)
    lines += account_section()

    # ---- 系列配額 ----
    K = len(stats)
    if len(rows) < MIN_TOTAL or K < 2:
        share = {s: 1 / K for s in stats}
        lines += ["", f"> 成熟貼文 {len(rows)} < {MIN_TOTAL},配額維持均等,不調整。"]
    else:
        pb = thompson_p_best(stats, mu0, sigma)
        share = mix(pb)
        lines += ["", "Thompson 勝率(各系列為「最佳」的機率): " +
                  ", ".join(f"{k}={v:.2f}" for k, v in pb.items())]
    arms["series_prob"] = {s: round(min(1.0, max(MIN_P, DAILY_BUDGET * sh)), 3) for s, sh in share.items()}
    lines += ["", f"series_prob(每日預算 {DAILY_BUDGET}): {arms['series_prob']}"]

    # ---- 系列內的選項(arm 維度)----
    dim_groups = defaultdict(lambda: defaultdict(list))   # "series.dim" -> option -> rows
    for r in rows:
        for dim, opt in r["arm"].items():
            dim_groups[f"{r['series']}.{dim}"][opt].append(r)
    if dim_groups:
        lines += ["", "## 系列內選項", ""]
    for name, opts in dim_groups.items():
        ostats = {o: group_stats(g) for o, g in opts.items()}
        total = sum(v["n"] for v in ostats.values())
        K2 = len(ostats)
        if total < MIN_TOTAL or K2 < 2:
            arms["dims"][name] = {o: 1.0 for o in ostats}
            lines.append(f"- {name}: 樣本 {total} 篇不足,維持均等")
            continue
        s2 = pooled_sigma(opts)
        pb = thompson_p_best(ostats, st.fmean(r["x"] for g in opts.values() for r in g), s2)
        sh = mix(pb)
        arms["dims"][name] = {o: round(v * K2, 3) for o, v in sh.items()}   # 平均 = 1
        lines.append(f"- {name}: " + ", ".join(
            f"{o}(n={ostats[o]['n']}, 中位數{ostats[o]['median_views']:.0f}, 權重{arms['dims'][name][o]})"
            for o in ostats))

    if (DATA / "FREEZE").exists():
        lines += ["", "> 偵測到 data/FREEZE,只出報告,不更新 arms.json。"]
    else:
        ARMS_FILE.parent.mkdir(parents=True, exist_ok=True)
        ARMS_FILE.write_text(json.dumps(arms, ensure_ascii=False, indent=1), encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
