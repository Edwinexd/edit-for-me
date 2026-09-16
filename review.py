"""Review rounds: publish a render for the user, serve the review web UI, read the answers.

Usage:
  venv/bin/python review.py publish [RENDER.mp4] [--edl EDL]   (default work/preview.mp4, work/edl.json)
  venv/bin/python review.py serve [--port 8790]
  venv/bin/python review.py wait [ROUND]      (keeps running; prints a line per send)
  venv/bin/python review.py show [ROUND]      (default: the latest round)

Paths are in the project folder (see project.py).

`publish` copies the render, its timeline and the EDL to review/review-N.*
(so their times stay fixed while editing continues) and writes a skeleton
review/review-N.json. The agent then fills in what the user should check:

  {"title": "review-2: redone joins",
   "notes": "What changed since the last round.",
   "items": [
    {"id": "formatet", "kind": "join", "title": "Formatet",
     "question": "Does the splice sound natural?",
     "at": "Formatet@15.9", "to": 21.0, "choices": ["ok", "redo"]},
    {"id": "intro-take", "kind": "take", "title": "Which intro take?",
     "clips": [{"label": "take 1", "src": "11-40-10", "in": 1.2, "out": 9.8},
               {"label": "take 2", "src": "11-42-47", "in": 1.7, "out": 14.3}],
     "choices": ["take 1", "take 2"]},
    {"id": "thanks", "kind": "question", "question": "Leave out the closing thanks?"}
   ]}

"at"/"to" are seconds in review-N.mp4 or a times.py mark (PREFIX[@SRC_TIME]),
resolved against review-N.timeline.json; playback starts "pre" (default 3) s
before "at" and stops at "to". "clips" play ranges of the source clips, for
comparing takes. Every item needs a stable "id". After handling an answer,
add "reply" (shown to the user) and "resolved": true to the item.

The UI autosaves the user's answers to review/responses/review-N.json:
  {"sent": 2, "answers": {ID: {"choice", "comment"}},
   "comments": [{"at", "piece", "src", "src_at", "text"}], "general": "..."}
Pressing "Send to agent" bumps "sent", and `wait` prints a line for it.
"""
import argparse
import json
import mimetypes
import re
import shutil
import sys
import time
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from common import REVIEW, ROOT, clip_path, fmt, in_data, resolve_stem
from times import resolve

RESPONSES = REVIEW / "responses"
UI = ROOT / "ui" / "index.html"
ROUND_RE = re.compile(r"review-(\d+)")


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    tmp.replace(path)


def round_names():
    names = {m.group(0) for p in REVIEW.glob("review-*.json") if (m := ROUND_RE.fullmatch(p.stem))}
    return sorted(names, key=lambda n: int(n.split("-")[1]))


def latest_round():
    names = round_names()
    if not names:
        raise SystemExit("no review rounds yet (review.py publish RENDER)")
    return names[-1]


def load_round(name):
    """The round with "at"/"to" marks resolved to seconds, plus its timeline and response."""
    rnd = read_json(REVIEW / f"{name}.json")
    rnd.setdefault("video", f"{name}.mp4")
    timeline = read_json(REVIEW / rnd.get("timeline", f"{name}.timeline.json"), [])
    for item in rnd.get("items", []):
        for key in ("at", "to"):
            mark = item.get(key)
            if isinstance(mark, str):
                item[key] = resolve(timeline, mark)
                if item[key] is None:
                    item["error"] = f"no piece matches {key} mark '{mark}'"
    response = read_json(RESPONSES / f"{name}.json", {})
    return {"name": name, "round": rnd, "timeline": timeline, "response": response}


def piece_text(timeline, n):
    return timeline[n]["text"] if n is not None and 0 <= n < len(timeline) else ""


# ---- CLI --------------------------------------------------------------------

def cmd_publish(args):
    render = args.render
    names = round_names() + [p.stem for p in REVIEW.glob("review-*.mp4")]
    n = max((int(ROUND_RE.fullmatch(s).group(1)) for s in names if ROUND_RE.fullmatch(s)), default=0) + 1
    name = f"review-{n}"
    REVIEW.mkdir(exist_ok=True)
    shutil.copyfile(render, REVIEW / f"{name}.mp4")
    timeline = render.with_suffix(".timeline.json")
    if timeline.exists():
        shutil.copyfile(timeline, REVIEW / f"{name}.timeline.json")
    shutil.copyfile(args.edl, REVIEW / f"{name}.edl.json")
    write_json(REVIEW / f"{name}.json", {"title": name, "notes": "", "items": []})
    print(f"{name}: fill in the items in {REVIEW / name}.json")


