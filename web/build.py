#!/usr/bin/env python3
"""Build the static results site (docs/, served by GitHub Pages) from the technical report's data.

Reads paper/paper_data.json (items and every sample's score), paper/analysis.json (all aggregate numbers) and
samples/models.json, so the site shows exactly the report's numbers; before writing it recomputes the capability,
overall, tier and solved-by numbers from the per-item scores and stops if they disagree. No question text or
images are published (several sources allow academic use only): only item ids, metadata and scores, with a link
to each item's row on Hugging Face.

Usage: python web/build.py [--out docs]
"""
import argparse
import html
import json
import math
import os
import shutil
import statistics
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA_DATE = "2026-10-31"
CREATED = "2026-11-01"
AUTHOR = "Albert Huang"
AUTHOR_URL = "https://alberthx86.github.io/"
REPO_URL = "https://github.com/BAI-AI-Lab/mmBench"
CODE_SITE = "https://bai-ai-lab.github.io/coding-eval/"
PDF = f"report-{DATA_DATE}.pdf"

CAP_ZH = {"reasoning": "学科推理", "perception": "视觉感知", "charts": "图表", "documents": "文档",
          "spatial": "空间", "gui": "界面定位", "video": "视频时序"}
TIER_ZH = {"L1": "基础", "L2": "中等", "L3": "困难"}
TYPE_ZH = {"mcq": "选择", "yesno": "是非", "exact": "文字短答", "number": "数值短答", "anls": "文档短答",
           "point_in_box": "坐标"}
CLS = {"kimi-k3.1-pro": "kimi", "MiniMax-M3.1-Flash": "minimax", "deepseek-flash": "deepseek"}
SHORT = {"kimi-k3.1-pro": "Kimi", "MiniMax-M3.1-Flash": "MiniMax", "deepseek-flash": "DeepSeek"}

# the source benchmarks: display name, Hugging Face repo, venue, arXiv id, what the questions ask (paraphrased)
SOURCES = {
    "mmmu_pro": ("MMMU-Pro 标准版", "MMMU/MMMU_Pro", "ACL 2025", "2409.02813",
                 "大学学科题（理、工、医、商、人文等），看图作答，10 选 1"),
    "blink": ("BLINK", "BLINK-Benchmark/BLINK", "ECCV 2024", "2404.12390", "低层视觉感知的 9 个子任务"),
    "chartqa": ("ChartQA", "HuggingFaceM4/ChartQA", "ACL 2022 Findings", "2203.10244",
                "从统计图上读数或做简单比较，答一个词或数"),
    "charxiv": ("CharXiv 推理题", "princeton-nlp/CharXiv", "NeurIPS 2024", "2406.18521",
                "科研论文图表上的推理：比较、趋势、读数，答文字或数值"),
    "docvqa": ("DocVQA", "lmms-lab-encoder/DocVQA", "WACV 2021", "2007.00398",
               "扫描文档（表单、信件、报表）上的问答，答案是文档里的文字"),
    "ocrbench_kie": ("OCRBench 关键信息抽取", "echo840/OCRBench", "SCIS 2024", "2305.07895",
                     "从收据、商品标签、表单中抽取指定字段的值"),
    "cvbench_3d": ("CV-Bench 3D", "nyu-visionx/CV-Bench", "NeurIPS 2024", "2406.16860",
                   "两个物体哪个离相机更近，或哪个离参照物更近"),
    "blink_spatial": ("BLINK 空间子任务", "BLINK-Benchmark/BLINK", "ECCV 2024", "2404.12390", "深度、方位、多视角、定位"),
    "mindcube": ("MindCube", "oscarqjh/MindCube_lmmseval", "arXiv 2025", "2506.21458",
                 "只看场景的少数几个视角，推断换位或转向后的物体方位"),
    "screenspot_v2": ("ScreenSpot-v2", "lmms-lab/ScreenSpot-v2", "arXiv 2024", "2410.23218",
                      "在手机、网页、桌面截图上找到指定图标，给出点击坐标"),
    "screenspot_pro": ("ScreenSpot-Pro", "likaixin/ScreenSpot-Pro", "ACM MM 2025", "2504.07981",
                       "在专业软件的高分辨率截图上找到指定图标，给出点击坐标"),
    "timeblind": ("TimeBlind", "BaiqiL/TimeBlind", "EMNLP 2026", "2602.00288",
                  "看按时间排列的 16 帧，回答单看一帧答不出的时序问题"),
}
# sub-tasks named in the item id (BLINK config, TimeBlind split): short name, what the question asks
SUBTASKS = {
    "Art_Style": ("画风", "给一张参考画，在两张候选中选出画风相同的一张"),
    "Counting": ("计数", "数出图中指定物体的个数"),
    "Forensic_Detection": ("伪造检测", "在几张图中找出真实拍摄的照片"),
    "Functional_Correspondence": ("功能对应", "在另一物体上找出与参考点功能相同的位置"),
    "Jigsaw": ("拼图", "选出能补上图中缺块的拼图块"),
    "Relative_Reflectance": ("反射率", "比较两个标记点所在表面的反射率（颜色深浅）"),
    "Semantic_Correspondence": ("语义对应", "在第二张图中找到与参考点语义相同的部位"),
    "Visual_Correspondence": ("视觉对应", "在另一视角的图中找到同一个物理点"),
    "Visual_Similarity": ("相似度", "在两张候选中选出与参考图更相似的一张"),
    "Multi-view_Reasoning": ("多视角", "由同一场景的两个视角判断相机往哪边移动"),
    "Object_Localization": ("定位", "在两个候选框中选出正确框住指定物体的一个"),
    "Relative_Depth": ("相对深度", "两个标记点哪一个离相机更近"),
    "Spatial_Relation": ("方位", "判断对两个物体方位关系的描述是否正确"),
    "yes_no": ("是非", "判断一条时序描述是否成立"),
    "multiple_choice": ("二选一", "从两条时序描述中选出正确的一条"),
}
N_DATASETS = len({v[1] for v in SOURCES.values()})  # BLINK serves two capabilities
CONFIG_ORIG = {"mmmu_pro": "standard (10 options)"}  # item ids replace spaces with "_"
HUB_FILES = {"screenspot_pro", "timeblind"}           # read from Hub files, not datasets-server rows: no row link

