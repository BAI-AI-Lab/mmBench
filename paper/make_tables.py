"""LaTeX tables of the mmBench technical report, generated from analysis.json and paper_data.json so that no number
is copied by hand.

  python make_tables.py <paper dir>      -> <paper dir>/tables/*.tex
"""
import collections
import json
import os
import statistics
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
A = json.load(open(os.path.join(ROOT, "analysis.json")))
D = json.load(open(os.path.join(ROOT, "paper_data.json")))
OUT = os.path.join(ROOT, "tables")
os.makedirs(OUT, exist_ok=True)
CAPS = A["caps"]
CN = {"reasoning": "学科推理", "perception": "视觉感知", "charts": "图表", "documents": "文档", "spatial": "空间",
      "gui": "界面定位", "video": "视频时序"}
ORDER = ["kimi-k3.1-pro", "MiniMax-M3.1-Flash", "deepseek-flash"]
NAME = A["names"]
items = D["items"]


def write(name, s):
    open(os.path.join(OUT, name), "w").write(s.strip() + "\n")


def rank_marks(vals):
    """best bold, second underlined (ties share the mark)"""
    order = sorted(set(vals), reverse=True)
    return [r"\textbf{%s}" if v == order[0] else (r"\underline{%s}" if len(order) > 1 and v == order[1] else "%s") for v in vals]


# ---------------------------------------------------------------- main results
cols = CAPS + ["overall"]
head = " & ".join(CN[c] for c in CAPS) + r" & \textbf{总分}"
rows = [r"随机猜测 & " + " & ".join(f"{A['chance'][c]:.1f}" for c in CAPS) + f" & {A['chance_overall']:.1f} \\\\", r"\midrule"]
marks = {c: dict(zip(ORDER, rank_marks([round(A["cap"][m][c] if c != "overall" else A["overall"][m], 1) for m in ORDER]))) for c in cols}
for m in ORDER:
    v = [A["cap"][m][c] for c in CAPS] + [A["overall"][m]]
    ci = [A["cap_ci"][m][c] for c in CAPS] + [A["overall_ci"][m]]
    rows.append(NAME[m] + " & " + " & ".join(marks[c][m] % f"{x:.1f}" for c, x in zip(cols, v)) + r" \\")
    rows.append(r"\multicolumn{1}{r}{\scriptsize\color{gray}95\% 区间} & " +
                " & ".join(r"{\scriptsize\color{gray}%.1f--%.1f}" % tuple(c) for c in ci) + r" \\[2pt]")
write("main_results.tex", r"""
\begin{tabular}{l*{7}{c}c}
\toprule
模型 & """ + head + r""" \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}""")

# ---------------------------------------------------------------- statistics per capability
TYPE = {"mcq": "选择", "yesno": "是非", "exact": "文字", "number": "数值", "anls": "ANLS", "point_in_box": "坐标"}
rows = []
for c in CAPS:
    v = [x for x in items.values() if x["cap"] == c]
    types = collections.Counter(TYPE[x["type"]] for x in v)
    media = statistics.mean((x["frames"] or x["images"]) for x in v)
    media_s = f"{media:.0f} 帧" if c == "video" else f"{media:.1f}"
    mp = statistics.median(x["size"][0] * x["size"][1] / 1e6 for x in v if x["size"])
    rows.append(f"{CN[c]} & {len(v)} & {' / '.join(f'{k} {n}' for k, n in types.most_common())} & {media_s} & {mp:.2f} & "
                f"{statistics.mean(x['q_words'] for x in v):.0f} & {A['chance'][c]:.1f} \\\\")
tiers = A["tier_n"]
write("statistics.tex", r"""
\begin{tabular}{lrlrrrr}
\toprule
能力 & 题数 & 题型（题数） & 每题图片数 & 分辨率中位数（MP） & 提示词词数 & 随机猜测得分 \\
\midrule
""" + "\n".join(rows) + r"""
\midrule
合计 & """ + str(len(items)) + r""" & \multicolumn{4}{l}{难度：L1 """ + f"{tiers['L1']}" + r""" 题，L2 """ + f"{tiers['L2']}" +
      r""" 题，L3 """ + f"{tiers['L3']}" + r""" 题} & """ + f"{A['chance_overall']:.1f}" + r"""（等权） \\
\bottomrule
\end{tabular}""")

# ---------------------------------------------------------------- tokens and cost
rows = []
best_cost = min(A["cost"][m]["cny"] for m in ORDER)
for m in ORDER:
    t, c = A["tokens"][m], A["cost"][m]
    rows.append(f"{NAME[m]} & {t['in']:,.0f} & {t['hit']:,.0f} & {t['out']:,.0f}（{t['out_median']:,.0f}） & "
                f"{100 * t['reasoning'] / t['out']:.1f}\\% & {t['latency_median']:.1f} & "
                f"{c['cny']:.2f} & {c['cny'] / len(items):.3f} & \\${c['usd']:.2f} \\\\")
