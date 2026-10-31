"""Every number of the report from paper_data.json: per-capability scores with bootstrap intervals, the random-guess
baseline, avg@4 / pass@4 / all@4 and sample agreement, per-capability pairwise differences with paired intervals,
per-tier scores, how many models solve each item, tokens per capability, and cost at each vendor's list prices
(DeepSeek peak / off-peak by each call's start time); written to analysis.json.

  python paper/analysis.py
"""
import collections
import datetime
import json
import os
import random
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "paper_data.json")))
# yuan / USD per 1M tokens (China site / international site list prices, 2026-10): in (cache miss), cache hit, out
CNY = {"MiniMax-M3.1-Flash": {"in": 1.0, "hit": 0.10, "out": 4.0}, "kimi-k3.1-pro": {"in": 13.0, "hit": 1.30, "out": 68.0},
       "deepseek-flash": {"in": 2.0, "hit": 0.04, "out": 8.0, "off": {"in": 1.0, "hit": 0.02, "out": 4.0}}}
USD = {"MiniMax-M3.1-Flash": {"in": 0.15, "hit": 0.015, "out": 0.60}, "kimi-k3.1-pro": {"in": 2.0, "hit": 0.20, "out": 10.0},
       "deepseek-flash": {"in": 0.30, "hit": 0.006, "out": 1.20, "off": {"in": 0.15, "hit": 0.003, "out": 0.60}}}
PEAK_BJ = [(9, 12), (14, 18)]  # DeepSeek peak hours, Beijing time, Monday to Friday


def price(p, start):
    if "off" not in p:
        return p
    d = datetime.datetime.fromtimestamp(start, datetime.timezone(datetime.timedelta(hours=8)))
    return p if d.weekday() < 5 and any(a <= d.hour < b for a, b in PEAK_BJ) else p["off"]


def cost(calls, table, peak=False):
    total = 0.0
    for c in calls:
        p = table if peak or "off" not in table else price(table, c["start"])
        total += ((c["in"] - c["hit"]) * p["in"] + c["hit"] * p["hit"] + c["out"] * p["out"]) / 1e6
    return total
CAPS = ["reasoning", "perception", "charts", "documents", "spatial", "gui", "video"]
MODELS = ["kimi-k3.1-pro", "MiniMax-M3.1-Flash", "deepseek-flash"]
items = D["items"]
ids = sorted(items)
by_cap = {c: [i for i in ids if items[i]["cap"] == c] for c in CAPS}
S = {m: D["runs"][m]["scores"] for m in MODELS}
mean = {m: {i: statistics.mean(S[m][i]) for i in ids} for m in MODELS}
rng = random.Random(0)
B = 2000


def cap_score(m, pick):
    return {c: 100 * statistics.mean(mean[m][i] for i in pick[c]) for c in CAPS}


boots = []
for _ in range(B):
    pick = {c: [rng.choice(v) for _ in v] for c, v in by_cap.items()}
    boots.append({m: cap_score(m, pick) for m in MODELS})
ci = lambda xs: [sorted(xs)[int(0.025 * (len(xs) - 1))], sorted(xs)[int(0.975 * (len(xs) - 1))]]  # noqa: E731
out = {"caps": CAPS, "models": MODELS, "names": {m: D["runs"][m]["name"] for m in MODELS}}
out["cap"] = {m: cap_score(m, by_cap) for m in MODELS}
out["overall"] = {m: statistics.mean(out["cap"][m].values()) for m in MODELS}
out["cap_ci"] = {m: {c: ci([b[m][c] for b in boots]) for c in CAPS} for m in MODELS}
out["overall_ci"] = {m: ci([statistics.mean(b[m].values()) for b in boots]) for m in MODELS}
out["chance"] = {c: 100 * statistics.mean(items[i]["chance"] for i in by_cap[c]) for c in CAPS}
out["chance_overall"] = statistics.mean(out["chance"].values())
# pairwise per capability
pairs = {}
for a, b in [(0, 1), (0, 2), (1, 2)]:
    ma, mb = MODELS[a], MODELS[b]
    pairs[f"{ma}|{mb}"] = {c: {"diff": out["cap"][ma][c] - out["cap"][mb][c],
                               "ci": ci([bb[ma][c] - bb[mb][c] for bb in boots])} for c in CAPS}
    pairs[f"{ma}|{mb}"]["overall"] = {"diff": out["overall"][ma] - out["overall"][mb],
                                      "ci": ci([statistics.mean(bb[ma].values()) - statistics.mean(bb[mb].values()) for bb in boots])}
out["pairs"] = pairs
# how much a capability difference exceeds the overall difference of the same pair (the attribution test), paired
excess = {}
for a, b in [(0, 1), (0, 2), (1, 2)]:
    ma, mb = MODELS[a], MODELS[b]
    excess[f"{ma}|{mb}"] = {c: {"diff": pairs[f"{ma}|{mb}"][c]["diff"] - pairs[f"{ma}|{mb}"]["overall"]["diff"],
                                "ci": ci([(bb[ma][c] - bb[mb][c]) - (statistics.mean(bb[ma].values()) - statistics.mean(bb[mb].values()))
                                          for bb in boots])} for c in CAPS}