# capability definitions (technical report, table 1)
CAP_DEF = {
    "reasoning": ("结合学科知识的看图推理", "图片为表格、统计图或截图的题；题目印在图片里的版本"),
    "perception": ("计数、对应点、相似度、反射率、伪造检测、拼图、画风", "深度、方位、多视角、定位子任务（归入空间）；IQ 测试"),
    "charts": ("读取数值、比较与趋势", "—"),
    "documents": ("表单、版面、表格、收据等密集文字", "针对插图或照片的问题；信息图；OCRBench 的文档问答子集"),
    "spatial": ("深度、距离、方位与多视角心理建模", "以坐标作答的指点题"),
    "gui": ("在截图上找到要点击的图标", "文字目标"),
    "video": ("单看一帧无法回答的时序问题", "依赖专业知识的视频题"),
}
# vendor-reported scores (technical report, table 6; sources in the report)
OFFICIAL = [
    ("MMMU-Pro 标准版", "cap:reasoning", "本站排除表格、统计图与截图题，50 题",
     {"kimi-k3.1-pro": "84.1", "MiniMax-M3.1-Flash": "78.1（前代 M3）", "deepseek-flash": "80.6（Kimi 博客中的对比值）"}),
    ("CharXiv 推理题", "src:charxiv", "本站 35 题、规则评分；厂商用模型裁判",
     {"kimi-k3.1-pro": "89.0", "MiniMax-M3.1-Flash": "82.5（GPT-5.5 裁判）", "deepseek-flash": "77.0（Kimi 博客中的对比值）"}),
    ("DocVQA", "src:docvqa", "本站为接口模型、ANLS", {"deepseek-flash": "95.6（基座，4-shot，模型裁判）"}),
    ("CV-Bench", "src:cvbench_3d", "本站只用 3D 子集，14 题", {"deepseek-flash": "77.9（基座，4-shot，全集）"}),
]

esc = html.escape


def f1(x):
    return f"{x:.1f}"


def signed(x):
    return "0.0" if abs(x) < 0.05 else f"{x:+.1f}"


def ci(lo, hi):
    return f"{lo:.1f}–{hi:.1f}"


def sci(lo, hi):
    return f"{signed(lo)} 至 {signed(hi)}"


def sign_p(w, losses):
    """Exact two-sided sign test on the items one model did better and worse on."""
    n, k = w + losses, min(w, losses)
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def fmt_p(p):
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def split_id(iid):
    src, config, split, off = iid.split("/")
    return src, config, split, off


def subtask(iid):
    src, config, split, _ = split_id(iid)
    if src in ("blink", "blink_spatial"):
        return config
    if src == "timeblind":
        return split
    return None


def item_label(iid):
    src = split_id(iid)[0]
    st = subtask(iid)
    return SOURCES[src][0] + (" · " + SUBTASKS[st][0] if st else "")


def item_url(iid):
    src, config, split, off = split_id(iid)
    hf = SOURCES[src][1]
    if src in HUB_FILES:
        return f"https://huggingface.co/datasets/{hf}"
    config = CONFIG_ORIG.get(src, config)
    q = urllib.parse.quote
    return f"https://huggingface.co/datasets/{hf}/viewer/{q(config, safe='')}/{q(split, safe='')}?row={off}"


class Data:
    def __init__(self):
        p = json.load(open(os.path.join(ROOT, "paper", "paper_data.json"), encoding="utf-8"))
        self.a = json.load(open(os.path.join(ROOT, "paper", "analysis.json"), encoding="utf-8"))
        self.notes = json.load(open(os.path.join(ROOT, "samples", "models.json"), encoding="utf-8"))
        self.items = p["items"]
        self.runs = p["runs"]
        self.version = p["version"]
        a = self.a
        self.models, self.caps, self.names = a["models"], a["caps"], a["names"]
        ids = list(self.items)
        for m in self.models:
            assert set(self.runs[m]["scores"]) == set(ids), m
        self.mean = {m: {i: statistics.mean(self.runs[m]["scores"][i]) for i in ids} for m in self.models}
        order = {s: n for n, s in enumerate(SOURCES)}
        self.ids = sorted(ids, key=lambda i: (self.caps.index(self.items[i]["cap"]), order[self.items[i]["source"]],
                                              subtask(i) or "", int(split_id(i)[3])))
        self.check()
        self.rank = {m: 1 + sum(self.clearly_better(o, m) for o in self.models if o != m) for m in self.models}

    def group_score(self, m, pred):
        xs = [self.mean[m][i] for i in self.ids if pred(self.items[i])]
        return 100 * statistics.mean(xs)

    def src_score(self, m, src):
        return self.group_score(m, lambda it: it["source"] == src)

    def solved(self, i):
        return sum(self.mean[m][i] >= 0.5 for m in self.models)

    def pair(self, x, y):
        """(diff, ci, key order sign) for x minus y, from analysis.json's pairs."""
        k = f"{x}|{y}"
        if k in self.a["pairs"]:
            return self.a["pairs"][k], 1
        return self.a["pairs"][f"{y}|{x}"], -1

    def clearly_better(self, x, y):
        d, s = self.pair(x, y)
        lo, hi = (s * v for v in d["overall"]["ci"])
        return min(lo, hi) > 0

    def wtl(self, x, y):
        w = sum(self.mean[x][i] > self.mean[y][i] + 1e-9 for i in self.ids)
        loss = sum(self.mean[y][i] > self.mean[x][i] + 1e-9 for i in self.ids)
        return w, len(self.ids) - w - loss, loss

    def check(self):
        """The site's per-item view must reproduce the report's aggregates."""
        a = self.a
        for m in self.models:
            caps = {c: self.group_score(m, lambda it, c=c: it["cap"] == c) for c in self.caps}
            for c in self.caps:
                assert abs(caps[c] - a["cap"][m][c]) < 0.05, (m, c, caps[c], a["cap"][m][c])
            assert abs(statistics.mean(caps.values()) - a["overall"][m]) < 0.05, m
            for t, v in a["tier"][m].items():
                assert abs(self.group_score(m, lambda it, t=t: it["tier"] == t) - v) < 0.05, (m, t)
        for c in self.caps:
            got = [0, 0, 0, 0]
            for i in self.ids:
                if self.items[i]["cap"] == c:
                    got[self.solved(i)] += 1
            assert got == a["solved_by"][c], (c, got, a["solved_by"][c])
        for t, n in a["tier_n"].items():
            assert sum(self.items[i]["tier"] == t for i in self.ids) == n, t


