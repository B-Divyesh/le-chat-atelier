"""Fast drop-in replacement for demo.py: same HTTP API, generation proxied to vLLM.

Start one or more vLLM OpenAI servers first (see serve_vllm.sh), then for LoRA mode:

    python -u fast_server.py \
        --upstream base=http://127.0.0.1:8001#base \
        --upstream step-0625=http://127.0.0.1:8001#step-0625 \
        --default step-0625

studio.js, local_studio.py, demo.html and eval.py work unchanged against this server.
"""
import argparse
import http.client
import json
import queue
import re
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from svg_model import get_tokenizer, prompt_tokens

ROOT = Path(__file__).resolve().parent
CSP = ("default-src 'none'; img-src data:; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
       "connect-src 'self'; frame-ancestors 'none'")
TAG = re.compile(r"<(/?)([A-Za-z][\w:.-]*)[^<>]*?(/?)>")
COMMENT = re.compile(r"<!--.*?-->", re.S)


def find_loop(text, chunk=48, repeats=3, window=2000):
    """True when the end of `text` is the same unit repeated back to back.

    The unit is found from the previous occurrence of the last `chunk` characters.
    It must repeat at least `repeats` times and cover at least chunk * repeats
    characters, so short legitimate repeats (shared attribute strings, a few equal
    coordinates) never trigger it. Catches the degenerate Bezier loop where every
    point sits at the same coordinate. A unit that spans whole elements needs twice
    as many copies: real OmniSVG files sometimes stack 3 identical paths.
    """
    recent = text[-window:]
    n = len(recent)
    if n < chunk * repeats:
        return False
    tail = recent[-chunk:]
    previous = recent.rfind(tail, 0, n - 1)
    if previous < 0:
        return False
    period = n - chunk - previous
    unit = recent[-period:]
    copies = max(repeats * (2 if "<" in unit else 1), -(-chunk * repeats // period))
    span = period * copies
    return span <= n and recent[-span:] == unit * copies


def open_tags(fragment):
    stack = []
    for closing_tag, name, self_closing in TAG.findall(COMMENT.sub("", fragment)):
        if self_closing:
            continue
        if closing_tag:
            if name in stack:
                del stack[len(stack) - 1 - stack[::-1].index(name):]
        else:
            stack.append(name)
    return stack


def closing(text):
    """Text to append so a truncated SVG still parses. Empty when already closed."""
    start = text.rfind("<svg")
    if start < 0 or "</svg>" in text[start:]:
        return ""
    body = text[start:]
    lt, gt = body.rfind("<"), body.rfind(">")
    partial = body[lt:] if lt > gt else ""
    stack = open_tags(body[:len(body) - len(partial)])
    tail = ""
    if partial.startswith("<!--"):
        tail = " -->"
    elif partial.startswith("</"):
        typed = partial[2:].strip()
        target = next((name for name in reversed(stack) if name.startswith(typed)), None)
        if target is None:
            tail = ">" if typed else "svg>"
            target = typed or "svg"
        else:
            tail = target[len(typed):] + ">"
        if target in stack:
            del stack[len(stack) - 1 - stack[::-1].index(target):]
    elif partial:
        if re.match(r"<[A-Za-z][\w:.-]*\s", partial):
            if partial.count('"') % 2 == 0 and partial.rstrip().endswith("/"):
                return ">" + "".join(f"</{name}>" for name in reversed(stack))
            if partial.count('"') % 2:
                tail = '"'
            elif re.search(r"=\s*$", partial):
                tail = '""'
            elif re.search(r"\s[\w:.-]+$", partial):
                tail = '=""'
            tail += "/>"
        elif "path".startswith(partial[1:]):
            tail = 'path d=""/>'[len(partial) - 1:]
        else:
            tail = "/>"
    return tail + "".join(f"</{name}>" for name in reversed(stack))


class Upstream:
    def __init__(self, spec):
        name, sep, rest = spec.partition("=")
        if not sep or not name:
            raise ValueError(f"Expected NAME=URL#SERVED_MODEL, got {spec!r}")
        url, _, served = rest.partition("#")
        parts = urlsplit(url)
        if parts.scheme != "http" or not parts.hostname:
            raise ValueError(f"Expected an http:// URL in {spec!r}")
        self.name, self.served = name, served or name
        self.host, self.port = parts.hostname, parts.port or 80
        self.prefix = parts.path.rstrip("/")

    def connect(self, timeout):
        return http.client.HTTPConnection(self.host, self.port, timeout=timeout)

    def healthy(self):
        conn = self.connect(2)
        try:
            conn.request("GET", self.prefix + "/health")
            return conn.getresponse().status == 200
        except (OSError, http.client.HTTPException):
            return False
        finally:
            conn.close()


def shut(conn):
    """Close the upstream socket so a blocked reader wakes and vLLM aborts the request."""
    sock = conn.sock
    if sock is not None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
    conn.close()


class Engine:
    def __init__(self, args):
        self.tokenizer = get_tokenizer()
        self.upstreams = {}
        for spec in args.upstream:
            upstream = Upstream(spec)
            self.upstreams[upstream.name] = upstream
        self.default = args.default or next((n for n in self.upstreams if n != "base"), next(iter(self.upstreams)))
        if self.default not in self.upstreams:
            raise SystemExit(f"--default {self.default} is not one of {list(self.upstreams)}")
        self.temperature, self.top_p, self.cap = args.temperature, args.top_p, args.max_tokens
        self.loop = dict(chunk=args.loop_chunk, repeats=args.loop_repeats)
        self._rr, self._rr_lock = 0, threading.Lock()

    def healthy(self):
        seen, ok = set(), True
        for upstream in self.upstreams.values():
            key = (upstream.host, upstream.port, upstream.prefix)
            if key not in seen:
                seen.add(key)
                ok = upstream.healthy() and ok
        return ok

    def sprite(self, name, temperature, size=8):
        """NxN PICO-8 sprite from a pixel model; a grammar forces exactly N rows of N palette characters."""
        upstream = self.upstreams.get(f"pix{size}")
        if upstream is None:
            raise ValueError(f"No pix{size} upstream configured")
        system = (f"Draw the requested game sprite as {size}x{size} pixel art in the PICO-8 palette. "
                  f"Reply with {size} lines of {size} characters: . is transparent, 0-f are palette colors.")
        grammar = f"root ::= {' '.join(['row'] * size)}\nrow ::= {' '.join(['px'] * size)} \"\\n\"\npx ::= [.0-9a-f]\n"
        ids = self.tokenizer.encode(f"<s>[SYSTEM_PROMPT]{system}[/SYSTEM_PROMPT][INST]{name}[/INST]",
                                    add_special_tokens=False).ids
        body = json.dumps(dict(prompt=ids, n_predict=size * size + size + 30, temperature=temperature, top_p=0.95,
                               cache_prompt=True, grammar=grammar)).encode()
        conn = upstream.connect(60)
        started = time.monotonic()
        try:
            conn.request("POST", upstream.prefix + "/completion", body, {"Content-Type": "application/json"})
            response = conn.getresponse()
            result = json.loads(response.read())
        finally:
            conn.close()
        rows = [r for r in result.get("content", "").split("\n") if r][:size]
        if len(rows) != size or any(len(r) != size for r in rows):
            raise ValueError(f"Malformed sprite: {result.get('content', '')[:80]!r}")
        return {"name": name, "rows": rows, "tokens": result.get("tokens_predicted"),
                "ms": round((time.monotonic() - started) * 1000)}

    def _complete(self, system, user, **params):
        """Non-streaming completion on the base (instruct) model."""
        upstream = self.upstreams.get("base")
        if upstream is None:
            raise ValueError("No base upstream configured")
        ids = self.tokenizer.encode(f"<s>[SYSTEM_PROMPT]{system}[/SYSTEM_PROMPT][INST]{user}[/INST]",
                                    add_special_tokens=False).ids
        conn = upstream.connect(120)
        try:
            conn.request("POST", upstream.prefix + "/completion",
                         json.dumps(dict(prompt=ids, cache_prompt=True, **params)).encode(), {"Content-Type": "application/json"})
            return json.loads(conn.getresponse().read())
        finally:
            conn.close()

    def world(self, prompt):
        """World director: turn the player's prompt into a game-world spec (schema-constrained JSON)."""
        started = time.monotonic()
        result = self._complete(
            "You design tiny retro 8-bit adventure game worlds as JSON. Every object is ONE complete visual noun phrase "
            "of 2-4 words that starts with a color word, so it can be drawn as an 8x8 sprite. Never split a phrase "
            "across list items. Example:\n" + WORLD_EXAMPLE,
            f"Design a game world for this idea: {prompt}",
            n_predict=900, temperature=0.8, top_p=0.95, json_schema=WORLD_SCHEMA)
        spec = json.loads(result["content"])
        spec["ms"] = round((time.monotonic() - started) * 1000)
        spec["tokens"] = result.get("tokens_predicted")
        return spec

    def arena(self, prompt):
        """Director for the survivors arena: hero, enemies with behaviors, boss, weapons with mechanics."""
        started = time.monotonic()
        result = self._complete(
            "You design retro 8-bit survivor arena games as JSON. Every object is ONE complete visual noun phrase "
            "of 2-4 words that starts with a color word, so it can be drawn as an 8x8 sprite. Enemies escalate "
            "from weak to dangerous. Pick the game genre that best fits the idea: survivors (top-down, enemies chase you, "
            "collect gems), snake (a creature that grows by eating), shooter (a ship at the bottom shoots descending enemies), "
            "dodge (a vertical racer dodging falling obstacles), platformer (side view, jump between platforms, collect coins). "
            "The projectile is the bullet, or for snake the body segment. Example:\n" + ARENA_EXAMPLE,
            f"Design a survivor arena for this idea: {prompt}",
            n_predict=900, temperature=0.8, top_p=0.95, json_schema=ARENA_SCHEMA)
        spec = json.loads(result["content"])
        spec["ms"] = round((time.monotonic() - started) * 1000)
        return spec

    def wave(self, title, number, previous):
        """Invent the next enemy for this wave, escalating from the ones the player has already met."""
        started = time.monotonic()
        result = self._complete(
            "You are the dungeon master of a retro 8-bit survivor game. Invent ONE new enemy for the next wave. "
            "Its name is a 2-4 word visual noun phrase starting with a color word. It must be stranger and more "
            "dangerous than earlier enemies and fit the world. The taunt is one menacing sentence.",
            f"World: {title}. Wave {number}. Enemies so far: {', '.join(previous[-8:])}.",
            n_predict=120, temperature=0.95, top_p=0.95, json_schema=WAVE_SCHEMA)
        spec = json.loads(result["content"])
        spec["ms"] = round((time.monotonic() - started) * 1000)
        return spec

    def upgrade(self, title, level, owned):
        """Level-up: the model designs three themed upgrade options."""
        started = time.monotonic()
        result = self._complete(
            "You are the game master of a retro 8-bit survivor game. Offer exactly three level-up choices themed to "
            "the world. Weapon kinds: bolt (auto-fires at the nearest enemy), orbit (blades circle the hero), nova "
            "(periodic blast), aura (damage zone). Stat kinds: speed, health, damage, magnet. Mix weapons and stats. "
            "Each name is a 2-4 word visual noun phrase starting with a color word; the blurb says what it does.",
            f"World: {title}. Hero level {level}. Already owned: {', '.join(owned[-8:]) or 'nothing'}.",
            n_predict=260, temperature=0.9, top_p=0.95, json_schema=UPGRADE_SCHEMA)
        spec = json.loads(result["content"])
        spec["ms"] = round((time.monotonic() - started) * 1000)
        return spec

    def _next_wm(self):
        """Round-robin over world-model replicas (upstreams named wm, wm_*) so both GPUs share the work."""
        ups = [u for n, u in self.upstreams.items() if n == "wm" or n.startswith("wm_")]
        if not ups:
            raise ValueError("No wm upstream configured")
        with self._rr_lock:
            self._rr = (self._rr + 1) % len(ups)
            return ups[self._rr]

    def step_once(self, svg, action, temperature=0.3):
        upstream = self._next_wm()
        ids = self.tokenizer.encode(f"<s>[INST]{action}\n{svg}[/INST]", add_special_tokens=False).ids
        conn = upstream.connect(60)
        started = time.monotonic()
        try:
            conn.request("POST", upstream.prefix + "/completion", json.dumps(dict(
                prompt=ids, n_predict=520, temperature=temperature, top_p=0.95, cache_prompt=True, grammar=grammar_for(action))).encode(),
                {"Content-Type": "application/json"})
            r = json.loads(conn.getresponse().read())
        finally:
            conn.close()
        return {"svg": r.get("content", ""), "tokens": r.get("tokens_predicted"), "ms": round((time.monotonic() - started) * 1000),
                "replica": f"{upstream.host}:{upstream.port}"}

    def step_all(self, svg, prefix, actions, temperature=0.3):
        """Branch prefetch: generate the next frame for every possible action in parallel across all replicas."""
        from concurrent.futures import ThreadPoolExecutor
        started = time.monotonic()
        with ThreadPoolExecutor(len(actions)) as ex:
            outs = list(ex.map(lambda a: self.step_once(svg, prefix + a, temperature), actions))
        return {"branches": dict(zip(actions, outs)), "ms": round((time.monotonic() - started) * 1000)}

    def start_frame(self, genre, layout=""):
        """Environment generation: the model writes the first frame; it is checked against the genre's invariants and
        resampled (hotter) up to 3 times, falling back to the procedural generator only if every sample fails."""
        action = f"{genre}: start" + (f" {layout}" if genre == "survivors" and layout else "")
        def ok(f):
            if not f.endswith("</svg>"):
                return False
            hero = re.search(r'#hero" x="(\d+)" y="(\d+)"', f)
            if not hero:
                return False
            hx, hy = int(hero.group(1)), int(hero.group(2))
            cells = [(int(a), int(b)) for a, b in re.findall(r'x="(\d+)" y="(\d+)"', f)]
            if any(x > 15 or y > 11 for x, y in cells):
                return False
            stands = f'#o2" x="{hx}" y="{hy + 1}"' in f
            return {"snake": f.count('#b"') >= 2, "dodge": hy == 10, "shooter": hy == 11,
                    "platformer": f.count('#o2"') >= 6 and stands, "survivors": "HP 5 XP 0 T 0" in f}.get(genre, True)
        tries = []
        for temperature in (0.3, 0.8, 1.0):
            r = self.step_once(EMPTY_FRAME, action, temperature)
            tries.append(r["ms"])
            if ok(r["svg"]):
                return {"svg": r["svg"], "source": "model", "tries": len(tries), "ms": sum(tries)}
        import random as _random
        import wm_multi
        new, _, to_svg, _, _ = wm_multi.GENRES[genre]
        state = wm_multi.surv.new_env(_random.Random(), layout or None) if genre == "survivors" else new(_random.Random())
        return {"svg": to_svg(state), "source": "procedural", "tries": len(tries), "ms": sum(tries)}

    def step_stream(self, svg, action, temperature=0.3):
        """World-model step: current SVG frame + action -> next SVG frame, streamed as text deltas."""
        upstream = self._next_wm()
        ids = self.tokenizer.encode(f"<s>[INST]{action}\n{svg}[/INST]", add_special_tokens=False).ids
        body = json.dumps(dict(prompt=ids, n_predict=520, temperature=temperature, top_p=0.95, cache_prompt=True,
                               grammar=grammar_for(action), stream=True)).encode()
        conn = upstream.connect(60)
        started, tokens = time.monotonic(), 0
        try:
            conn.request("POST", upstream.prefix + "/completion", body, {"Content-Type": "application/json"})
            for raw in conn.getresponse():
                line = raw.strip()
                if not line.startswith(b"data:"):
                    continue
                obj = json.loads(line[5:])
                if obj.get("content"):
                    tokens += 1
                    yield {"text": obj["content"]}
                if obj.get("stop"):
                    break
        finally:
            conn.close()
        yield {"done": True, "ms": round((time.monotonic() - started) * 1000), "tokens": tokens}

    def sprite_stream(self, name, temperature, size=8):
        """Stream an NxN sprite row by row as the model writes it (grammar-constrained)."""
        upstream = self.upstreams.get(f"pix{size}")
        if upstream is None:
            raise ValueError(f"No pix{size} upstream configured")
        system = (f"Draw the requested game sprite as {size}x{size} pixel art in the PICO-8 palette. "
                  f"Reply with {size} lines of {size} characters: . is transparent, 0-f are palette colors.")
        grammar = f"root ::= {' '.join(['row'] * size)}\nrow ::= {' '.join(['px'] * size)} \"\\n\"\npx ::= [.0-9a-f]\n"
        ids = self.tokenizer.encode(f"<s>[SYSTEM_PROMPT]{system}[/SYSTEM_PROMPT][INST]{name}[/INST]",
                                    add_special_tokens=False).ids
        body = json.dumps(dict(prompt=ids, n_predict=size * size + size + 30, temperature=temperature, top_p=0.95,
                               cache_prompt=True, grammar=grammar, stream=True)).encode()
        conn = upstream.connect(60)
        started, buf, tokens = time.monotonic(), "", 0
        try:
            conn.request("POST", upstream.prefix + "/completion", body, {"Content-Type": "application/json"})
            response = conn.getresponse()
            for raw in response:
                line = raw.strip()
                if not line.startswith(b"data:"):
                    continue
                obj = json.loads(line[5:])
                if obj.get("content"):
                    buf += obj["content"]; tokens += 1
                while "\n" in buf:
                    row, buf = buf.split("\n", 1)
                    if row:
                        yield {"row": row}
                if obj.get("stop"):
                    break
        finally:
            conn.close()
        yield {"done": True, "ms": round((time.monotonic() - started) * 1000), "tokens": tokens}

    def narrate(self, title, event):
        result = self._complete(
            "You narrate a retro 8-bit adventure game. Reply with ONE short vivid sentence (at most 22 words), "
            "second person, no quotes.",
            f"World: {title}. Event: {event}", n_predict=60, temperature=0.9, top_p=0.95, stop=["\n"])
        return {"text": result.get("content", "").strip()}

    def stream(self, caption, requested, max_tokens, temperature, top_p, repair):
        name = self.default if requested == "latest" else requested
        upstream = self.upstreams.get(name)
        if upstream is None:
            raise ValueError("Unknown checkpoint")
        yield {"model": name}
        body = json.dumps(dict(
            model=upstream.served, prompt=prompt_tokens(self.tokenizer, caption), max_tokens=max_tokens,
            temperature=temperature, top_p=top_p, stream=True, stop=["</svg>"],
            include_stop_str_in_output=True, skip_special_tokens=True,
            stream_options={"include_usage": True})).encode()
        conn = upstream.connect(600)
        events = queue.Queue()
        cancel = threading.Event()

        def read():
            try:
                conn.request("POST", upstream.prefix + "/v1/completions", body, {"Content-Type": "application/json"})
                response = conn.getresponse()
                if response.status != 200:
                    detail = response.read(400).decode(errors="replace")
                    events.put(("error", f"vLLM returned {response.status}: {detail}"))
                    return
                for raw in response:
                    if cancel.is_set():
                        return
                    line = raw.strip()
                    if not line.startswith(b"data:"):
                        continue
                    data = line[5:].strip()
                    if data == b"[DONE]":
                        return
                    events.put(("chunk", json.loads(data)))
            except Exception as exc:  # reported to the client unless we cancelled on purpose
                if not cancel.is_set():
                    events.put(("error", f"{type(exc).__name__}: {exc}"))
            finally:
                events.put(("end", None))

        worker = threading.Thread(target=read, daemon=True)
        started = time.monotonic()
        worker.start()
        text, usage_tokens, reason, first = "", None, None, None
        try:
            while True:
                try:
                    kind, value = events.get(timeout=2)
                except queue.Empty:
                    yield {"heartbeat": True}
                    continue
                if kind == "end":
                    break
                if kind == "error":
                    raise RuntimeError(value)
                usage = value.get("usage")
                if usage and usage.get("completion_tokens") is not None:
                    usage_tokens = usage["completion_tokens"]
                for choice in value.get("choices") or []:
                    delta = choice.get("text") or ""
                    if delta:
                        if first is None:
                            first = time.monotonic() - started
                        text += delta
                        yield {"text": delta}
                    if choice.get("finish_reason"):
                        reason = choice["finish_reason"]
                if reason is None and find_loop(text, **self.loop):
                    reason = "loop"
                    break
        finally:
            cancel.set()
            shut(conn)
            worker.join(timeout=5)
        if usage_tokens is None or reason == "loop":
            # vLLM sends usage only when the request runs to completion.
            usage_tokens = len(self.tokenizer.encode(text, add_special_tokens=False).ids)
        seconds = time.monotonic() - started
        tail = closing(text) if repair else ""
        if tail:
            yield {"text": tail}
        print(json.dumps(dict(model=name, tokens=usage_tokens, seconds=round(seconds, 2),
                              tokens_per_second=round(usage_tokens / max(seconds, 1e-6), 1),
                              first_token_s=None if first is None else round(first, 2),
                              stopped=reason or "stop", repaired=bool(tail))), flush=True)
        yield {"done": True, "tokens": usage_tokens, "seconds": round(seconds, 2), "stopped": reason or "stop",
               "repaired": bool(tail), "first_token_s": None if first is None else round(first, 2)}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path not in {"/", "/health", "/game", "/explore"}:
            self.send_error(404)
            return
        if path == "/health":
            ready = engine.healthy()
            data, status, mime = (b"ready", 200, "text/plain") if ready else (b"starting", 503, "text/plain")
        elif path in ("/game", "/explore"):
            data, status, mime = (ROOT / ("world.html" if path == "/game" else "game.html")).read_bytes(), 200, "text/html; charset=utf-8"
        else:
            data, status, mime = (ROOT / PAGE).read_bytes(), 200, "text/html; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path in ("/start", "/step_stream", "/step_all") and self.headers.get("X-Atelier") != "3":
            # stale game tabs keep stepping in the background and steal GPU time: ask them to reload
            data = json.dumps({"error": "This game tab is outdated. Please reload the page."}).encode()
            self.send_response(409); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data)))
            self.end_headers(); self.wfile.write(data)
            return
        if self.path == "/start":
            try:
                n = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(n))
                genre = str(payload.get("genre", "survivors"))
                if genre not in {"survivors", "snake", "shooter", "dodge", "platformer"}:
                    raise ValueError("Unknown genre")
                layout = str(payload.get("layout", ""))
                layout = layout if layout in {"arena", "forest", "maze", "islands", "cave"} else ""
                data, status = json.dumps(engine.start_frame(genre, layout)).encode(), 200
            except Exception as exc:
                data, status = json.dumps({"error": str(exc)}).encode(), 500
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/step_all":
            try:
                n = int(self.headers.get("Content-Length", 0))
                if not 0 < n <= 20000:
                    raise ValueError("Request too large")
                payload = json.loads(self.rfile.read(n))
                svg = str(payload["svg"])[:6000]
                genre = str(payload.get("genre", ""))
                if genre and genre not in {"survivors", "snake", "shooter", "dodge", "platformer"}:
                    raise ValueError("Unknown genre")
                actions = [a for a in payload.get("actions", []) if a in {"up", "down", "left", "right", "stay"}][:5] or ["stay"]
                result = engine.step_all(svg, f"{genre}: " if genre else "", actions, min(max(float(payload.get("temperature", 0.3)), 0.0), 1.5))
                data, status = json.dumps(result).encode(), 200
            except Exception as exc:
                data, status = json.dumps({"error": str(exc)}).encode(), 500
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/step_stream":
            try:
                n = int(self.headers.get("Content-Length", 0))
                if not 0 < n <= 20000:
                    raise ValueError("Request too large")
                payload = json.loads(self.rfile.read(n))
                svg = str(payload["svg"])[:6000]
                action = str(payload.get("action", "stay"))
                if not re.fullmatch(r"((survivors|snake|shooter|dodge|platformer): )?(up|down|left|right|stay|start( (arena|forest|maze|islands|cave))?)", action):
                    raise ValueError("Unknown action")
                temperature = min(max(float(payload.get("temperature", 0.3)), 0.0), 1.5)
            except (ValueError, TypeError, KeyError) as exc:
                self.send_error(400, str(exc))
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            try:
                for event in engine.step_stream(svg, action, temperature):
                    self.wfile.write((json.dumps(event) + "\n").encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as exc:
                try:
                    self.wfile.write((json.dumps({"error": str(exc)}) + "\n").encode())
                except OSError:
                    pass
            return
        if self.path == "/sprite_stream":
            try:
                n = int(self.headers.get("Content-Length", 0))
                if not 0 < n <= 4000:
                    raise ValueError("Request too large")
                payload = json.loads(self.rfile.read(n))
                name = str(payload["name"]).strip()[:120]
                size = 16 if int(payload.get("size", 8)) == 16 else 8
                temperature = min(max(float(payload.get("temperature", 0.75)), 0.0), 1.5)
            except (ValueError, TypeError, KeyError) as exc:
                self.send_error(400, str(exc))
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            try:
                for event in engine.sprite_stream(name, temperature, size):
                    self.wfile.write((json.dumps(event) + "\n").encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as exc:
                try:
                    self.wfile.write((json.dumps({"error": str(exc)}) + "\n").encode())
                except OSError:
                    pass
            return
        if self.path in ("/world", "/narrate", "/arena", "/wave", "/upgrade"):
            try:
                n = int(self.headers.get("Content-Length", 0))
                if not 0 < n <= 4000:
                    raise ValueError("Request too large")
                payload = json.loads(self.rfile.read(n))
                if self.path == "/world":
                    result = engine.world(str(payload["prompt"]).strip()[:300] or "a mysterious land")
                elif self.path == "/arena":
                    result = engine.arena(str(payload["prompt"]).strip()[:300] or "a mysterious land")
                elif self.path == "/upgrade":
                    result = engine.upgrade(str(payload.get("title", ""))[:80], int(payload.get("level", 1)),
                                            [str(x)[:60] for x in payload.get("owned", [])][:20])
                elif self.path == "/wave":
                    result = engine.wave(str(payload.get("title", ""))[:80], int(payload.get("number", 1)),
                                         [str(x)[:60] for x in payload.get("previous", [])][:20])
                else:
                    result = engine.narrate(str(payload.get("title", ""))[:80], str(payload["event"])[:200])
                data, status = json.dumps(result).encode(), 200
            except Exception as exc:  # reported to the game as JSON
                data, status = json.dumps({"error": str(exc)}).encode(), 500
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/sprite":
            try:
                n = int(self.headers.get("Content-Length", 0))
                if not 0 < n <= 4000:
                    raise ValueError("Request too large")
                payload = json.loads(self.rfile.read(n))
                name = str(payload["name"]).strip()[:120]
                if not name:
                    raise ValueError("Empty sprite name")
                temperature = min(max(float(payload.get("temperature", 0.6)), 0.0), 1.5)
                size = 16 if int(payload.get("size", 8)) == 16 else 8
                result = engine.sprite(name, temperature, size)
                data, status = json.dumps(result).encode(), 200
            except Exception as exc:  # reported to the game as JSON
                data, status = json.dumps({"error": str(exc)}).encode(), 500
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path != "/generate":
            self.send_error(404)
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            if not 0 < n <= 12000:
                raise ValueError("Request too large")
            payload = json.loads(self.rfile.read(n))
            prompt = payload["prompt"].strip()
            if not 0 < len(prompt) <= 2000:
                raise ValueError("Enter a description under 2,000 characters")
            limit = max(1, min(int(payload.get("max_tokens", engine.cap)), engine.cap))
            temperature = payload.get("temperature")
            temperature = engine.temperature if temperature is None else min(max(float(temperature), 0.0), 2.0)
            top_p = payload.get("top_p")
            top_p = engine.top_p if top_p is None else min(max(float(top_p), 0.01), 1.0)
            repair = bool(payload.get("repair", True))
            model = str(payload.get("model", "latest"))
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            self.send_error(400, str(exc))
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        stream = engine.stream(prompt, model, limit, temperature, top_p, repair)
        try:
            for event in stream:
                self.wfile.write((json.dumps(event) + "\n").encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            try:
                self.wfile.write((json.dumps({"error": str(exc)}) + "\n").encode())
            except OSError:
                pass
        finally:
            stream.close()


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8091)
    p.add_argument("--upstream", action="append", required=True,
                   help="NAME=URL#SERVED_MODEL, e.g. step-0625=http://127.0.0.1:8001#step-0625 (repeatable)")
    p.add_argument("--default", help="Model used for 'latest' (default: first upstream that is not 'base')")
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--top-p", type=float, default=0.95)
    p.add_argument("--max-tokens", type=int, default=8192, help="Upper cap on tokens per drawing")
    p.add_argument("--loop-chunk", type=int, default=48)
    p.add_argument("--loop-repeats", type=int, default=3)
    p.add_argument("--page", default="demo.html", help="HTML page served at / (relative to this file)")
    return p.parse_args(argv)


PAGE = "demo.html"
PIX_SYSTEM = ("Draw the requested game sprite as 8x8 pixel art in the PICO-8 palette. "
              "Reply with 8 lines of 8 characters: . is transparent, 0-f are palette colors.")
_S = {"type": "string", "minLength": 5, "maxLength": 40}
COLORS = ["green", "dark green", "sand", "white", "grey", "brown", "purple", "blue", "dark blue", "red", "orange", "pink", "black", "yellow"]
WORLD_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 3, "maxLength": 40},
        "intro": {"type": "string", "minLength": 20, "maxLength": 260},
        "hero": _S,
        "liquid": {"type": "string", "enum": ["water", "lava", "acid", "void", "ice"]},
        "biomes": {"type": "array", "minItems": 3, "maxItems": 3, "items": {
            "type": "object",
            "properties": {
                "name": _S, "ground": _S, "ground_color": {"type": "string", "enum": COLORS},
                "obstacles": {"type": "array", "minItems": 3, "maxItems": 3, "items": _S},
                "heal_item": _S, "stamina_item": _S, "treasure": _S,
                "enemies": {"type": "array", "minItems": 2, "maxItems": 2, "items": _S},
            },
            "required": ["name", "ground", "ground_color", "obstacles", "heal_item", "stamina_item", "treasure", "enemies"],
        }},
    },
    "required": ["title", "intro", "hero", "liquid", "biomes"],
}
WM_GRAMMAR = r'''root ::= "<svg viewBox=\"0 0 16 12\"><text x=\"0\" y=\"1\">" hud "</text>" use* "</svg>"
hud ::= pair (" " pair)*
pair ::= [A-Z]+ " " num
use ::= "<use href=\"#" kind "\" x=\"" n "\" y=\"" n "\"/>"
kind ::= "hero" | "o1" | "o2" | "e1" | "e2" | "e3" | "gem" | "b"
num ::= "-"? n
n ::= [0-9] | [1-9] [0-9]
'''
EMPTY_FRAME = '<svg viewBox="0 0 16 12"></svg>'
def _genre_grammar(hud, kinds, tail=""):
    use = 'use ::= "<use href=\\"#" kind "\\" x=\\"" xn "\\" y=\\"" yn "\\"/>"\n'
    return ('root ::= "<svg viewBox=\\"0 0 16 12\\"><text x=\\"0\\" y=\\"1\\">" hud "</text>" hero use* ' + tail + '"</svg>"\n'
            f'hud ::= {hud}\n'
            'hero ::= "<use href=\\"#hero\\" x=\\"" xn "\\" y=\\"" yn "\\"/>"\n' + use +
            'kind ::= ' + " | ".join(f'"{k}"' for k in kinds) + "\n"
            'd ::= [0-9]\nnum ::= "-"? n\nn ::= [0-9] | [1-9] [0-9]\n'
            'xn ::= [0-9] | "1" [0-5]\nyn ::= [0-9] | "1" [0-1]\n'
            'gemuse ::= "<use href=\\"#gem\\" x=\\"" xn "\\" y=\\"" yn "\\"/>"\n')
