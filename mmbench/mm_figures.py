"""The capability-profile chart of a report, in Nature figure style (183 mm wide, Arial 5-7 pt, no top/right spines,
outward ticks, frameless legend, colour-blind-safe Okabe-Ito colours, fonts embedded as TrueType): one group of bars
per capability plus the overall score, one bar per model, 95% intervals as error bars, a value on every bar.

  draw(profile, out_dir) -> ["fig_profile"]   (profile = mm_report.profile(stats); writes .pdf and .png)

Chinese labels fall back to a CJK sans font (Heiti on the Mac, Noto Sans CJK on Linux) next to Arial. Importing this
module raises ImportError when matplotlib is missing.
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

import mm_lib as M  # noqa: E402

MM = 1 / 25.4
COLORS = ("#0072B2", "#D55E00", "#009E73", "#E69F00", "#56B4E9", "#CC79A7", "#F0E442")  # Okabe-Ito
LIGHT, DARK = "#E4E4E4", "#7A7A7A"
CJK = ("STHeiti", "Heiti SC", "Heiti TC", "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei",
       "Arial Unicode MS")


def style():
    have = {f.name for f in font_manager.fontManager.ttflist}
    latin = [f for f in ("Arial", "Helvetica", "Liberation Sans") if f in have] or ["DejaVu Sans"]
    plt.rcParams.update({
        "font.family": latin[:1] + [f for f in CJK if f in have][:1] + ["DejaVu Sans"],
        "font.size": 7, "axes.labelsize": 7, "axes.titlesize": 7, "xtick.labelsize": 6, "ytick.labelsize": 6,
        "legend.fontsize": 6, "axes.linewidth": 0.5, "xtick.major.width": 0.5, "ytick.major.width": 0.5,
        "xtick.major.size": 2.5, "ytick.major.size": 2.5, "xtick.direction": "out", "ytick.direction": "out",
        "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "legend.handlelength": 1.0,
        "legend.handleheight": 0.7, "legend.columnspacing": 1.0, "axes.unicode_minus": False, "pdf.fonttype": 42,
        "ps.fonttype": 42, "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    })


def save(fig, out_dir, stem):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(out_dir, f"{stem}.{ext}"))
    plt.close(fig)
    return stem


def draw(p, out_dir):
    style()
    n = len(p["names"])
    labels = [M.CAP_NAME[c] for c in p["caps"]] + ["总分"]
    width = min(0.8 / n, 0.38)
    fig, ax = plt.subplots(figsize=(183 * MM, 62 * MM))
    for r in range(n):
        vals = [p["cap"][r][c] for c in p["caps"]] + [p["overall"][r]]
        cis = [p["cap_ci"][r][c] for c in p["caps"]] + [p["overall_ci"][r]]
        xs = [i + (r - (n - 1) / 2) * width for i in range(len(labels))]
        err = [[v - c[0] for v, c in zip(vals, cis)], [c[1] - v for v, c in zip(vals, cis)]]
        bars = ax.bar(xs, vals, width, color=COLORS[r % len(COLORS)], linewidth=0, label=p["names"][r],
                      yerr=err, error_kw={"elinewidth": 0.5, "capsize": 1.2, "capthick": 0.5, "ecolor": DARK})
        ax.bar_label(bars, labels=[f"{v:.0f}" for v in vals], padding=1, fontsize=5, label_type="center", color="white")
    ax.axvline(len(labels) - 1.5, color=LIGHT, linewidth=0.5)
    ax.set_xticks(range(len(labels)), labels)
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel("得分 (0-100) ↑")
    ax.set_ylim(0, 105)
    ax.set_xlim(-0.6, len(labels) - 0.4)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.12), ncol=min(n, 4))
    return [save(fig, out_dir, "fig_profile")]
