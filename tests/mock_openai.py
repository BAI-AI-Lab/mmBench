"""A stand-in OpenAI-compatible endpoint for testing mmBench end to end without paying for a model.

  MMB_HOME=<dir with data/items> python tests/mock_openai.py [--port 18999]

It answers every chat completion (streamed or not, with a little "reasoning_content" and a usage block): an item whose
prompt appears in the message's text parts gets its correct answer; a model whose name contains "weak" answers about
half of the items wrongly (the same ones every time), so two runs differ. Model "mock-cut" gets a stream the server
drops (no finish reason, no usage).
"""
import argparse
import glob
import hashlib
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mmbench"))
import mm_lib as M  # noqa: E402

ITEMS = []


def load():
    for d in glob.glob(os.path.join(M.ITEMS, "*")):
        try:
            it = json.load(open(os.path.join(d, "item.json")))
        except OSError:
            continue
        ITEMS.append((M.prompt_text(it), it))


def item_answer(it, weak):
    t, gold = it["answer_type"], it["answer"]
    wrong = weak and int(hashlib.sha1(it["id"].encode()).hexdigest(), 16) % 2 == 0
    if t == "point_in_box":
        x1, y1, x2, y2 = it["box"]
        w, h = it["size"]
        x, y = ((x1 + x2) / 2 / w * 1000, (y1 + y2) / 2 / h * 1000) if not wrong else (999, 999)
        return f"The target is here.\nAnswer: ({x:.0f}, {y:.0f})"
    if t == "point_in_mask":
        y, runs = next(iter(it["mask"].items()))
        w, h = it["size"]
        x = (runs[0][0] + runs[0][1]) / 2 if not wrong else w - 1
        return f"It is here.\nAnswer: ({x / w * 1000:.0f}, {(int(y) + 0.5) / h * 1000:.0f})"
    g = gold[0] if isinstance(gold, list) else gold
    if wrong:
        g = {"mcq": "A" if g != "A" else "B", "yesno": "no" if str(g).lower() == "yes" else "yes"}.get(t, "zzz")
    return f"Looking at the image.\nAnswer: {g}"


def text_of(content):
    return content if isinstance(content, str) else "\n".join(p.get("text", "") for p in content if p.get("type") == "text")


def answer(prompt, model=""):
    for key, it in ITEMS:
        if key in prompt:
            return item_answer(it, "weak" in model)
    return "I cannot see this item."


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        prompt = text_of(body["messages"][-1]["content"])
        text = answer(prompt, body["model"])
        usage = {"prompt_tokens": len(prompt) // 4, "completion_tokens": len(text) // 4 + 50,
                 "completion_tokens_details": {"reasoning_tokens": 50}}
        if not body.get("stream"):
            out = {"id": "x", "object": "chat.completion", "created": int(time.time()), "model": body["model"],
                   "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
                   "usage": usage}
            data = json.dumps(out).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()

        def chunk(delta, finish=None, use=None):
            c = {"id": "x", "object": "chat.completion.chunk", "created": int(time.time()), "model": body["model"],
                 "choices": [{"index": 0, "delta": delta, "finish_reason": finish}] if delta is not None else []}
            if use:
                c["usage"] = use
            self.wfile.write(b"data: " + json.dumps(c).encode() + b"\n\n")
            self.wfile.flush()
        chunk({"role": "assistant", "reasoning_content": "Let me look at the image. "})
        for i in range(0, len(text), 200):
            chunk({"content": text[i:i + 200]})
        if body["model"] == "mock-cut":  # the server drops the stream: no finish_reason, no usage
            self.wfile.write(b"data: [DONE]\n\n")
            return
        chunk({}, finish="stop")
        chunk(None, use=usage)
        self.wfile.write(b"data: [DONE]\n\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18999)
    a = ap.parse_args()
    load()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    print(f"mock endpoint on http://127.0.0.1:{a.port}/v1 with {len(ITEMS)} items", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
