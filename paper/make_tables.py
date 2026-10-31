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
# ---------------------------------------------------------------- vendor claims against the observations (sec. results)
K, M, S = ORDER
src = {sname: {m: 100 * statistics.mean(statistics.mean(S_[m]["scores"][i]) for i in ids_)
               for m in ORDER} for sname, ids_ in
       {sn: [i for i, x in items.items() if x["source"] == sn] for sn in {x["source"] for x in items.values()}}.items()
       for S_ in [D["runs"]]}


def sg(x):
    return f"{x:+.1f}".replace("-", "$-$").replace("+", "")


def dci(a, b, c):
    """difference a - b on capability c with its interval, as '19.0 [8.0, 29.0]'"""
    key, sign = (f"{a}|{b}", 1) if f"{a}|{b}" in A["pairs"] else (f"{b}|{a}", -1)
    d = A["pairs"][key][c]
    lo, hi = sorted(sign * x for x in d["ci"])
    return f"{sg(sign * d['diff'])} [{sg(lo)}, {sg(hi)}]"


cap = lambda m, c: f"{A['cap'][m][c]:.1f}"  # noqa: E731
sp = A["speed"]
tk = A["tokens"]
mp = lambda sn: statistics.median(x["size"][0] * x["size"][1] / 1e6 for x in items.values() if x["source"] == sn and x["size"])  # noqa: E731
over = lambda sn: sum(x["size"][0] * x["size"][1] > 1300 * 1300 for x in items.values() if x["source"] == sn and x["size"])  # noqa: E731
nsrc = lambda sn: sum(x["source"] == sn for x in items.values())  # noqa: E731
rows = {
    K: [
        ("坐标监督（绝对与归一化坐标）；编码器支持至 3584$^2$ 像素（K3）", "界面定位",
         f"{cap(K, 'gui')}，三者最高；领先 MiniMax {dci(K, M, 'gui')}、DeepSeek {dci(K, S, 'gui')}，均大于总分差"
         f"（{A['pairs'][f'{K}|{M}']['overall']['diff']:.1f}、{A['pairs'][f'{K}|{S}']['overall']['diff']:.1f}）；ScreenSpot-Pro {src['screenspot_pro'][K]:.1f}",
         "一致，可归因"),
        ("“擅长 3D 创作与空间推理”（K3.1）", "空间",
         f"{cap(K, 'spatial')}；领先 MiniMax {dci(K, M, 'spatial')}，大于总分差；领先 DeepSeek {dci(K, S, 'spatial')}，与总分差相当",
         "部分一致"),
        ("带 Python 沙箱的视觉推理强化学习，面向 STEM 视觉推理与图表（K3）", "学科推理、图表",
         f"学科推理领先 {dci(K, M, 'reasoning')}、{dci(K, S, 'reasoning')}，小于总分差；图表领先 {dci(K, M, 'charts')}、"
         f"{dci(K, S, 'charts')}，区间含 0；本文不提供工具", "不一致（无工具时）"),
        ("按 token 预算约束推理长度的强化学习（K3）", "思考效率",
         f"每次调用平均输出 {tk[K]['out']:,.0f} token（中位数 {tk[K]['out_median']:,.0f}），三者最短", "一致（token 计数跨厂商不可比）"),
        ("视频通路（帧内、帧间分解注意力）；长程编程、金融、事实准确性", "视频时序等", "本文以帧图片输入视频，其余不在本文范围", "本文未测"),
    ],
    M: [
        ("电脑操作上的“代际提升”，OSWorld 2.0 61.7；M3 可操作桌面电脑", "界面定位",
         f"{cap(M, 'gui')}；领先 DeepSeek {dci(M, S, 'gui')}，而总分差只有 {dci(M, S, 'overall')}；落后 Kimi {A['pairs'][f'{K}|{M}']['gui']['diff']:.1f}",
         "一致，可归因（相对 DeepSeek）"),
        ("全部层改为稀疏注意力、量化感知训练、DSpark 投机解码；称输出速度中位数 170 token/s 以上", "生成速度",
         f"首个 token 之后的生成速度中位数 {sp[M]['gen_median']:.0f} token/s，低于所称；DeepSeek 为 {sp[S]['gen_median']:.0f}",
         "不一致（国内站、8 路并发、多图输入）"),
        ("在线推理快近 3 倍、使用成本降低 70\\%（相对前代）", "—",
         f"没有前代对照；全部评测费用 {A['cost'][M]['cny']:.2f} 元，三者最低", "无法检验"),
        ("从第 0 步起混合多种模态训练（M3）", "全部", "没有指向具体能力", "无法单独检验"),
        ("视频原生输入（M3 Video-MME 85.4）；智能体、编程、网络安全", "视频时序等", "本文以帧图片输入视频，其余不在本文范围", "本文未测"),
    ],
    S: [
        ("“视觉定位与指点”领域数据、电脑操作轨迹", "界面定位",
         f"{cap(S, 'gui')}，三者最低；ScreenSpot-v2 {src['screenspot_v2'][S]:.1f}、ScreenSpot-Pro {src['screenspot_pro'][S]:.1f}", "不一致"),
        ("接口把总像素超过约 1300$^2$ 的图片缩小，每图至多 1024 token（设计限制）", "高分辨率细节",
         f"ScreenSpot-Pro 截图中位 {mp('screenspot_pro'):.1f} MP，{over('screenspot_pro')}/{nsrc('screenspot_pro')} 张被缩小，得分 {src['screenspot_pro'][S]:.1f}；"
         f"DocVQA {over('docvqa')}/{nsrc('docvqa')} 张被缩小，仍得 {src['docvqa'][S]:.1f}", "与设计限制一致"),
        ("OCR 领域数据", "文档",
         f"{cap(S, 'documents')}；领先 MiniMax {dci(S, M, 'documents')}，与 Kimi 差 {dci(S, K, 'documents')}，均好于总分位置", "一致，可归因"),
        ("视觉推理与专业图表的评测超过 Kimi K3", "图表、学科推理",
         f"图表与 Kimi 差 {dci(S, K, 'charts')}，好于总分差 {dci(S, K, 'overall')}；学科推理差 {dci(S, K, 'reasoning')}",
         "图表一致；学科推理不一致"),
        ("无空间方向的声称（只报告基座 CVBench 77.9）", "空间", f"{cap(S, 'spatial')}；领先 MiniMax {dci(S, M, 'spatial')}", "无对应声称"),
        ("1017 版缩短输出长度（相对 0910 版）", "—",
         f"每次调用平均输出 {tk[S]['out']:,.0f} token，三者最长；没有 0910 版对照", "无法检验"),
        ("KV cache 压缩、Engram 条件记忆", "长上下文、成本", "本文单题输入短", "本文未测"),
    ],
}
body = []
for m in ORDER:
    body.append(r"\multicolumn{4}{@{}l}{\textbf{" + NAME[m] + r"}} \\")
    body += [f"{a} & {b} & {c} & {d} \\\\" for a, b, c, d in rows[m]]
    body.append(r"\midrule" if m != ORDER[-1] else "")
