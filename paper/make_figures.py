"""Figures of the mmBench technical report, from analysis.json and paper_data.json (no item content).

  python make_figures.py <paper dir>      -> <paper dir>/figures/fig*.pdf

Okabe-Ito colours, one fixed colour per model in every figure; Chinese labels in a CJK sans font next to Arial.
"""
import json
import math
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
A = json.load(open(os.path.join(ROOT, "analysis.json")))
D = json.load(open(os.path.join(ROOT, "paper_data.json")))
OUT = os.path.join(ROOT, "figures")
os.makedirs(OUT, exist_ok=True)
MM = 1 / 25.4
CAPS = A["caps"]
CAP_NAME = {"reasoning": "学科推理", "perception": "视觉感知", "charts": "图表", "documents": "文档", "spatial": "空间",
            "gui": "界面定位", "video": "视频时序"}
ORDER = ["kimi-k3.1-pro", "MiniMax-M3.1-Flash", "deepseek-flash"]
COLOR = {"kimi-k3.1-pro": "#009E73", "MiniMax-M3.1-Flash": "#0072B2", "deepseek-flash": "#D55E00"}
NAME = A["names"]
GREY, LIGHT, DARK = "#999999", "#E4E4E4", "#555555"


def style():
    have = {f.name for f in font_manager.fontManager.ttflist}
    latin = [f for f in ("Arial", "Helvetica", "Liberation Sans") if f in have] or ["DejaVu Sans"]
    cjk = [f for f in ("STHeiti", "Heiti SC", "PingFang SC", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei") if f in have]
    plt.rcParams.update({
        "font.family": latin[:1] + cjk[:1] + ["DejaVu Sans"], "font.size": 7, "axes.labelsize": 7, "axes.titlesize": 7.5,
        "xtick.labelsize": 6.5, "ytick.labelsize": 6.5, "legend.fontsize": 6.5, "axes.linewidth": 0.6,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 2.5, "ytick.major.size": 2.5,
        "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "axes.unicode_minus": False,
        "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.02})


def save(fig, stem):
    fig.savefig(os.path.join(OUT, f"{stem}.pdf"))
    fig.savefig(os.path.join(OUT, f"{stem}.png"))
    plt.close(fig)


def panel(ax, s):
    ax.text(-0.08, 1.1, s, transform=ax.transAxes, fontsize=8.5, fontweight="bold", va="bottom", ha="left")


def fig1():
    """(a) the composition: capabilities (inner ring) and sources (outer ring); (b) the capability profiles."""
    fig = plt.figure(figsize=(170 * MM, 72 * MM))
    ax = fig.add_subplot(1, 2, 1)
    items = D["items"]
    capn = [sum(v["cap"] == c for v in items.values()) for c in CAPS]
    cap_colors = ["#8DA0CB", "#A6D854", "#FFD92F", "#E5C494", "#B3B3B3", "#FC8D62", "#E78AC3"]  # not the model colours
    src = []
    for c, col in zip(CAPS, cap_colors):
        names = sorted({v["source"] for v in items.values() if v["cap"] == c})
        for s in names:
            src.append((s, sum(v["source"] == s and v["cap"] == c for v in items.values()), col))
    ax.pie(capn, radius=0.68, colors=cap_colors, wedgeprops={"width": 0.36, "edgecolor": "white", "linewidth": 0.8},
           startangle=90, counterclock=False)
    ax.text(0, 0, "354\n道题", ha="center", va="center", fontsize=7.5, fontweight="bold")
    from matplotlib.patches import Patch
    ax.legend([Patch(color=c) for c in cap_colors], [f"{CAP_NAME[c]} {n}" for c, n in zip(CAPS, capn)],
              loc="center left", bbox_to_anchor=(-0.62, 0.5), fontsize=5.8, handlelength=0.9, title="能力（题数）", title_fontsize=6)
    pretty = {"mmmu_pro": "MMMU-Pro", "blink": "BLINK", "chartqa": "ChartQA", "charxiv": "CharXiv", "docvqa": "DocVQA",
              "ocrbench_kie": "OCRBench-KIE", "cvbench_3d": "CV-Bench-3D", "blink_spatial": "BLINK-空间", "mindcube": "MindCube",
              "screenspot_v2": "ScreenSpot-v2", "screenspot_pro": "ScreenSpot-Pro", "timeblind": "TimeBlind"}
    w, _ = ax.pie([n for _, n, _ in src], radius=1.0, colors=[c for *_, c in src],
                  wedgeprops={"width": 0.3, "edgecolor": "white", "linewidth": 0.8, "alpha": 0.6}, startangle=90, counterclock=False)
    for wedge, (s, n, _) in zip(w, src):
        ang = math.radians((wedge.theta1 + wedge.theta2) / 2)
        x, y = math.cos(ang), math.sin(ang)
        ax.annotate(f"{pretty.get(s, s)} {n}", xy=(0.92 * x, 0.92 * y), xytext=(1.22 * x, 1.18 * y), fontsize=5.4,
                    ha="left" if x >= 0 else "right", va="center", arrowprops={"arrowstyle": "-", "lw": 0.4, "color": GREY})
    ax.set_title("(a) 题库构成：7 项能力（内圈）与 12 个来源子集（外圈）", pad=14)
    ax = fig.add_subplot(1, 2, 2, projection="polar")
    ang = [2 * math.pi * i / len(CAPS) for i in range(len(CAPS))] + [0]
    for m in ORDER:
        v = [A["cap"][m][c] for c in CAPS]
        ax.plot(ang, v + v[:1], color=COLOR[m], lw=1.2, label=f"{NAME[m]}（{A['overall'][m]:.1f}）")
        ax.fill(ang, v + v[:1], color=COLOR[m], alpha=0.08)
    ch = [A["chance"][c] for c in CAPS]
    ax.plot(ang, ch + ch[:1], color=GREY, lw=0.8, ls="--", label=f"随机猜测（{A['chance_overall']:.1f}）")
    ax.set_xticks(ang[:-1], [CAP_NAME[c] for c in CAPS])
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100], ["20", "40", "60", "80", ""], fontsize=5, color=GREY)
    ax.set_rlabel_position(102)
    ax.spines["polar"].set_linewidth(0.5)
    ax.grid(lw=0.4, color=LIGHT)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2, fontsize=6)
    ax.set_title("(b) 能力画像（图例括号内为等权总分）", pad=14)
    fig.subplots_adjust(wspace=0.45)
    save(fig, "fig1_overview")


def fig2():
    """The construction and evaluation pipeline, as two rows: build once (solid boxes), then evaluate every model
    (dashed boxes); outlines only, no fill."""
    fig, ax = plt.subplots(figsize=(170 * MM, 62 * MM))
    ax.set_xlim(-0.5, 100.5)
    ax.set_ylim(0, 46)
    ax.axis("off")
    rows = [("构建（一次，得到固定题库）", "-", 25,
             [("11 个公开评测集", "经 Hugging Face\ndatasets-server 按行读取"),
              ("按能力过滤", "一种技能 × 一种答题形式；\n排除测到其他能力的题"),
              ("固定种子分层抽样", "seed = 0；按子任务\n与难度轮流抽取"),
              ("下载与抽帧", "只下载抽中的题；视频\n均匀抽取 16 帧")]),
            ("评测（每个模型）", (0, (4, 2.5)), 1,
             [("统一作答", "同一套 354 题，每题 4 次；\n统一参数，流式调用"),
              ("规则评分", "选项、是非、数值、ANLS、\n坐标；不用模型裁判"),
              ("画像与排名", "各项 95% 区间；按能力\n分层的配对 bootstrap")])]
    for title, ls, y0, steps in rows:
        n = len(steps)
        w = 22.0
        gap = (100 - w * 4) / 3
        x0 = (100 - (n * w + (n - 1) * gap)) / 2
        ax.text(0, y0 + 18.6, title, ha="left", fontsize=6.8, fontweight="bold")
        for i, (head, body) in enumerate(steps):
            x = x0 + i * (w + gap)
            ax.add_patch(Rectangle((x, y0), w, 16, lw=0.7, ls=ls, ec="black", fc="none"))
            ax.text(x + w / 2, y0 + 12, head, ha="center", va="center", fontsize=6.8, fontweight="bold")
            ax.text(x + w / 2, y0 + 5.5, body, ha="center", va="center", fontsize=5.6, color=DARK, linespacing=1.4)
            if i < n - 1:
                ax.annotate("", xy=(x + w + gap - 0.6, y0 + 8), xytext=(x + w + 0.6, y0 + 8),
                            arrowprops={"arrowstyle": "-|>", "lw": 0.6, "color": "black"})
    ax.annotate("", xy=(50, 17.4), xytext=(50, 24.6), arrowprops={"arrowstyle": "-|>", "lw": 0.6, "color": "black"})
    ax.text(51.2, 21, "固定题库 samples/mm.json（354 个题号）", fontsize=5.6, color=DARK, va="center")
    save(fig, "fig2_pipeline")


def bars(ax, vals, cis, labels, ymax=105, chance=None):
    n = len(ORDER)
    width = 0.26
    for r, m in enumerate(ORDER):
        xs = [i + (r - (n - 1) / 2) * width for i in range(len(labels))]
        v = vals[m]
        err = [[a - c[0] for a, c in zip(v, cis[m])], [c[1] - a for a, c in zip(v, cis[m])]]
        b = ax.bar(xs, v, width, color=COLOR[m], lw=0, label=NAME[m], yerr=err,
                   error_kw={"elinewidth": 0.5, "capsize": 1.2, "capthick": 0.5, "ecolor": DARK})
        ax.bar_label(b, labels=[f"{x:.0f}" for x in v], padding=1, fontsize=4.8)
    if chance:
        for i, c in enumerate(chance):
            ax.plot([i - 0.42, i + 0.42], [c, c], color=GREY, lw=0.8, ls="--", label="随机猜测" if i == 0 else None)
    ax.set_xticks(range(len(labels)), labels)
    ax.tick_params(axis="x", length=0)
    ax.set_ylim(0, ymax)
    ax.set_xlim(-0.6, len(labels) - 0.4)


def fig3():
    """Capability scores with 95% intervals and the random-guess level."""
    fig, ax = plt.subplots(figsize=(170 * MM, 58 * MM))
    labels = [CAP_NAME[c] for c in CAPS] + ["总分"]
    vals = {m: [A["cap"][m][c] for c in CAPS] + [A["overall"][m]] for m in ORDER}
    cis = {m: [A["cap_ci"][m][c] for c in CAPS] + [A["overall_ci"][m]] for m in ORDER}
    bars(ax, vals, cis, labels, chance=[A["chance"][c] for c in CAPS] + [A["chance_overall"]])
    ax.axvline(len(CAPS) - 0.5, color=LIGHT, lw=0.6)
    ax.set_ylabel("得分（0–100）↑")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.13), ncol=4)
    save(fig, "fig3_scores")