# ---------------------------------------------------------------- page frame

NAV = [("index.html", "概览"), ("results.html", "结果"), ("bench.html", "评测集"), ("questions.html", "题目"),
       (PDF, "报告")]


def page(name, title, desc, body):
    nav = "".join(f'<li><a href="{h}"{" aria-current=page" if h == name else ""}>{t}</a></li>' for h, t in NAV)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="icon" href="assets/icon.svg" type="image/svg+xml">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<nav class="nav"><div class="nav-in"><a class="brand" href="index.html"><span class="hide-sm">BAI AI Lab </span>多模态评测</a><ul>{nav}</ul></div></nav>
<main>
{body}
</main>
<footer><div class="wrap">
<p>BAI AI Lab 多模态评测 mmBench · 数据截至 {DATA_DATE}</p>
<p>题目抽自 {N_DATASETS} 个公开评测集，题面与图片版权归原作者，本站只列题号、题型与得分。评测代码：<a href="{REPO_URL}">BAI-AI-Lab/mmBench</a>；全部数据：<a href="data/mmbench.json">data/mmbench.json</a>。另见 <a href="{CODE_SITE}">代码能力评测</a>。</p>
<p>由 <a href="{AUTHOR_URL}" target="_blank" rel="noopener">{AUTHOR}</a> 创建于 {CREATED}</p>
</div></footer>
<script src="assets/app.js"></script>
</body>
</html>
"""


def model_head(d, m, tag="th"):
    return f'<{tag} class="n"><span class="dot {CLS[m]}"></span> {esc(SHORT[m])} ↑</{tag}>'


def bars(d, groups):
    """groups: [(title, note, {model: score}, chance, extra_class)] as HTML bars on a 0-100 track."""
    out = []
    for title, note, scores, chance, extra in groups:
        rows = []
        for m in d.models:
            v = scores[m]
            mark = f'<span class="chance" style="left:{chance:.1f}%"></span>' if chance is not None else ""
            rows.append(f'<div class="brow"><span>{esc(SHORT[m])}</span><span class="track">'
                        f'<span class="fill {CLS[m]}-bg" style="width:{v:.1f}%"></span>{mark}</span>'
                        f'<span class="bval">{f1(v)}</span></div>')
        out.append(f'<div class="bgrp {extra}"><h4>{esc(title)}<span>{esc(note)}</span></h4>{"".join(rows)}</div>')
    return f'<div class="bars">{"".join(out)}</div>'


def legend(d, chance=True):
    li = "".join(f'<li><i class="{CLS[m]}-bg"></i>{esc(d.names[m])}</li>' for m in d.models)
    if chance:
        li += '<li><span class="chance-key"></span>随机猜测</li>'
    return f'<ul class="legend">{li}</ul>'


def table(head, rows):
    return (f'<div class="tw"><table><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def best_of(vals):
    top = max(vals)
    return [abs(v - top) < 1e-9 for v in vals]


def cap_items(d, c):
    return sum(d.items[i]["cap"] == c for i in d.ids)


# ---------------------------------------------------------------- pages

def index(d):
    a = d.a
    cards = []
    for m in d.models:
        caps = a["cap"][m]
        hi = max(d.caps, key=lambda c: caps[c])
        lo = min(d.caps, key=lambda c: caps[c])
        cost, tok, sp = a["cost"][m], a["tokens"][m], a["speed"][m]
        lo_ci, hi_ci = a["overall_ci"][m]
        specs = [
            (f"{CAP_ZH[hi]} {f1(caps[hi])}", "最强能力 · 得分 ↑"),
            (f"{CAP_ZH[lo]} {f1(caps[lo])}", "最弱能力 · 得分 ↑"),
            (f"¥{cost['cny']:.2f}", "全部 1,416 次调用费用 ↓"),
            (f"¥{cost['cny'] / len(d.ids):.3f}", "每题费用 ↓"),
            (f"{tok['latency_median']:.1f} 秒", "延迟中位数 ↓"),
            (f"{sp['gen_median']:.0f}", "生成速度 token/秒 ↑"),
        ]
        li = "".join(f"<li><b>{esc(v)}</b><span>{esc(k)}</span></li>" for v, k in specs)
        short = SHORT[m]
        cards.append(f'<div class="model"><div><span class="dot {CLS[m]}"></span><h3><span class="long">{esc(d.names[m])}</span>'
                     f'<span class="short">{esc(short)}</span></h3><div class="id">{esc(m)}</div></div>'
                     f'<div class="big">{f1(a["overall"][m])}</div><div class="cap">总分 ↑ · 第 {d.rank[m]} 名<br>'
                     f'95% 区间 {ci(lo_ci, hi_ci)}</div><ul class="specs">{li}</ul></div>')
    rows = 3 + 6
    k, mm, ds = d.models
    p_km, s_km = d.pair(k, mm)
    p_kd, s_kd = d.pair(k, ds)
    p_md, s_md = d.pair(mm, ds)
    g = a["cap"]
    gui_gap = max(g[m]["gui"] for m in d.models) - min(g[m]["gui"] for m in d.models)
    src = {m: {s: d.src_score(m, s) for s in ("screenspot_pro", "mindcube")} for m in d.models}
    cheap = min(d.models, key=lambda m: a["cost"][m]["cny"])
    lead_all = all(g[k][c] >= max(g[m][c] for m in d.models) for c in d.caps)
    assert lead_all and cheap == mm, "the highlight text below assumes these"
    tiles = f"""