write("attribution.tex", r"""
\begin{tabularx}{\linewidth}{@{}>{\raggedright\arraybackslash}p{4.1cm}>{\raggedright\arraybackslash}p{1.4cm}>{\raggedright\arraybackslash}X>{\raggedright\arraybackslash}p{2.4cm}@{}}
\toprule
厂商声称（来源） & 对应能力 & 本文观测（得分差与 95\% 区间） & 判定 \\
\midrule
""" + "\n".join(x for x in body if x) + r"""
\bottomrule
\end{tabularx}""")

# ---------------------------------------------------------------- vendor-reported scores on the sources we sample
off = [("MMMU-Pro 标准版", "mmmu_pro", [(K, "84.1", ""), (M, "78.1", "前代 M3"), (S, "80.6", "Kimi 博客中的对比值")],
        "本文排除表格、统计图与截图题，50 题"),
       ("CharXiv 推理题", "charxiv", [(K, "89.0", ""), (M, "82.5", "GPT-5.5 裁判"), (S, "77.0", "Kimi 博客中的对比值")],
        "本文 35 题、规则评分；厂商用模型裁判"),
       ("DocVQA", "docvqa", [(S, "95.6", "基座，4-shot，模型裁判")], "本文为接口模型、ANLS"),
       ("CV-Bench", "cvbench_3d", [(S, "77.9", "基座，4-shot，全集")], "本文只用 3D 子集，14 题")]
body = []
for name, sn, vals, note in off:
    for j, (m, v, how) in enumerate(vals):
        body.append((f"\\multirow{{{len(vals)}}}{{*}}{{{name}}}" if j == 0 else "") + f" & {NAME[m]} & {v}" +
                    (f"（{how}）" if how else "") + f" & {src[sn][m]:.1f} & " +
                    (f"\\multirow{{{len(vals)}}}{{*}}{{\\parbox{{4.2cm}}{{\\raggedright {note}}}}}" if j == 0 else "") + r" \\")
    body.append(r"\midrule")
write("official.tex", r"""
\begin{tabular}{lllrl}
\toprule
评测 & 模型 & 厂商自报 & 本文子集 $\uparrow$ & 主要口径差异 \\
\midrule
""" + "\n".join(body[:-1]) + r"""
\bottomrule
\end{tabular}""")
print("tables:", sorted(os.listdir(OUT)))
