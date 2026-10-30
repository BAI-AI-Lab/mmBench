"""One request to an OpenAI-compatible chat endpoint, and its line in the usage log (used by mm_run.py).

call() streams by default and records times (start, first token, first answer token, end), tokens, the finish reason
and the reply, or the error; the caller retries errors. A request that runs longer than MM_MAX_SECONDS is cut off and
counts as a timeout (not retried); the server sends no usage for a cut stream, so its tokens are estimated from the
characters streamed (MM_CHARS_PER_TOKEN, 3.57). A stream the server drops after at least MM_CUT_IS_TIMEOUT seconds
also counts as a timeout instead of an error. An account out of balance (402 and the like) sets `broke`, which stops
the run with the answered samples kept.
"""
import json
import os
import threading
import time

TAIL = 600
CHARS_PER_TOKEN = float(os.environ.get("MM_CHARS_PER_TOKEN") or 3.57)
broke = []
_write = threading.Lock()


def log(path, rec):
    """Append one JSON line; safe from several threads."""
    line = (json.dumps(rec, ensure_ascii=False) + "\n").encode()
    with _write:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)


def out_of_balance(e):
    text = repr(e).lower()
    return getattr(e, "status_code", None) == 402 or any(s in text for s in (
        "insufficient balance", "insufficient_balance", "exceeded_current_quota", "suspended",
        "balance is running low"))


def text_of(messages):
    """The last message's text (the text parts of a multimodal one), for the live file."""
    c = messages[-1]["content"]
    return (c if isinstance(c, str) else "\n".join(p.get("text", "") for p in c if p.get("type") == "text"))[:2000]


def call(client, model, messages, args, usage_path, q, logged=None):
    """One request (streamed unless args.stream is false); returns the usage-log record (content or error). `logged` is
    what the log keeps of the messages (default: the messages as sent), e.g. with the images replaced by file names."""
    import openai
    kw = {"model": model, "messages": messages, "temperature": args.temperature, "top_p": 0.95}
    if args.max_tokens:
        kw["max_tokens"] = args.max_tokens
    if getattr(args, "reasoning_effort", None):  # REASONING_EFFORT, e.g. low / high / max (MiniMax, Kimi, DeepSeek)
        kw["extra_body"] = {"reasoning_effort": args.reasoning_effort}
    for k in args.omit:
        kw.pop(k, None)
    logged = messages if logged is None else logged
    rec = {"q": q, "start": time.time(), "stream": args.stream, "messages": logged}
    live = f"{usage_path}.live.{os.getpid()}-{threading.get_ident()}"
    first = first_content = None
    n_reason = n_content = 0
    usage = finish = mdl = None
    try:
        if not args.stream:
            r = client.chat.completions.create(**kw)
            c = r.choices[0]
            content, finish, mdl = c.message.content or "", c.finish_reason, r.model
            usage = r.usage.model_dump() if r.usage else None
        else:
            try:
                stream = client.chat.completions.create(**kw, stream=True, stream_options={"include_usage": True})
            except openai.BadRequestError as e:
                if "stream_options" not in str(e) and "include_usage" not in str(e):
                    raise
                stream = client.chat.completions.create(**kw, stream=True)
            parts, r_tail, c_tail, last_write = [], "", "", 0.0
            limit = float(os.environ.get("MM_MAX_SECONDS") or 0)
            timed_out = False
            for ch in stream:
                if limit and time.time() - rec["start"] > limit:
                    timed_out = True
                    break
                mdl = ch.model or mdl
                if ch.usage:
                    usage = ch.usage.model_dump()
                for c in ch.choices:
                    d = c.delta
                    think = getattr(d, "reasoning_content", None) or (getattr(d, "model_extra", None) or {}).get("reasoning_content")
                    now = time.time()
                    if d.content or think:
                        first = first or now
                    if d.content:
                        first_content = first_content or now
                        parts.append(d.content)
                        n_content += len(d.content)
                        c_tail = (c_tail + d.content)[-TAIL:]
                    if think:
                        n_reason += len(think)
                        r_tail = (r_tail + think)[-TAIL:]
                    finish = c.finish_reason or finish
                    u = (getattr(c, "model_extra", None) or {}).get("usage")
                    usage = u or usage
                if time.time() - last_write > 10:  # what the request is doing now, for watching a long run
                    last_write = time.time()
                    with open(live + ".tmp", "w") as f:
                        json.dump({"q": q, "start": rec["start"], "updated": last_write, "first_token": first,
                                   "first_content": first_content, "reasoning_chars": n_reason,
                                   "content_chars": n_content, "reasoning_tail": r_tail, "content_tail": c_tail,
                                   "prompt": text_of(logged)}, f, ensure_ascii=False)
                    os.replace(live + ".tmp", live)
            if timed_out:
                finish = "timeout"
                stream.close()
            elif finish is None:
                raise RuntimeError("stream ended without a finish_reason")
            content = "".join(parts)
        if finish == "timeout" and not usage:
            usage = {"completion_tokens": round((n_reason + n_content) / CHARS_PER_TOKEN), "prompt_tokens": 0, "estimated": True}
        rec.update(end=time.time(), model=mdl, usage=usage, finish=[finish], chars=[len(content)], content=[content],
                   first_token=first, first_content=first_content, reasoning_chars=n_reason)
    except Exception as e:  # noqa: BLE001  (logged and retried by the caller)
        cut_after = float(os.environ.get("MM_CUT_IS_TIMEOUT") or 0)
        if cut_after and args.stream and time.time() - rec["start"] >= cut_after and not out_of_balance(e):
            # the server dropped a stream that had already run this long: the model did not finish in time
            rec.update(end=time.time(), model=mdl, finish=["timeout"], chars=[0], content=[""], first_token=first,
                       first_content=first_content, reasoning_chars=n_reason, content_chars=n_content, cut=repr(e)[:300],
                       usage=usage or {"completion_tokens": round((n_reason + n_content) / CHARS_PER_TOKEN),
                                       "prompt_tokens": 0, "estimated": True})
        else:
            if out_of_balance(e):
                broke.append(1)
            rec.update(end=time.time(), error=repr(e)[:500], first_token=first, first_content=first_content,
                       reasoning_chars=n_reason, content_chars=n_content, usage=usage)
    finally:
        if os.path.exists(live):
            os.remove(live)
    log(usage_path, rec)
    return rec
