"""Rendering and accounting helpers of the report (used by mm_report.py): tables and text blocks for both Markdown
and LaTeX, the model notes section, the exact sign test, and tokens and cost per API call.

A report is a list of (section title, blocks); a block is a string, a table (table()), a figure with its fallback
table (figure()), or a tuple ("h", heading) / ("ul", items) / ("links", [(title, url)]).
"""
import datetime
import math
import statistics

FIGS = set()  # figures drawn for this report (mm_figures.py, needs matplotlib); a figure stands in for its table


def tex(s):
    return (str(s).replace("\\", r"\textbackslash{}").replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")
            .replace("#", r"\#").replace("$", r"\$"))


def table(head, rows, align, groups=None, tex_spec=None):
    """A table for both renderers: head = column names, groups = [(label, span), ...] over them (label "" = none),
    align = one l/r per column; tex_spec overrides the LaTeX column spec (e.g. wrapping p{} columns)."""
    return {"head": head, "rows": rows, "align": align, "groups": groups, "tex_spec": tex_spec}


def figure(stem, caption, fallback, width=1.0):
    """A chart in place of a table; width = share of the text width in the PDF."""
    return ("fig", {"file": stem, "caption": caption, "table": fallback, "width": width})


def intro(stats, db):
    """First section: what each model is, what changed since its previous version, its highlights (samples/models.json)."""
    blocks = []
    for st in stats:
        m = db.get(st["model_id"])
        if not m:
            continue
        blocks.append(("h", m.get("name") or st["model"]))
        facts = [(k, m[f]) for k, f in (("厂商", "vendor"), ("发布", "released"), ("权重与许可", "weights"), ("架构", "architecture"),
                                         ("价格", "price"), ("本次调用", "access")) if m.get(f)]
        blocks.append(table(["项目", "内容"], [[k, v] for k, v in facts], "ll", tex_spec=r"@{}p{2.2cm}>{\raggedright\arraybackslash}p{13.6cm}@{}"))
        if m.get("updates"):
            blocks += ["相较上一版的更新：", ("ul", m["updates"])]
        if m.get("highlights"):
            blocks += ["亮点：", ("ul", m["highlights"])]
        if m.get("sources"):
            blocks.append(("links", m["sources"]))
    if not blocks:
        return []
    return [("模型简介", ["各模型的发布信息、相较上一版的更新与亮点，整理自厂商公告与模型卡；标注“厂商自报”的分数未经独立复现，"
                        "与本报告的测评结果不是同一口径。"] + blocks)]


def sign_test(wins, losses):
    """Two-sided exact sign test: the chance of a split at least this uneven between wins and losses if both models
    were equally good (ties left out)."""
    n = wins + losses
    if not n:
        return None
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / 2 ** n)


def f_p(p):
    return "–" if p is None else "< 0.001" if p < 0.001 else f"{p:.3f}"


def f_d(x, nd=1):
    """A difference, signed."""
    return "–" if x is None else f"{x:+.{nd}f}"


# ---------------------------------------------------------------- tokens and cost of API calls

def tokens(u):
    """(prompt, cache hit, completion, reasoning) from DeepSeek- or OpenAI/Kimi-style usage."""
    u = u or {}
    hit = u.get("prompt_cache_hit_tokens")
    if hit is None:
        hit = (u.get("prompt_tokens_details") or {}).get("cached_tokens") or u.get("cached_tokens") or 0
    reason = (u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
    return u.get("prompt_tokens") or 0, hit, u.get("completion_tokens") or 0, reason


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def is_peak(t, hours):
    d = datetime.datetime.fromtimestamp(t, datetime.timezone.utc)
    return d.weekday() < 5 and any(a <= d.hour < b for a, b in hours)


def call_cost(c, prices):
    """Cost of one call; prices = {"in", "hit", "out"[, "off": {"in", "hit", "out"}, "peak_hours": [(a, b)]]}."""
    p = prices if "off" not in prices or is_peak(c["start"], prices["peak_hours"]) else prices["off"]
    t = tokens(c.get("usage"))
    return ((t[0] - t[1]) * p["in"] + t[1] * p["hit"] + t[2] * p["out"]) / 1e6


def fmt_tok(n):
    return f"{n / 1e6:.2f}M" if n >= 1e6 else f"{n / 1e3:.1f}k"


def stats(v):
    return {"n": len(v), "mean": statistics.mean(v), "median": statistics.median(v), "p90": pct(v, 90), "max": max(v)} \
        if v else None


# ---------------------------------------------------------------- Markdown

def _flat_head(t):
    """Markdown has no grouped headers: "得分 ↑" over a model name becomes "得分 <model> ↑"; a group without a label
    leaves its columns as they are."""
    labels = []
    for label, span in t["groups"] or [("", len(t["head"]))]:
        labels += [label] * span
    out = []
    for g, h in zip(labels, t["head"]):
        if not g:
            out.append(h)
        else:
            arrow = g[-1] if g[-1] in "↑↓" else ""
            out.append(f"{g.rstrip(' ↑↓')} {h}" + (f" {arrow}" if arrow and arrow not in h else ""))
    return out


def md_table(t):
    head = _flat_head(t)
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "|".join("---:" if a == "r" else "---" for a in t["align"]) + "|"]
                     + ["| " + " | ".join(r) + " |" for r in t["rows"]])