<a class="card" href="results.html#rank"><p class="k">排名</p><p class="v">{signed(s_km * p_km['overall']['diff'])} 分</p>
<p>{esc(d.names[k])} 总分 {f1(a['overall'][k])}，比 {esc(d.names[mm])} 高 {f1(s_km * p_km['overall']['diff'])} 分（区间 {sci(*sorted(s_km * x for x in p_km['overall']['ci']))}），比 {esc(d.names[ds])} 高 {f1(s_kd * p_kd['overall']['diff'])} 分。后两者相差 {f1(abs(p_md['overall']['diff']))} 分，区间含 0，并列第 2。</p></a>
<a class="card" href="results.html#source"><p class="k">差距最大：界面定位</p><p class="v">{f1(gui_gap)} 分</p>
<p>Kimi {f1(g[k]['gui'])}、MiniMax {f1(g[mm]['gui'])}、DeepSeek {f1(g[ds]['gui'])}。在专业软件截图 ScreenSpot-Pro 上分别为 {f1(src[k]['screenspot_pro'])}、{f1(src[mm]['screenspot_pro'])}、{f1(src[ds]['screenspot_pro'])}。</p></a>
<a class="card" href="results.html#profile"><p class="k">空间</p><p class="v">{f1(g[k]['spatial'])}</p>
<p>Kimi 的最强项。只看少数视角推断方位的 MindCube 上，Kimi {f1(src[k]['mindcube'])}、DeepSeek {f1(src[ds]['mindcube'])}、MiniMax {f1(src[mm]['mindcube'])}。</p></a>
<a class="card" href="results.html#cost"><p class="k">费用</p><p class="v">¥{a['cost'][mm]['cny'] / len(d.ids):.3f} / 题</p>
<p>{esc(d.names[mm])} 最便宜，全部调用 ¥{a['cost'][mm]['cny']:.2f}；DeepSeek ¥{a['cost'][ds]['cny']:.2f}，Kimi ¥{a['cost'][k]['cny']:.2f}（约 {a['cost'][k]['cny'] / a['cost'][mm]['cny']:.0f} 倍）。</p></a>
<div class="card wide"><p class="k">选型</p>
<p>要准确率选 {esc(d.names[k])}：7 项能力得分都最高，但费用最高、生成最慢（{a['speed'][k]['gen_median']:.0f} token/秒）。要成本选 {esc(d.names[mm])}：与 DeepSeek 并列第 2，费用约为其一半，生成 {a['speed'][mm]['gen_median']:.0f} token/秒。{esc(d.names[ds])} 的空间与视觉感知强于 MiniMax，但界面定位只有 {f1(g[ds]['gui'])}。</p></div>"""
    groups = [(CAP_ZH[c], f"{cap_items(d, c)} 题", {m: g[m][c] for m in d.models}, a["chance"][c], "") for c in d.caps]
    body = f"""<section class="hero"><div class="wrap">