def fig4():
    """Pairwise differences per capability with paired-bootstrap 95% intervals."""
    pairs = [("kimi-k3.1-pro", "MiniMax-M3.1-Flash"), ("kimi-k3.1-pro", "deepseek-flash"), ("MiniMax-M3.1-Flash", "deepseek-flash")]
    fig, axs = plt.subplots(1, 3, figsize=(170 * MM, 56 * MM), sharey=True)
    rows = CAPS + ["overall"]
    for k, (ax, (a, b)) in enumerate(zip(axs, pairs)):
        p = A["pairs"][f"{a}|{b}"]
        for j, c in enumerate(rows):
            d, (lo, hi) = p[c]["diff"], p[c]["ci"]
            sig = lo > 0 or hi < 0
            col = COLOR[a] if d > 0 else COLOR[b]
            y = len(rows) - 1 - j
            ax.plot([lo, hi], [y, y], color=col if sig else GREY, lw=1.0)
            ax.plot(d, y, "o", ms=3.6 if c == "overall" else 3, mfc=col if sig else "white", mec=col if sig else GREY, mew=0.8)
        ax.axvline(0, color=DARK, lw=0.5)
        ax.axhline(0.5, color=LIGHT, lw=0.5)
        ax.set_yticks(range(len(rows)), [("总分" if c == "overall" else CAP_NAME[c]) for c in rows][::-1])
        ax.set_xlabel("得分差（95% 区间）")
        ax.set_title(f"{NAME[a]}\n− {NAME[b]}", fontsize=6.4)
        ax.set_xlim(-30, 55)
        panel(ax, "abc"[k])
    fig.subplots_adjust(wspace=0.12)
    save(fig, "fig4_pairwise")


