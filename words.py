"""Print word-level timestamps for a clip, optionally within a time window.

Usage: venv/bin/python words.py CLIP [FROM [TO]]
       venv/bin/python words.py CLIP --stretched [SECONDS]

CLIP is a stem or suffix (e.g. 11-45-45); FROM/TO are seconds.
Gaps >= 0.4 s between words are marked so pauses/restarts stand out.
--stretched lists words lasting >= SECONDS (default 1.2): a full-file
Whisper pass often hides a restart or pause inside such a word, so
check each one with snippet.py.
"""
import sys

from common import load, resolve_stem


def all_words(stem):
    for seg in load(stem)["segments"]:
        for w in seg.get("words", []):
            yield seg, w


def stretched(stem, limit):
    for seg, w in all_words(stem):
        if w["end"] - w["start"] >= limit:
            print(f"{w['start']:7.2f}-{w['end']:7.2f} ({w['end'] - w['start']:.1f}s) "
                  f"{w['word'].strip()}  | {seg['text'].strip()[:70]}")


def window(stem, lo, hi):
    prev_end = None
    for _, w in all_words(stem):
        if not lo <= w["start"] <= hi:
            continue
        if prev_end is not None and w["start"] - prev_end >= 0.4:
            print(f"        ~~ {w['start'] - prev_end:.2f}s gap")
        print(f"{w['start']:7.2f}-{w['end']:7.2f} {w['word'].strip()}  ({w.get('probability', 0):.2f})")
        prev_end = w["end"]


def main():
    stem = resolve_stem(sys.argv[1])
    if len(sys.argv) > 2 and sys.argv[2] == "--stretched":
        stretched(stem, float(sys.argv[3]) if len(sys.argv) > 3 else 1.2)
        return
    lo = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    hi = float(sys.argv[3]) if len(sys.argv) > 3 else float("inf")
    window(stem, lo, hi)


if __name__ == "__main__":
    main()