<p class="eyebrow">mmBench · {DATA_DATE}</p>
<h1>多模态评测</h1>
<p class="lead"><span class="nw">Kimi K3.1 Pro</span>、<span class="nw">MiniMax M3.1 Flash</span>、<span class="nw">DeepSeek Flash V4.1-1017</span>：<span class="nw">7 项能力，354 道题，</span><span class="nw">每题作答 4 次。</span></p>
<div class="ctas"><a class="btn" href="results.html">查看结果</a><a class="more" href="questions.html">逐题结果</a><a class="more" href="{PDF}">下载技术报告（PDF）</a></div>
</div></section>
<section class="section alt"><div class="wrap">
<h2>三个模型</h2>
<p class="sub">总分是 7 项能力的等权平均（0–100）。两两总分差的 95% 区间不含 0 才算分出高下，名次相同表示差距在误差内。</p>
<div class="compare" style="--rows:{rows}">{"".join(cards)}</div>
<p class="note">↑ 越大越好，↓ 越小越好。费用按各厂商国内站标价与实际 token 计算；延迟、生成速度为每次调用的中位数，生成速度从首个 token 起算。</p>
</div></section>
<section class="section"><div class="wrap">
<h2>能力画像</h2>
<p class="sub">每项能力只考一种技能、只用一种答题形式。竖线是随机猜测的期望得分。</p>
{legend(d)}
{bars(d, groups)}
<p class="note">得分 ↑ 越大越好。区间与两两差见 <a href="results.html#profile">结果</a>。</p>
</div></section>
<section class="section alt"><div class="wrap">
<h2>要点</h2>
<p class="sub">数字均来自本次评测记录，计算方法见“评测集”。</p>
<div class="tiles">{tiles}
</div>
</div></section>"""
    return page("index.html", "多模态评测 · BAI AI Lab",
                "Kimi K3.1 Pro、MiniMax M3.1 Flash、DeepSeek Flash V4.1-1017 在 mmBench 7 项能力上的评测结果", body)


def results(d):
    a = d.a
    M = d.models
    heads = "".join(model_head(d, m) for m in M)

    # profile
    rows = []
    for c in d.caps + ["overall"]:
        if c == "overall":
            vals, cis = [a["overall"][m] for m in M], [a["overall_ci"][m] for m in M]
            name, n, ch = "总分（等权）", len(d.ids), a["chance_overall"]
        else:
            vals, cis = [a["cap"][m][c] for m in M], [a["cap_ci"][m][c] for m in M]
            name, n, ch = CAP_ZH[c], cap_items(d, c), a["chance"][c]
        b = best_of(vals)
        cells = "".join(f'<td class="n{" best" if bb else ""}">{f1(v)}<span class="ci">{ci(*x)}</span></td>'
                        for v, x, bb in zip(vals, cis, b))
        rows.append(f'<tr{" class=grp" if c == d.caps[-1] else ""}><td>{name}</td><td class="n">{n}</td><td class="n">{f1(ch)}</td>{cells}</tr>')
    profile = table(f'<th>能力</th><th class="n">题数</th><th class="n">随机猜测</th>{heads}', rows)

    # ranking
    rk = sorted(M, key=lambda m: (d.rank[m], -a["overall"][m]))
    rrows = [f'<tr><td>{d.rank[m]}</td><td><span class="dot {CLS[m]}"></span> {esc(d.names[m])}</td>'
             f'<td class="n">{f1(a["overall"][m])}</td><td class="n">{ci(*a["overall_ci"][m])}</td></tr>' for m in rk]
    ranking = table('<th>名次</th><th>模型</th><th class="n">总分 ↑</th><th class="n">95% 区间</th>', rrows)
    pairs = [(M[0], M[1]), (M[0], M[2]), (M[1], M[2])]
    prows = []
    for x, y in pairs:
        p, s = d.pair(x, y)
        w, t, loss = d.wtl(x, y)
        lo, hi = sorted(s * v for v in p["overall"]["ci"])
        prows.append(f'<tr><td>{esc(SHORT[x])} − {esc(SHORT[y])}</td><td class="n">{signed(s * p["overall"]["diff"])}</td>'
                     f'<td class="n">{sci(lo, hi)}</td><td class="n">{w}</td><td class="n">{t}</td><td class="n">{loss}</td>'
                     f'<td class="n">{esc(fmt_p(sign_p(w, loss)))}</td></tr>')
    pairwise = table('<th>比较</th><th class="n">总分差</th><th class="n">95% 区间</th><th class="n">更好</th>'
                     '<th class="n">相同</th><th class="n">更差</th><th class="n">符号检验 p</th>', prows)
    crows = []
    for c in d.caps:
        cells = []
        for x, y in pairs:
            p, s = d.pair(x, y)
            lo, hi = sorted(s * v for v in p[c]["ci"])
            sig = lo > 0 or hi < 0
            cells.append(f'<td class="n{" best" if sig else ""}">{signed(s * p[c]["diff"])}<span class="ci">{sci(lo, hi)}</span></td>')
        crows.append(f'<tr><td>{CAP_ZH[c]}</td>{"".join(cells)}</tr>')
    pair_caps = table("<th>能力</th>" + "".join(f'<th class="n">{esc(SHORT[x])} − {esc(SHORT[y])}</th>' for x, y in pairs), crows)

    # tiers
    trows = []
    for t in ("L1", "L2", "L3"):
        vals = [a["tier"][m][t] for m in M]
        b = best_of(vals)
        trows.append(f'<tr><td>{t} {TIER_ZH[t]}</td><td class="n">{a["tier_n"][t]}</td>'
                     + "".join(f'<td class="n{" best" if bb else ""}">{f1(v)}</td>' for v, bb in zip(vals, b)) + "</tr>")
    tiers = table(f'<th>难度</th><th class="n">题数</th>{heads}', trows)

    # sources
    srows = []
    for c in d.caps:
        first = True
        for s in SOURCES:
            its = [i for i in d.ids if d.items[i]["source"] == s and d.items[i]["cap"] == c]
            if not its:
                continue
            tiers_s = sorted({d.items[i]["tier"] for i in its})
            vals = [d.src_score(m, s) for m in M]
            b = best_of(vals)
            srows.append(f'<tr><td>{CAP_ZH[c] if first else ""}</td><td>{esc(SOURCES[s][0])}</td>'
                         f'<td>{"/".join(tiers_s)}</td><td class="n">{len(its)}</td>'
                         + "".join(f'<td class="n{" best" if bb else ""}">{f1(v)}</td>' for v, bb in zip(vals, b)) + "</tr>")
            first = False
        srows[-1] = srows[-1].replace("<tr>", "<tr class=grp>", 1) if c != d.caps[-1] else srows[-1]
    sources = table(f'<th>能力</th><th>来源</th><th>难度</th><th class="n">题数</th>{heads}', srows)

    # sampling
    smp = a["sampling"]
    sm_rows = [f'<tr><td><span class="dot {CLS[m]}"></span> {esc(d.names[m])}</td><td class="n">{f1(smp[m]["avg@4"])}</td>'
               f'<td class="n">{f1(smp[m]["pass@4"])}</td><td class="n">{f1(smp[m]["all@4"])}</td>'
               f'<td class="n">{smp[m]["mixed_items"]}（{smp[m]["mixed_share"]:.0f}%）</td></tr>' for m in M]
    sampling = table('<th>模型</th><th class="n">avg@4 ↑</th><th class="n">pass@4 ↑</th><th class="n">all@4 ↑</th>'
                     '<th class="n">4 次结果不一的题 ↓</th>', sm_rows)

    # cost and speed
    co_rows = []
    for m in M:
        tk, sp, co = a["tokens"][m], a["speed"][m], a["cost"][m]
        co_rows.append(f'<tr><td><span class="dot {CLS[m]}"></span> {esc(d.names[m])}</td>'
                       f'<td class="n">{tk["in"]:,.0f}</td><td class="n">{tk["hit"]:,.0f}</td>'
                       f'<td class="n">{tk["out"]:,.0f}（{tk["out_median"]:,.0f}）</td>'
                       f'<td class="n">{100 * tk["reasoning"] / tk["out"]:.1f}%</td>'
                       f'<td class="n">{tk["latency_median"]:.1f}</td><td class="n">{sp["ttft_median"]:.1f}</td>'
                       f'<td class="n">{sp["gen_median"]:.0f}</td><td class="n">{co["cny"]:.2f}</td>'
                       f'<td class="n">{co["cny"] / len(d.ids):.3f}</td><td class="n">${co["usd"]:.2f}</td></tr>')
    cost = table('<th>模型</th><th class="n">输入 token</th><th class="n">其中缓存</th><th class="n">输出 token（中位数）</th>'
                 '<th class="n">思考占比</th><th class="n">延迟 秒 ↓</th><th class="n">首 token 秒 ↓</th>'
                 '<th class="n">生成 token/秒 ↑</th><th class="n">费用 元 ↓</th><th class="n">元 / 题 ↓</th>'
                 '<th class="n">美元参考 ↓</th>', co_rows)
    tc_rows = [f'<tr><td>{CAP_ZH[c]}</td>' + "".join(f'<td class="n">{a["tokens"][m]["cap_out"][c]:,.0f}</td>' for m in M) + "</tr>"
               for c in d.caps]
    tok_caps = table("<th>能力</th>" + "".join(f'<th class="n"><span class="dot {CLS[m]}"></span> {esc(SHORT[m])}</th>' for m in M), tc_rows)

    # vendor-reported
    o_rows = []
    for bench, key, diffnote, vals in OFFICIAL:
        kind, name = key.split(":")
        first = True
        for m in M:
            if m not in vals:
                continue
            ours = a["cap"][m][name] if kind == "cap" else d.src_score(m, name)
            o_rows.append(f'<tr><td>{esc(bench) if first else ""}</td>'
                          f'<td><span class="dot {CLS[m]}"></span> {esc(SHORT[m])}</td><td>{esc(vals[m])}</td>'
                          f'<td class="n">{f1(ours)}</td><td class="sec">{esc(diffnote) if first else ""}</td></tr>')
            first = False
        if bench != OFFICIAL[-1][0]:
            o_rows[-1] = o_rows[-1].replace("<tr>", "<tr class=grp>", 1)
    official = table('<th>评测</th><th>模型</th><th>厂商自报</th><th class="n">本站子集 ↑</th><th>口径差异</th>', o_rows)

    co = a["cost"][M[2]]
    body = f"""<section class="hero"><div class="wrap">