def fig5():
    """Score against cost and against output length."""
    fig, axs = plt.subplots(1, 2, figsize=(170 * MM, 60 * MM))
    for k, (ax, key, xl) in enumerate([(axs[0], "cny", "完成全部 1416 次调用的费用（元，按国内站标价，对数轴）"),
                                       (axs[1], "out", "每次调用平均输出 token（含思考，对数轴）")]):
        for m in ORDER:
            x = A["cost"][m]["cny"] if key == "cny" else A["tokens"][m]["out"]
            lo, hi = A["overall_ci"][m]
            ax.errorbar(x, A["overall"][m], yerr=[[A["overall"][m] - lo], [hi - A["overall"][m]]], fmt="o", ms=5,
                        color=COLOR[m], elinewidth=0.7, capsize=2)
            off = {"kimi-k3.1-pro": (6, -2), "MiniMax-M3.1-Flash": (6, 9) if key == "cny" else (-6, 9), "deepseek-flash": (6, -11)}[m]
            ax.annotate(NAME[m], (x, A["overall"][m]), xytext=off, textcoords="offset points", fontsize=6, color=COLOR[m],
                        ha="right" if off[0] < 0 else "left")
        ax.set_xscale("log")
        ax.set_xlabel(xl)
        ax.set_ylabel("等权总分 ↑")
        ax.set_ylim(65, 92)
        ax.grid(lw=0.3, color=LIGHT, which="both")
        panel(ax, "ab"[k])
    from matplotlib.ticker import FixedLocator, NullLocator
    for ax, ticks, lim in ((axs[0], [10, 20, 50, 100, 200, 400], (7, 500)), (axs[1], [500, 1000, 2000, 5000, 10000], (400, 12000))):
        ax.set_xlim(*lim)
        ax.xaxis.set_major_locator(FixedLocator(ticks))
        ax.xaxis.set_minor_locator(NullLocator())
        ax.set_xticklabels([f"{t:,}" for t in ticks])
    fig.subplots_adjust(wspace=0.3)
    save(fig, "fig5_cost")


