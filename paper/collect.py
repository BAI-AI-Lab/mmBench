"""Collect what the report's tables and figures need, as one JSON without any item content (no question text, images,
answers or replies): per item its capability, tier, source, answer type, image / frame count, image size and the
expected score of a random guess; per model and item the 4 sample scores; per call the tokens, start time and latency.

  MMB_HOME=<mmBench home with data/ and runs/> python paper/collect.py      -> paper/paper_data.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.environ.get("MMB_HOME") or os.path.dirname(HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "mmbench"))
import mm_lib as M  # noqa: E402
import mm_render as R  # noqa: E402
from PIL import Image  # noqa: E402

man = M.load_manifest(os.path.join(os.path.dirname(HERE), "samples", "mm.json"))
items = {}
for cap, ids in man["capabilities"].items():
    for iid in ids:
        it = M.load_item(iid)
        d = M.item_dir(iid)
        files = (it.get("images") or []) + (it.get("frames") or [])
        sizes = []
        for f in files[:4]:
            try:
                with Image.open(os.path.join(d, f)) as im:
                    sizes.append(im.size)
            except OSError:
                pass
        t = it["answer_type"]
        if t == "mcq":
            n = len(it["options"]) if it.get("options") else it.get("n_options") or 0
            chance = 1 / n if n else 0.0
        elif t == "yesno":
            chance = 0.5
        elif t == "point_in_box":
            x1, y1, x2, y2 = it["box"]
            w, h = it["size"]
            chance = max(0.0, (x2 - x1) * (y2 - y1) / (w * h))
        else:
            chance = 0.0
        items[iid] = {"cap": cap, "tier": it["tier"], "source": it["source"], "type": t,
                      "n_options": (len(it["options"]) if it.get("options") else it.get("n_options")) if t == "mcq" else None,
                      "images": len(it.get("images") or []), "frames": len(it.get("frames") or []),
                      "size": sizes[0] if sizes else None, "chance": chance,
                      "q_words": len(M.prompt_text(it).split())}
runs = {}
for model in ("kimi-k3.1-pro", "MiniMax-M3.1-Flash", "deepseek-flash"):
    run = os.path.join(HOME, "runs", model, "mm-full")
    last = {}
    for a in M.read_jsonl(f"{run}/answers.jsonl"):
        last[a["q"]] = a
    scores = {}
    for q, a in last.items():
        if a["finish"] == "error":
            continue
        s, got = M.score(M.load_item(a["id"]), a.get("text", ""))
        scores.setdefault(a["id"], {})[a["k"]] = s
    calls = []
    for c in M.read_jsonl(f"{run}/usage.jsonl"):
        if "error" in c or not c.get("usage"):
            continue
        t_in, hit, out, reason = R.tokens(c["usage"])
        calls.append({"id": c["q"].rsplit("#", 1)[0], "start": c["start"], "latency": c["end"] - c["start"],
                      "ttft": (c["first_token"] - c["start"]) if c.get("first_token") else None,
                      "in": t_in, "hit": hit, "out": out, "reasoning": reason})
    info = json.load(open(f"{run}/run.json"))
    runs[model] = {"name": info.get("name"), "scores": {i: [v[k] for k in sorted(v)] for i, v in scores.items()},
                   "calls": calls, "settings": {k: info.get(k) for k in ("reasoning_effort", "max_tokens", "temperature")}}
json.dump({"version": man.get("version"), "items": items, "runs": runs}, open(os.path.join(HERE, "paper_data.json"), "w"))
print(len(items), "items;", {m: (len(r["scores"]), len(r["calls"])) for m, r in runs.items()})