out["excess"] = excess
# sampling: avg@4, pass@4 (best sample), all@4 (worst sample), agreement
samp = {}
for m in MODELS:
    best = {c: 100 * statistics.mean(max(S[m][i]) for i in by_cap[c]) for c in CAPS}
    worst = {c: 100 * statistics.mean(min(S[m][i]) for i in by_cap[c]) for c in CAPS}
    mixed = sum(max(S[m][i]) != min(S[m][i]) for i in ids)
    samp[m] = {"pass@4": statistics.mean(best.values()), "all@4": statistics.mean(worst.values()),
               "avg@4": out["overall"][m], "mixed_items": mixed, "mixed_share": 100 * mixed / len(ids),
               "pass_cap": best, "all_cap": worst,
               "item_sd": statistics.mean(statistics.pstdev(S[m][i]) for i in ids)}
out["sampling"] = samp
# tiers
out["tier"] = {m: {t: 100 * statistics.mean(mean[m][i] for i in ids if items[i]["tier"] == t) for t in ("L1", "L2", "L3")} for m in MODELS}
out["tier_n"] = {t: sum(items[i]["tier"] == t for i in ids) for t in ("L1", "L2", "L3")}
# how many of the three models solve an item (item mean >= 0.5)
solved = collections.defaultdict(lambda: [0, 0, 0, 0])
for i in ids:
    k = sum(mean[m][i] >= 0.5 for m in MODELS)
    solved[items[i]["cap"]][k] += 1
out["solved_by"] = dict(solved)
# per item wins / losses per capability (item mean, ties within 1e-9)
wl = {}
for a, b in [(0, 1), (0, 2), (1, 2)]:
    ma, mb = MODELS[a], MODELS[b]
    wl[f"{ma}|{mb}"] = {c: [sum(mean[ma][i] > mean[mb][i] + 1e-9 for i in by_cap[c]), sum(abs(mean[ma][i] - mean[mb][i]) <= 1e-9 for i in by_cap[c]),
                           sum(mean[mb][i] > mean[ma][i] + 1e-9 for i in by_cap[c])] for c in CAPS}
out["win_tie_loss"] = wl
# tokens per capability
tok = {}
for m in MODELS:
    per = collections.defaultdict(list)
    for c in D["runs"][m]["calls"]:
        per[items[c["id"]]["cap"]].append(c)
    calls = D["runs"][m]["calls"]
    tok[m] = {"in": statistics.mean(c["in"] for c in calls), "hit": statistics.mean(c["hit"] for c in calls),
              "out": statistics.mean(c["out"] for c in calls), "reasoning": statistics.mean(c["reasoning"] for c in calls),
              "out_median": statistics.median(c["out"] for c in calls),
              "latency_median": statistics.median(c["latency"] for c in calls),
              "cap_out": {c: statistics.mean(x["out"] for x in per[c]) for c in CAPS},
              "cap_in": {c: statistics.mean(x["in"] for x in per[c]) for c in CAPS},
              "total_in": sum(c["in"] for c in calls), "total_out": sum(c["out"] for c in calls)}
out["tokens"] = tok
# generation speed per call: output tokens / whole call, and output tokens / time after the first token (calls with a
# first-token time and at least 1 s of generation after it); the aggregate is token-weighted
speed = {}
for m in MODELS:
    calls = D["runs"][m]["calls"]
    gen = [c for c in calls if c.get("ttft") is not None and c["latency"] - c["ttft"] >= 1]
    speed[m] = {"call_median": statistics.median(c["out"] / c["latency"] for c in calls if c["latency"] > 0),
                "gen_median": statistics.median(c["out"] / (c["latency"] - c["ttft"]) for c in gen),
                "gen_aggregate": sum(c["out"] for c in gen) / sum(c["latency"] - c["ttft"] for c in gen),
                "gen_n": len(gen), "ttft_median": statistics.median(c["ttft"] for c in calls if c.get("ttft") is not None)}
out["speed"] = speed
out["cost"] = {m: {"cny": cost(D["runs"][m]["calls"], CNY[m]), "usd": cost(D["runs"][m]["calls"], USD[m]),
                  "cny_peak": cost(D["runs"][m]["calls"], CNY[m], peak=True)} for m in MODELS}
json.dump(out, open(os.path.join(HERE, "analysis.json"), "w"), indent=1, ensure_ascii=False)
for m in MODELS:
    print(f"{out['names'][m]:<26} overall {out['overall'][m]:.1f} {[round(x, 1) for x in out['overall_ci'][m]]} | pass@4 {samp[m]['pass@4']:.1f} all@4 {samp[m]['all@4']:.1f} "
          f"mixed items {samp[m]['mixed_items']} ({samp[m]['mixed_share']:.0f}%) | tier {[round(v, 1) for v in out['tier'][m].values()]} | "
          f"out {tok[m]['out']:.0f} (median {tok[m]['out_median']:.0f}) | ¥{out['cost'][m]['cny']:.2f} (peak ¥{out['cost'][m]['cny_peak']:.2f}) ${out['cost'][m]['usd']:.2f}")
print("chance", {c: round(v, 1) for c, v in out["chance"].items()}, "overall", round(out["chance_overall"], 1))
print("solved by 0/1/2/3 models:", {c: v for c, v in out["solved_by"].items()})
for k, v in pairs.items():
    print(k, {c: (round(x["diff"], 1), [round(y, 1) for y in x["ci"]]) for c, x in v.items()})