def fig6():
    """(a) by difficulty tier; (b) avg@4, pass@4 and all@4."""
    fig, axs = plt.subplots(1, 2, figsize=(170 * MM, 56 * MM), gridspec_kw={"width_ratios": [1, 1.25]})
    ax = axs[0]
    tiers = ["L1", "L2", "L3"]
    for m in ORDER:
        ax.plot(range(3), [A["tier"][m][t] for t in tiers], "-o", color=COLOR[m], ms=3.5, lw=1.1, label=NAME[m])
    ax.set_xticks(range(3), [f"{t}（{A['tier_n'][t]} 题）" for t in tiers])
    ax.set_ylabel("得分 ↑")
    ax.set_ylim(55, 100)
    ax.grid(axis="y", lw=0.3, color=LIGHT)
    ax.legend(loc="lower left")
    ax.set_title("按难度分档（所有能力合并）")
    panel(ax, "a")
    ax = axs[1]
    kinds = [("all@4", "4 次全对"), ("avg@4", "4 次平均"), ("pass@4", "至少 1 次对")]
    width = 0.26
    for r, m in enumerate(ORDER):
        xs = [i + (r - 1) * width for i in range(3)]
        v = [A["sampling"][m][k] for k, _ in kinds]
        b = ax.bar(xs, v, width, color=COLOR[m], lw=0, label=NAME[m])
        ax.bar_label(b, labels=[f"{x:.1f}" for x in v], padding=1, fontsize=5)
    ax.set_xticks(range(3), [n for _, n in kinds])
    ax.tick_params(axis="x", length=0)
    ax.set_ylim(50, 100)
    ax.set_ylabel("等权总分 ↑")
    ax.set_title("同一题 4 次采样的稳定性")
    for r, m in enumerate(ORDER):
        ax.text(1.02, 0.86 - r * 0.09, f"{NAME[m].split(' ')[0]}：{A['sampling'][m]['mixed_share']:.0f}% 的题 4 次结果不一致",
                transform=ax.transAxes, fontsize=5.6, color=COLOR[m])
    panel(ax, "b")
    fig.subplots_adjust(wspace=0.3, right=0.8)
    save(fig, "fig6_tiers_sampling")


def fig7():
    """Mean output tokens per call by capability."""
    fig, ax = plt.subplots(figsize=(170 * MM, 52 * MM))
    width = 0.26
    for r, m in enumerate(ORDER):
        xs = [i + (r - 1) * width for i in range(len(CAPS))]
        v = [A["tokens"][m]["cap_out"][c] for c in CAPS]
        b = ax.bar(xs, v, width, color=COLOR[m], lw=0, label=NAME[m])
        ax.bar_label(b, labels=[f"{x / 1000:.1f}k" if x >= 1000 else f"{x:.0f}" for x in v], padding=1, fontsize=4.8)
    ax.set_yscale("log")
    ax.set_ylim(80, 30000)
    from matplotlib.ticker import FixedLocator, NullLocator
    ax.yaxis.set_major_locator(FixedLocator([100, 300, 1000, 3000, 10000]))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.set_yticklabels(["100", "300", "1,000", "3,000", "10,000"])
    ax.set_xticks(range(len(CAPS)), [CAP_NAME[c] for c in CAPS])
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel("每次调用平均输出 token（对数轴）↓")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.14), ncol=3)
    save(fig, "fig7_tokens")


style()
for f in (fig1, fig2, fig3, fig4, fig5, fig6, fig7):
    f()
print("figures:", sorted(os.listdir(OUT)))