<p class="eyebrow">354 题 × 4 次 · {DATA_DATE}</p>
<h1>结果</h1>
<p class="lead">能力得分、排名、难度、来源、作答稳定性、费用与速度。</p>
</div></section>
<section class="section alt" id="profile"><div class="wrap">
<h2>各项能力</h2>
<p class="sub">每题 4 次作答取平均，再按能力平均（0–100）。小字为 95% 区间（按题重抽样 2,000 次）。</p>
{profile}
<p class="note">↑ 越大越好；加粗为该行最高。随机猜测为逐题的期望得分，题数只描述规模。</p>
</div></section>
<section class="section" id="rank"><div class="wrap">
<h2>排名</h2>
<p class="sub">名次 = 1 + 明显强于它的模型数；总分差的 95% 区间包含 0 时名次相同。</p>
{ranking}
<h3>两两比较</h3>
{pairwise}
<p class="note">总分差为正表示前者更高，区间来自成对重抽样。更好 / 相同 / 更差为逐题比较的题数（每题 4 次的平均分），p 为精确符号检验。按这套题的题量，小于约 ±2.7 分的总分差分不出来。</p>
<h3>各项能力的两两差</h3>
{pair_caps}
<p class="note">加粗：95% 区间不含 0，即该项上差距明显。小字为区间。</p>
</div></section>
<section class="section alt" id="tier"><div class="wrap">
<h2>按难度</h2>
<p class="sub">所有能力合在一起按题平均。难度越高，Kimi 与另两个模型的差距越大。</p>
{tiers}
<p class="note">↑ 越大越好。难度按来源对当前模型是否已饱和划分，MMMU-Pro 用其自带的难度标签逐题分档。</p>
</div></section>
<section class="section" id="source"><div class="wrap">
<h2>按来源</h2>
<p class="sub">每个来源只抽了一部分题，不等于该评测集的完整成绩。</p>
{sources}
<p class="note">↑ 越大越好；加粗为该行最高。各来源的题目说明见 <a href="questions.html">题目</a>。</p>
</div></section>
<section class="section alt" id="sampling"><div class="wrap">
<h2>同一道题答 4 次</h2>
<p class="sub">avg@4 是本站使用的分数；pass@4 为 4 次中至少一次答对，all@4 为 4 次全对。</p>
{sampling}
<p class="note">↑ 越大越好，↓ 越小越好。“结果不一”指同一道题 4 次作答有对有错，越少说明单次结果越稳定。</p>
</div></section>
<section class="section" id="cost"><div class="wrap">
<h2>费用与速度</h2>
<p class="sub">每个模型 1,416 次调用（354 题 × 4 次）。token 为每次调用的平均值。</p>
{cost}
<p class="note">↑ 越大越好，↓ 越小越好；token 数只描述用量，不标方向。费用按各厂商国内站标价（元 / 百万 token）与实际 token 计算：Kimi 输入 13、缓存 1.30、输出 68；MiniMax 1 / 0.10 / 4；DeepSeek 非高峰 1 / 0.02 / 4。本次 DeepSeek 调用都在非高峰时段，按高峰价为 ¥{co['cny_peak']:.2f}。美元为参考价。</p>
<h3>各项能力的平均输出 token</h3>
{tok_caps}
<p class="note">每次调用的平均输出 token（含思考），只描述用量。</p>
</div></section>
<section class="section alt" id="official"><div class="wrap">
<h2>与厂商自报成绩对照</h2>
<p class="sub">口径不同，只作参考：本站是子集、规则评分；厂商成绩多用全集或模型裁判。</p>
{official}
<p class="note">↑ 越大越好。厂商自报的出处见技术报告。</p>
</div></section>"""
    return page("results.html", "结果 · 多模态评测", "mmBench 评测结果：能力得分、排名、难度、来源、稳定性、费用与速度", body)


def bench(d):
    a = d.a
    principles = [
        ("一项能力只考一种技能。", "会考到其他能力的题在抽题时排除。"),
        ("一项能力只用一类答题形式。", "坐标只用于界面定位，避免“不会按格式作答”同时拉低多项能力。"),
        ("所有模型答同一套题。", "题库由固定随机种子决定并以题号清单发布；视频按同一规则抽帧。"),
        ("只用确定的规则评分。", "不用模型裁判，同一份回答任何时候都得同一个分数。"),
    ]
    steps = "".join(f'<div class="card"><h4>{esc(h)}</h4><p>{esc(t)}</p></div>' for h, t in principles)

    rows = []
    for c in d.caps:
        what, excl = CAP_DEF[c]
        its = [i for i in d.ids if d.items[i]["cap"] == c]
        srcs = []
        for s in SOURCES:
            n = sum(d.items[i]["source"] == s for i in its)
            if n:
                tiers = sorted({d.items[i]["tier"] for i in its if d.items[i]["source"] == s})
                srcs.append(f"{SOURCES[s][0]}（{n}，{'–'.join([tiers[0], tiers[-1]]) if len(tiers) > 1 else tiers[0]}）")
        fmts = {}
        for i in its:
            t = TYPE_ZH[d.items[i]["type"]]
            fmts[t] = fmts.get(t, 0) + 1
        fmt = " / ".join(f"{t} {n}" for t, n in fmts.items())
        imgs = statistics.mean(d.items[i]["frames"] or d.items[i]["images"] for i in its)
        img = f"{imgs:.0f} 帧" if c == "video" else f"{imgs:.1f}"
        rows.append(f'<tr><td class="nw">{CAP_ZH[c]}</td><td>{esc(what)}</td><td>{esc("；".join(srcs))}</td>'
                    f'<td class="nw">{esc(fmt)}</td><td class="n">{img}</td><td class="n">{f1(a["chance"][c])}</td>'
                    f'<td class="sec">{esc(excl)}</td></tr>')
    caps = table('<th>能力</th><th>考查内容</th><th>来源（题数，难度）</th><th>答题形式（题数）</th><th class="n">每题图片</th>'
                 '<th class="n">随机猜测</th><th>排除的题</th>', rows)

    srows = []
    for s, (name, hf, venue, arxiv, _) in SOURCES.items():
        n = sum(d.items[i]["source"] == s for i in d.ids)
        cap = CAP_ZH[next(d.items[i]["cap"] for i in d.ids if d.items[i]["source"] == s)]
        srows.append(f'<tr><td>{esc(name)}</td><td>{cap}</td><td class="n">{n}</td><td>{esc(venue)}</td>'
                     f'<td><a href="https://arxiv.org/abs/{arxiv}">arXiv:{arxiv}</a></td>'
                     f'<td><a href="https://huggingface.co/datasets/{hf}">{esc(hf)}</a></td></tr>')
    srcs = table('<th>来源评测集</th><th>能力</th><th class="n">题数</th><th>出处</th><th>论文</th><th>数据</th>', srows)

    rules = [
        ("选择题", "取最后一行 “Answer: X” 的选项字母，与标准答案相同得 1 分"),
        ("是非题", "取最后的 yes 或 no，与标准答案相同得 1 分"),
        ("文字短答", "小写、去掉冠词与标点后与标准答案完全相同得 1 分"),
        ("数值短答", "取回答中的数（可带单位或 million 等量级词），相对误差 1% 内得 1 分；ChartQA 按其规则放宽到 5%"),
        ("文档短答", "ANLS：与最接近的标准答案的归一化编辑距离相似度，低于 0.5 记 0"),
        ("坐标", "模型给出 0–1000 的相对坐标，换算到原图后落在目标框内得 1 分"),
        ("视频", "所有模型拿到同样的 16 帧（按时长等分取中点），按上面的题型判分"),
    ]
    rules_t = table("<th>题型</th><th>怎么判</th>", [f'<tr><td class="nw">{esc(k)}</td><td>{esc(v)}</td></tr>' for k, v in rules])

    stats = [
        "每个模型对每道题独立作答 4 次，题目得分取 4 次的平均（avg@4）；读不出答案、被截断或超时记 0 分。",
        "能力得分是该项各题得分的平均（0–100）；总分是 7 项能力的等权平均，不按题数加权。",
        "95% 区间来自 2,000 次按题重抽样（在每项能力内部有放回地抽同样数量的题）；两两比较用成对重抽样。",
        "名次 = 1 + 明显强于它的模型数，“明显强于”指总分差的 95% 区间完全大于 0。按这套题的题量，小于约 ±2.7 分的差距分不出来。",
    ]
    stats_l = "<ul class=list>" + "".join(f"<li>{esc(s)}</li>" for s in stats) + "</ul>"

    notes = []
    for m in d.models:
        n = d.notes.get(m, {})
        st = d.runs[m]["settings"]
        eff = f"reasoning_effort = {st['reasoning_effort']}" if st.get("reasoning_effort") else "reasoning_effort 不设置（厂商默认 max）"
        mt = f"max_tokens = {st['max_tokens']}" if st.get("max_tokens") else "max_tokens 不设上限"
        setting = f"{eff}；{mt}；temperature 用厂商默认值"
        fields = [("厂商", n.get("vendor")), ("发布", n.get("released")), ("权重", n.get("weights")),
                  ("架构", n.get("architecture")), ("价格", n.get("price")), ("调用", n.get("access")),
                  ("本次设置", setting)]
        dl = "".join(f"<dt>{k}</dt><dd>{esc(v)}</dd>" for k, v in fields if v)
        src = "、".join(f'<a href="{esc(u)}">{esc(t)}</a>' for t, u in n.get("sources", []))
        if src:
            dl += f"<dt>资料来源</dt><dd>{src}</dd>"
        notes.append(f'<details class="mnote"><summary><span class="dot {CLS[m]}"></span> {esc(d.names[m])}</summary><dl>{dl}</dl></details>')

    body = f"""<section class="hero"><div class="wrap">