def md_block(b):
    if isinstance(b, dict):
        return md_table(b)
    if isinstance(b, tuple):
        kind, x = b
        if kind == "fig":
            if x["file"] in FIGS:
                return f"![{x['caption']}]({x['file']}.png)\n\n{x['caption']}"
            return md_table(x["table"]) if x["table"] else ""
        if kind == "h":
            return f"### {x}"
        if kind == "ul":
            return "\n".join(f"- {i}" for i in x)
        if kind == "links":
            return "资料来源：" + "；".join(f"[{t}]({u})" for t, u in x)
    return b


# ---------------------------------------------------------------- LaTeX (xelatex + ctex)

PREAMBLE = r"""\documentclass[11pt,a4paper,fontset=none]{ctexart}
\usepackage[margin=2.2cm]{geometry}
\usepackage{fontspec}
\newcommand{\WinFonts}{/mnt/c/Windows/Fonts/}
\IfFontExistsTF{Times New Roman}{\setmainfont{Times New Roman}\setsansfont{Times New Roman}}{%
  \IfFileExists{\WinFonts times.ttf}{\setmainfont{times.ttf}[Path=\WinFonts, BoldFont=timesbd.ttf, ItalicFont=timesi.ttf]%
    \setsansfont{times.ttf}[Path=\WinFonts, BoldFont=timesbd.ttf]}{\setmainfont{TeX Gyre Termes}\setsansfont{TeX Gyre Termes}}}
\newcommand{\KaiPath}{/System/Library/AssetsV2/com_apple_MobileAsset_Font8/88d6cc32a907955efa1d014207889413890573be.asset/AssetData/}
\IfFileExists{\KaiPath Kaiti.ttc}{%
  \setCJKmainfont{Kaiti.ttc}[Path=\KaiPath, FontIndex=0, BoldFont=Kaiti.ttc, BoldFeatures={FontIndex=3}]
  \setCJKsansfont{Kaiti.ttc}[Path=\KaiPath, FontIndex=0, BoldFont=Kaiti.ttc, BoldFeatures={FontIndex=3}]
  \setCJKmonofont{Kaiti.ttc}[Path=\KaiPath, FontIndex=0]}{%
  \IfFontExistsTF{Kaiti SC}{\setCJKmainfont{Kaiti SC}\setCJKsansfont{Kaiti SC}\setCJKmonofont{Kaiti SC}}{%
  \IfFileExists{\WinFonts simkai.ttf}{\setCJKmainfont{simkai.ttf}[Path=\WinFonts, AutoFakeBold=2.5]\setCJKsansfont{simkai.ttf}[Path=\WinFonts, AutoFakeBold=2.5]%
    \setCJKmonofont{simkai.ttf}[Path=\WinFonts]}{%
  \setCJKmainfont{FandolKai-Regular.otf}[AutoFakeBold=2.5]\setCJKsansfont{FandolKai-Regular.otf}[AutoFakeBold=2.5]%
  \setCJKmonofont{FandolKai-Regular.otf}}}}% by file name: TeX Live's own fonts are not known to fontconfig on Linux
\usepackage{amsmath}
\usepackage{booktabs,tabularx,longtable,array,graphicx,float}
\usepackage{enumitem}
\usepackage{xurl}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\setlist{nosep,leftmargin=1.4em}
\ctexset{section={format=\Large\bfseries\raggedright},subsection={format=\large\bfseries\raggedright}}
\setlength{\parskip}{0.3em}
\renewcommand{\arraystretch}{1.15}
\pagestyle{fancy}\fancyhf{}
\lhead{\small BAI AI Lab mmBench 多模态评测}\rhead{\small __DATE__}\cfoot{\small\thepage}
\renewcommand{\headrulewidth}{0.4pt}
"""


def tex_table(t):
    groups = ""
    if t["groups"]:
        cells, rules, col = [], [], 1
        for label, span in t["groups"]:
            if label:
                cells.append(rf"\multicolumn{{{span}}}{{c}}{{{tex(label)}}}")
                rules.append(rf"\cmidrule(lr){{{col}-{col + span - 1}}}")
            else:
                cells += [""] * span
            col += span
        groups = " & ".join(cells) + r" \\ " + " ".join(rules) + "\n"
    head = groups + " & ".join(tex(h) for h in t["head"]) + r" \\"
    rows = [" & ".join(tex(c) for c in r) + r" \\" for r in t["rows"]]
    return "\n".join([r"\begin{center}\small", r"\resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{%",
                      r"\begin{tabular}{" + (t["tex_spec"] or t["align"]) + "}", r"\toprule", head, r"\midrule"] + rows
                     + [r"\bottomrule", r"\end{tabular}}", r"\end{center}"])


def tex_url(u):
    return u.replace("%", r"\%").replace("#", r"\#")


def tex_block(b):
    if isinstance(b, dict):
        return tex_table(b)
    if isinstance(b, tuple):
        kind, x = b
        if kind == "fig":
            if x["file"] in FIGS:
                return "\n".join([r"\begin{figure}[H]\centering", rf"\includegraphics[width={x.get('width', 1.0):g}\linewidth]{{{x['file']}.pdf}}",
                                  rf"\caption{{{tex(x['caption'])}}}", r"\end{figure}"])
            return tex_table(x["table"]) if x["table"] else ""
        if kind == "h":
            return rf"\subsection*{{{tex(x)}}}"
        if kind == "ul":
            return "\n".join([r"\begin{itemize}"] + [rf"\item {tex(i)}" for i in x] + [r"\end{itemize}"])
        if kind == "links":
            return r"{\small 资料来源：" + "；".join(rf"\href{{{tex_url(u)}}}{{{tex(t)}}}" for t, u in x) + "}"
    return tex(b)