GENRE_GRAMMARS = {
    "survivors": _genre_grammar('"HP " d " XP " n " T " n', ["o1", "o2", "e1", "e2", "e3", "gem"]),
    "snake": _genre_grammar('"LEN " n " SCORE " n " T " n', ["b"], tail="gemuse "),
    "shooter": _genre_grammar('"HP " d " SCORE " n " T " n', ["e1", "e2", "b"]),
    "dodge": _genre_grammar('"HP " d " SCORE " n " T " n', ["o1", "o2", "gem"]),
    "platformer": _genre_grammar('"HP " d " SCORE " n " VY " num " T " n', ["o2", "e1", "e2", "gem"]),
}
def grammar_for(action):
    g = action.split(":", 1)[0] if ":" in action else ""
    return GENRE_GRAMMARS.get(g, WM_GRAMMAR)
BEHAVIORS = ["chaser", "swarm", "tank", "fast", "ranged"]
TOUGH = ["weak", "normal", "tough", "huge"]
SPEEDS = ["slow", "normal", "fast"]
UPGRADE_KINDS = ["bolt", "orbit", "nova", "aura", "speed", "health", "damage", "magnet"]
ARENA_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 3, "maxLength": 40},
        "intro": {"type": "string", "minLength": 20, "maxLength": 220},
        "hero": _S,
        "ground_color": {"type": "string", "enum": COLORS},
        "obstacles": {"type": "array", "minItems": 3, "maxItems": 3, "items": _S},
        "gem": _S, "heal_item": _S,
        "enemies": {"type": "array", "minItems": 4, "maxItems": 4, "items": {
            "type": "object", "properties": {"name": _S, "behavior": {"type": "string", "enum": BEHAVIORS},
                                             "toughness": {"type": "string", "enum": TOUGH}, "speed": {"type": "string", "enum": SPEEDS}},
            "required": ["name", "behavior", "toughness", "speed"]}},
        "boss": _S,
        "layout": {"type": "string", "enum": ["arena", "forest", "maze", "islands", "cave"]},
        "genre": {"type": "string", "enum": ["survivors", "snake", "shooter", "dodge", "platformer"]},
        "projectile": _S,
        "weapons": {"type": "array", "minItems": 4, "maxItems": 4, "items": {
            "type": "object", "properties": {"name": _S, "kind": {"type": "string", "enum": ["bolt", "orbit", "nova", "aura"]}},
            "required": ["name", "kind"]}},
    },
    "required": ["title", "intro", "hero", "ground_color", "obstacles", "gem", "heal_item", "enemies", "boss", "layout", "genre", "projectile", "weapons"],
}
ARENA_EXAMPLE = json.dumps({
    "title": "Ember Hollow", "intro": "Ash falls on a buried kingdom. Hold the line until dawn as the fire swarms rise.",
    "hero": "silver armored knight", "ground_color": "grey",
    "obstacles": ["black charred tree", "red glowing rock", "grey stone pillar"],
    "gem": "blue soul crystal", "heal_item": "red health potion",
    "enemies": [{"name": "orange fire slime", "behavior": "chaser", "toughness": "weak", "speed": "normal"},
                {"name": "black ash bat", "behavior": "swarm", "toughness": "weak", "speed": "fast"},
                {"name": "red lava golem", "behavior": "tank", "toughness": "huge", "speed": "slow"},
                {"name": "yellow spark imp", "behavior": "fast", "toughness": "normal", "speed": "fast"}],
    "boss": "giant red fire dragon", "layout": "cave", "genre": "survivors", "projectile": "orange fire bolt",
    "weapons": [{"name": "silver throwing dagger", "kind": "bolt"}, {"name": "blue frost orb", "kind": "orbit"},
                {"name": "orange flame ring", "kind": "nova"}, {"name": "green poison cloud", "kind": "aura"}]})