<p class="eyebrow">mmBench</p>
<h1>评测集</h1>
<p class="lead">7 项互不重叠的能力，{len(d.ids)} 道题，抽自 {N_DATASETS} 个公开评测集。</p>
</div></section>
<section class="section alt"><div class="wrap">
<h2>设计原则</h2>
<p class="sub">先给出能力画像，再给出排名。</p>
<div class="steps">{steps}</div>
</div></section>
<section class="section"><div class="wrap">
<h2>7 项能力</h2>
<p class="sub">难度按来源对当前模型是否已饱和分为 L1 基础、L2 中等、L3 困难：L1 {a['tier_n']['L1']} 题，L2 {a['tier_n']['L2']} 题，L3 {a['tier_n']['L3']} 题。</p>
{caps}
<p class="note">随机猜测为逐题的期望得分：选择题为选项数的倒数，是非题 0.5，坐标题为目标框面积占整图的比例，短答案为 0。等权平均 {f1(a['chance_overall'])}。</p>
<h3>来源评测集</h3>
{srcs}
</div></section>
<section class="section alt"><div class="wrap">
<h2>评分规则</h2>
<p class="sub">提示词要求最后一行写 “Answer: …”，取最后一个 “Answer:” 之后的内容判分，不用模型裁判。</p>
{rules_t}
<h3>统计方法</h3>
{stats_l}
</div></section>
<section class="section"><div class="wrap">
<h2>被测模型</h2>
<p class="sub">均通过厂商官方 API（国内站）调用。以下整理自厂商公告与模型卡，厂商自报的分数未经独立复现。</p>
{"".join(notes)}
</div></section>"""
    return page("bench.html", "评测集 · 多模态评测", f"mmBench 的 7 项能力、{N_DATASETS} 个来源评测集、评分规则与统计方法", body)


def dots(scores):
    cls = ["y" if s >= 0.999 else ("p" if s > 0 else "") for s in scores]
    return "".join(f'<i class="{c}"></i>' if c else "<i></i>" for c in cls)


def questions(d):
    M = d.models
    # what each kind of question asks
    groups = {}
    for i in d.ids:
        it = d.items[i]
        key = (it["cap"], it["source"], subtask(i))
        groups.setdefault(key, []).append(i)
    krows, last = [], None
    keys = list(groups)
    for n, ((c, s, st), its) in enumerate(groups.items()):
        end = n + 1 < len(keys) and keys[n + 1][0] != c
        what = SUBTASKS[st][1] if st else SOURCES[s][4]
        if st and s == "timeblind":
            what = SOURCES[s][4] + "：" + what
        name = SOURCES[s][0] + (" · " + SUBTASKS[st][0] if st else "")
        tiers = sorted({d.items[i]["tier"] for i in its})
        fmts = sorted({TYPE_ZH[d.items[i]["type"]] for i in its})
        krows.append(f'<tr{" class=grp" if end else ""}><td class="nw hide-sm">{CAP_ZH[c] if c != last else ""}</td>'
                     f'<td>{esc(name)}</td><td>{esc(what)}</td><td class="nw hide-sm">{"/".join(fmts)}</td>'
                     f'<td>{"/".join(tiers)}</td><td class="n">{len(its)}</td></tr>')
        last = c
    kinds = table('<th class="hide-sm">能力</th><th>来源 · 子任务</th><th>题目在问什么</th><th class="hide-sm">形式</th>'
                  '<th>难度</th><th class="n">题数</th>', krows)

    # per item
    out_zh = {3: "solved", 0: "none"}
    rows = []
    for i in d.ids:
        it = d.items[i]
        k = d.solved(i)
        out = out_zh.get(k, "split")
        off = split_id(i)[3]
        cells = "".join(f'<td class="c"><span class="s4" title="{esc(SHORT[m])}：{" / ".join(f"{x:g}" for x in d.runs[m]["scores"][i])}">'
                        f'{dots(d.runs[m]["scores"][i])}</span></td>' for m in M)
        rows.append(f'<tr data-cap="{it["cap"]}" data-tier="{it["tier"]}" data-out="{out}">'
                    f'<td><a href="{esc(item_url(i))}" target="_blank" rel="noopener">{esc(item_label(i))}</a>'
                    f' <span class="sec mono">#{off}</span></td><td class="nw hide-sm">{CAP_ZH[it["cap"]]}</td>'
                    f'<td>{it["tier"]}</td><td class="nw hide-sm">{TYPE_ZH[it["type"]]}</td>'
                    f'<td class="n hide-sm">{100 * it["chance"]:.0f}</td>{cells}</tr>')
    mh = "".join(f'<th class="c"><span class="dot {CLS[m]}"></span> {esc(SHORT[m])}</th>' for m in M)
    plist = (f'<div class="tw"><table id="plist"><thead><tr><th>题目</th><th class="hide-sm">能力</th><th>难度</th><th class="hide-sm">形式</th>'
             f'<th class="n hide-sm">随机</th>{mh}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')

    def seg(key, opts):
        b = "".join(f'<button type="button" data-value="{v}" aria-pressed="{str(n == 0).lower()}">{t}</button>'
                    for n, (v, t) in enumerate(opts))
        return f'<div class="seg" data-filter="{key}" role="group">{b}</div>'

    counts = {o: sum(1 for i in d.ids if out_zh.get(d.solved(i), "split") == o) for o in ("solved", "split", "none")}
    filters = ('<div class="filters">'
               + seg("cap", [("all", "全部能力")] + [(c, CAP_ZH[c]) for c in d.caps])
               + seg("tier", [("all", "全部难度"), ("L1", "L1"), ("L2", "L2"), ("L3", "L3")])
               + seg("out", [("all", "全部结果"), ("solved", "都答对"), ("split", "有分歧"), ("none", "都答错")])
               + "</div>")
    body = f"""<section class="hero"><div class="wrap">
