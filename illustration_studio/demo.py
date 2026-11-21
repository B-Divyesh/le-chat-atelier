"""Private streaming SVG demo, served on the instance's loopback interface."""
import json
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import torch
from peft import PeftModel
from transformers import PreTrainedTokenizerFast, StoppingCriteria, TextIteratorStreamer
from svg_model import get_tokenizer, load_base, prompt_tokens


class Cancelled(StoppingCriteria):
    def __init__(self, flag):
        self.flag = flag

    def __call__(self, input_ids, scores, **kwargs):
        return self.flag.is_set()


class Engine:
    def __init__(self):
        self.raw = get_tokenizer()
        self.tokenizer = PreTrainedTokenizerFast(tokenizer_object=self.raw, bos_token="<s>", eos_token="</s>")
        self.model = load_base().eval()
        self.current = None
        self.lock = threading.Lock()

    def select(self, name):
        if name == "latest":
            checkpoints = sorted(Path("checkpoints").glob("step-*/adapter_model.safetensors"))
            name = checkpoints[-1].parent.name if checkpoints else "base"
        if name == "base":
            return name
        if not name.startswith("step-") or not name[5:].isdigit():
            raise ValueError("Unknown checkpoint")
        if self.current != name:
            path = Path("checkpoints") / name
            if self.current is None:
                self.model = PeftModel.from_pretrained(self.model, path, adapter_name=name)
            else:
                self.model.load_adapter(path, adapter_name=name)
                self.model.set_adapter(name)
                self.model.delete_adapter(self.current)
            self.current = name
        return name

    def stream(self, caption, checkpoint, max_tokens):
        from contextlib import nullcontext
        with self.lock:
            name = self.select(checkpoint)
            yield {"model": name}
            ids = torch.tensor([prompt_tokens(self.raw, caption)], device="cuda")
            cancel = threading.Event()
            streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True, timeout=2)
            errors = []
            def generate():
                try:
                    ctx = self.model.disable_adapter() if self.current and name == "base" else nullcontext()
                    with ctx, torch.inference_mode():
                        self.model.eval()
                        result = self.model.generate(input_ids=ids, attention_mask=torch.ones_like(ids),
                            max_new_tokens=max_tokens, do_sample=False, use_cache=True,
                            pad_token_id=self.raw.token_to_id("</s>"), eos_token_id=self.raw.token_to_id("</s>"),
                            streamer=streamer, stopping_criteria=[Cancelled(cancel)])
                        usage.append(result.shape[1] - ids.shape[1])
                except Exception as exc:
                    errors.append(str(exc))
                    streamer.end()
            usage = []
            worker = threading.Thread(target=generate)
            started = time.monotonic()
            worker.start()
            try:
                while True:
                    try:
                        delta = next(streamer)
                    except queue.Empty:
                        yield {"heartbeat": True}
                        continue
                    except StopIteration:
                        break
                    if delta:
                        yield {"text": delta}
            finally:
                cancel.set()
                worker.join()
            if errors:
                raise RuntimeError(errors[0])
            yield {"done": True, "tokens": usage[0], "seconds": round(time.monotonic() - started, 2)}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in {"/", "/health"}:
            self.send_error(404)
            return
        data = b"ready" if self.path == "/health" else Path("demo.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain" if self.path == "/health" else "text/html; charset=utf-8")
        self.send_header("Content-Security-Policy", "default-src 'none'; img-src data:; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
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
            limit = max(1, min(int(payload.get("max_tokens", 8192)), 8192))
        except (ValueError, TypeError, KeyError) as exc:
            self.send_error(400, str(exc))
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        stream = engine.stream(prompt, payload.get("model", "latest"), limit)
        try:
            for event in stream:
                self.wfile.write((json.dumps(event) + "\n").encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            self.wfile.write((json.dumps({"error": str(exc)}) + "\n").encode())
        finally:
            stream.close()


if __name__ == "__main__":
    engine = Engine()
    print("Ready on 127.0.0.1:8090", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8090), Handler).serve_forever()