write("cost.tex", r"""
\begin{tabular}{lrrrrrrrr}
\toprule
 & \multicolumn{4}{c}{每次调用平均 token} & & \multicolumn{3}{c}{全部 1416 次调用的费用 $\downarrow$} \\
\cmidrule(lr){2-5}\cmidrule(lr){7-9}
模型 & 输入 & 其中缓存命中 & 输出（中位数） & 思考占输出 & 延迟中位数（秒）$\downarrow$ & 元 & 元 / 题 & 美元参考 \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}""")

# ---------------------------------------------------------------- per source (appendix)
src_name = {"mmmu_pro": "MMMU-Pro", "blink": "BLINK", "chartqa": "ChartQA", "charxiv": "CharXiv", "docvqa": "DocVQA",
            "ocrbench_kie": "OCRBench-KIE", "cvbench_3d": "CV-Bench-3D", "blink_spatial": "BLINK 空间子任务", "mindcube": "MindCube",
            "screenspot_v2": "ScreenSpot-v2", "screenspot_pro": "ScreenSpot-Pro", "timeblind": "TimeBlind"}
S = D["runs"]
rows = []
for c in CAPS:
    for s in sorted({x["source"] for x in items.values() if x["cap"] == c}, key=lambda s: min(x["tier"] for x in items.values() if x["source"] == s)):
        ids = [i for i, x in items.items() if x["source"] == s]
        tiers_s = "/".join(sorted({items[i]["tier"] for i in ids}))
        v = [100 * statistics.mean(statistics.mean(S[m]["scores"][i]) for i in ids) for m in ORDER]
        ch = 100 * statistics.mean(items[i]["chance"] for i in ids)
        rows.append(f"{CN[c]} & {src_name[s]} & {tiers_s} & {len(ids)} & {ch:.1f} & " +
                    " & ".join(mk % f"{x:.1f}" for mk, x in zip(rank_marks([round(x, 1) for x in v]), v)) + r" \\")
write("per_source.tex", r"""
\begin{tabular}{llcrrrrr}
\toprule
能力 & 来源 & 难度 & 题数 & 随机 & """ + " & ".join(NAME[m] for m in ORDER) + r""" \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}""")

# ---------------------------------------------------------------- per-item wins / ties / losses (appendix)
pairs = [("kimi-k3.1-pro", "MiniMax-M3.1-Flash"), ("kimi-k3.1-pro", "deepseek-flash"), ("MiniMax-M3.1-Flash", "deepseek-flash")]
short = {"kimi-k3.1-pro": "Kimi", "MiniMax-M3.1-Flash": "MiniMax", "deepseek-flash": "DeepSeek"}
rows = []
for c in CAPS:
    cells = []
    for a, b in pairs:
        win, tie, loss = A["win_tie_loss"][f"{a}|{b}"][c]
        d = A["pairs"][f"{a}|{b}"][c]
        sig = d["ci"][0] > 0 or d["ci"][1] < 0
        cells.append(f"{win} / {tie} / {loss} & {d['diff']:+.1f}{'$^{*}$' if sig else ''}")
    rows.append(f"{CN[c]} & " + " & ".join(cells) + r" \\")
cells = []
for a, b in pairs:
    w = sum(A["win_tie_loss"][f"{a}|{b}"][c][0] for c in CAPS)
    t = sum(A["win_tie_loss"][f"{a}|{b}"][c][1] for c in CAPS)
    l_ = sum(A["win_tie_loss"][f"{a}|{b}"][c][2] for c in CAPS)
    d = A["pairs"][f"{a}|{b}"]["overall"]
    sig = d["ci"][0] > 0 or d["ci"][1] < 0
    cells.append(f"{w} / {t} / {l_} & {d['diff']:+.1f}{'$^{*}$' if sig else ''}")
write("win_tie_loss.tex", r"""
\begin{tabular}{l*{3}{rr}}
\toprule
 & \multicolumn{2}{c}{Kimi − MiniMax} & \multicolumn{2}{c}{Kimi − DeepSeek} & \multicolumn{2}{c}{MiniMax − DeepSeek} \\
\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}
能力 & 胜 / 平 / 负 & 分差 & 胜 / 平 / 负 & 分差 & 胜 / 平 / 负 & 分差 \\
\midrule
""" + "\n".join(rows) + r"""
\midrule
全部 & """ + " & ".join(cells) + r""" \\
\bottomrule
\end{tabular}""")

# ---------------------------------------------------------------- output tokens per capability (appendix)
rows = []
for c in CAPS:
    rows.append(f"{CN[c]} & " + " & ".join(f"{A['tokens'][m]['cap_in'][c]:,.0f} & {A['tokens'][m]['cap_out'][c]:,.0f}" for m in ORDER) + r" \\")
write("tokens_by_cap.tex", r"""
\begin{tabular}{l*{3}{rr}}
\toprule
 & \multicolumn{2}{c}{Kimi K3.1 Pro} & \multicolumn{2}{c}{MiniMax M3.1 Flash} & \multicolumn{2}{c}{DeepSeek Flash V4.1-1017} \\
\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}
能力 & 输入 & 输出 & 输入 & 输出 & 输入 & 输出 \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}""")
print("tables:", sorted(os.listdir(OUT)))