<p class="eyebrow">{len(d.ids)} 道题</p>
<h1>题目</h1>
<p class="lead">每道题的来源、题型和三个模型 4 次作答的结果。</p>
</div></section>
<section class="section alt"><div class="wrap">
<h2>题型一览</h2>
<p class="sub">本站不转载题面与图片（部分来源只许学术使用），只概述每类题在问什么；点逐题列表中的题目可在 Hugging Face 查看原题。</p>
{kinds}
</div></section>
<section class="section" id="list"><div class="wrap">
<h2>逐题结果</h2>
<p class="sub">每个圆点是一次作答：实心答对，半实心部分得分（文档题 ANLS），空心答错。三个模型都答对 {counts['solved']} 题，有分歧 {counts['split']} 题，都答错 {counts['none']} 题（以 4 次平均 ≥ 0.5 记为答对）。</p>
{filters}
<p class="count" id="pcount">显示 {len(d.ids)} 题</p>
{plist}
<p class="note">随机：随机猜测的期望得分（%），只描述难度下限。ScreenSpot-Pro 与 TimeBlind 的题目来自数据集文件，链接到数据集主页；其余链接到 Hugging Face 数据查看器中的原行。</p>
</div></section>"""
    return page("questions.html", "题目 · 多模态评测", "mmBench 354 道题的来源、题型与逐题结果", body)


def export(d):
    return {
        "version": d.version, "created": CREATED, "models": d.names,
        "note": "No question text or images: item ids, metadata and the 4 sample scores per model. "
                "Aggregates are the technical report's (paper/analysis.json).",
        "items": {i: {**{k: d.items[i][k] for k in ("cap", "tier", "source", "type", "images", "frames", "chance")},
                      "url": item_url(i), "scores": {m: d.runs[m]["scores"][i] for m in d.models}} for i in d.ids},
        "analysis": d.a,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(ROOT, "docs"))
    args = ap.parse_args()
    d = Data()
    os.makedirs(os.path.join(args.out, "assets"), exist_ok=True)
    os.makedirs(os.path.join(args.out, "data"), exist_ok=True)
    pages = {"index.html": index(d), "results.html": results(d), "bench.html": bench(d), "questions.html": questions(d)}
    for name, text in pages.items():
        with open(os.path.join(args.out, name), "w", encoding="utf-8") as f:
            f.write(text)
    for f in ("style.css", "app.js", "icon.svg"):
        shutil.copyfile(os.path.join(HERE, "assets", f), os.path.join(args.out, "assets", f))
    shutil.copyfile(os.path.join(ROOT, "paper", "main.pdf"), os.path.join(args.out, PDF))
    with open(os.path.join(args.out, "data", "mmbench.json"), "w", encoding="utf-8") as f:
        json.dump(export(d), f, ensure_ascii=False, separators=(",", ":"))
    open(os.path.join(args.out, ".nojekyll"), "w").close()
    print(f"wrote {args.out}: {', '.join(pages)}, {PDF}, data/mmbench.json")


if __name__ == "__main__":
    main()
