"""Transcribe each clip in SRC_DIR once it has finished downloading (keeps running; each output line is an event).

Usage: venv/bin/python watch.py [--interval 30]

A clip is ready when its size stayed the same for one poll interval and
ffprobe can read it. Prints READY/DONE/FAILED per clip (a failed clip is
not retried until restart), and never exits.
"""
import argparse
import subprocess
import time

from common import LANG, WORK, clips
from transcribe import transcribe


def readable(path):
    return subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                          capture_output=True).returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=30)
    args = ap.parse_args()

    last, failed = {}, set()
    while True:
        for path in clips():
            if path in failed or (WORK / f"{path.stem}.json").exists():
                continue
            size = path.stat().st_size
            if size and last.get(path) == size and readable(path):
                print(f"READY {path.stem}", flush=True)
                try:
                    transcribe(path, LANG)
                    print(f"DONE {path.stem}", flush=True)
                except Exception as e:
                    failed.add(path)
                    print(f"FAILED {path.stem}: {e}", flush=True)
            last[path] = size
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