def cmd_show(args):
    name = args.round or latest_round()
    data = load_round(name)
    rnd, timeline, resp = data["round"], data["timeline"], data["response"]
    print(f"== {rnd.get('title') or name}  (sent {resp.get('sent', 0)}x, updated {resp.get('updated', 'never')})")
    answers = resp.get("answers", {})
    for item in rnd.get("items", []):
        where = f" @ {fmt(item['at'])}" if item.get("at") is not None else ""
        state = " [resolved]" if item.get("resolved") else ""
        print(f"\n[{item['id']}]{state} {item.get('kind', '')}{where}  {item.get('title', '')}")
        if item.get("question"):
            print(f"  Q: {item['question']}")
        if item.get("error"):
            print(f"  ERROR: {item['error']}")
        a = answers.get(item["id"], {})
        print(f"  A: {' | '.join(x for x in (a.get('choice'), a.get('comment')) if x) or '(no answer)'}")
    comments = resp.get("comments", [])
    if comments:
        print("\n== comments at a time")
    for c in comments:
        where = f"{fmt(c['at'])} " if c.get("at") is not None else ""
        src = f"{c['src']}@{c['src_at']:.2f}" if c.get("src") else ""
        print(f"  {where}{src}  «{piece_text(timeline, c.get('piece'))[:50]}»\n    {c['text']}")
    if resp.get("general"):
        print(f"\n== general\n  {resp['general']}")


def cmd_wait(args):
    """Print a line whenever the user presses "Send to agent" (never exits)."""
    seen = {}
    first = True
    while True:
        for path in sorted(RESPONSES.glob("review-*.json")):
            if args.round and path.stem != args.round:
                continue
            try:
                resp = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            sent = resp.get("sent", 0)
            if not first and sent > seen.get(path.stem, 0):
                answered = sum(1 for a in resp.get("answers", {}).values() if a.get("choice") or a.get("comment"))
                print(f"SENT {path.stem} #{sent}: {answered} answers, {len(resp.get('comments', []))} comments"
                      f" -> review.py show {path.stem}", flush=True)
            seen[path.stem] = sent
        first = False
        time.sleep(2)


# ---- web server -------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, ctype):
        """Serve a file with HTTP Range support (browsers need it to seek in video)."""
        if not path.is_file():
            return self.send_error(HTTPStatus.NOT_FOUND)
        size = path.stat().st_size
        start, end = 0, size - 1
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
            else:
                start = max(0, size - int(m.group(2)))
            if start > end:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                return self.end_headers()
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        with open(path, "rb") as fh:
            fh.seek(start)
            left = end - start + 1
            try:
                while left > 0 and (chunk := fh.read(min(left, 1 << 20))):
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/":
            return self.send_file(UI, "text/html; charset=utf-8")
        if path == "/api/rounds":
            rounds = []
            for name in round_names():
                rnd = read_json(REVIEW / f"{name}.json")
                resp = read_json(RESPONSES / f"{name}.json", {})
                items = rnd.get("items", [])
                rounds.append({"name": name, "title": rnd.get("title", name), "items": len(items),
                               "open": sum(1 for i in items if not i.get("resolved")),
                               "sent": resp.get("sent", 0),
                               "mtime": (REVIEW / f"{name}.json").stat().st_mtime})
            return self.send_json(rounds)
        if m := re.fullmatch(r"/api/rounds/(review-\d+)", path):
            if not (REVIEW / f"{m.group(1)}.json").exists():
                return self.send_error(HTTPStatus.NOT_FOUND)
            return self.send_json(load_round(m.group(1)))
        if m := re.fullmatch(r"/media/([^/]+\.mp4)", path):
            return self.send_file(REVIEW / m.group(1), "video/mp4")
        if m := re.fullmatch(r"/src/([^/]+)", path):
            try:
                path = clip_path(resolve_stem(m.group(1)))
            except SystemExit:
                return self.send_error(HTTPStatus.NOT_FOUND)
            return self.send_file(path, mimetypes.guess_type(path.name)[0] or "video/mp4")
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_PUT(self):
        """Autosave the user's answers; ?send=1 also counts as "Send to agent"."""
        url = urlparse(self.path)
        m = re.fullmatch(r"/api/responses/(review-\d+)", url.path)
        if not m or not (REVIEW / f"{m.group(1)}.json").exists():
            return self.send_error(HTTPStatus.NOT_FOUND)
        path = RESPONSES / f"{m.group(1)}.json"
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        old = read_json(path, {})
        now = datetime.now().isoformat(timespec="seconds")
        resp = {"round": m.group(1), "updated": now, "sent": old.get("sent", 0), "sent_at": old.get("sent_at"),
                "answers": body.get("answers", {}), "comments": body.get("comments", []),
                "general": body.get("general", "")}
        if parse_qs(url.query).get("send") == ["1"]:
            resp["sent"] += 1
            resp["sent_at"] = now
        write_json(path, resp)
        self.send_json(resp)


def cmd_serve(args):
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"review UI on http://localhost:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("publish")
    p.add_argument("render", nargs="?", type=in_data, default="work/preview.mp4")
    p.add_argument("--edl", type=in_data, default="work/edl.json")
    p = sub.add_parser("serve")
    p.add_argument("--port", type=int, default=8790)
    for cmd in ("show", "wait"):
        sub.add_parser(cmd).add_argument("round", nargs="?")
    args = ap.parse_args()
    {"publish": cmd_publish, "serve": cmd_serve, "show": cmd_show, "wait": cmd_wait}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