WAVE_SCHEMA = {"type": "object", "properties": {"name": _S, "behavior": {"type": "string", "enum": BEHAVIORS},
               "toughness": {"type": "string", "enum": TOUGH}, "speed": {"type": "string", "enum": SPEEDS},
               "count": {"type": "string", "enum": ["few", "pack", "horde"]},
               "taunt": {"type": "string", "minLength": 10, "maxLength": 140}},
               "required": ["name", "behavior", "toughness", "speed", "count", "taunt"]}
UPGRADE_SCHEMA = {"type": "object", "properties": {"options": {"type": "array", "minItems": 3, "maxItems": 3, "items": {
                  "type": "object", "properties": {"name": _S, "kind": {"type": "string", "enum": UPGRADE_KINDS},
                                                   "blurb": {"type": "string", "minLength": 8, "maxLength": 70}},
                  "required": ["name", "kind", "blurb"]}}}, "required": ["options"]}
WORLD_EXAMPLE = json.dumps({
    "title": "Ember Hollow", "intro": "Ash falls on a buried kingdom. A lone knight wakes beside the lava river, sword in hand.",
    "hero": "silver armored knight", "liquid": "lava",
    "biomes": [{"name": "Cinder Plains", "ground": "grey ash ground", "ground_color": "grey",
                "obstacles": ["black charred tree", "red glowing rock", "grey stone pillar"],
                "heal_item": "red health potion", "stamina_item": "orange fire fruit", "treasure": "gold coin",
                "enemies": ["orange fire slime", "black ash bat"]}]})
PIX_GRAMMAR = 'root ::= row row row row row row row row\nrow ::= px px px px px px px px "\\n"\npx ::= [.0-9a-f]\n'

if __name__ == "__main__":
    args = parse_args()
    PAGE = args.page
    engine = Engine(args)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    print(f"Ready on {server.server_address[0]}:{server.server_address[1]} · upstreams "
          + ", ".join(f"{u.name}→{u.host}:{u.port}#{u.served}" for u in engine.upstreams.values())
          + f" · latest={engine.default}", flush=True)
    server.serve_forever()
