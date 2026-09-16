"""Snap EDL cut points into real silences (in place), and report the moves.

Usage: venv/bin/python snap.py EDL.json [--db -38] [--maxmove 0.6]

For each piece, "in" moves to just before speech resumes (end of the
nearest silence, minus --lead) and "out" to just after speech stops (start
of the nearest silence, plus --tail). Points with no silence within
--maxmove are left alone and flagged, since that means the cut is mid-speech.
A piece can carry "lock": ["in"] / ["out"] / ["in", "out"] to keep a
deliberate mid-speech cut exactly where it is.
"""
import argparse
import json
import re
import subprocess

from common import WORK, resolve_stem

_cache = {}


def silences(stem, db):
    if stem not in _cache:
        log = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", str(WORK / f"{stem}.wav"),
             "-af", f"silencedetect=noise={db}dB:d=0.25", "-f", "null", "-"],
            capture_output=True, text=True,
        ).stderr
        starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
        ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
        _cache[stem] = list(zip(starts, ends))
    return _cache[stem]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edl")
    ap.add_argument("--db", type=float, default=-38)
    ap.add_argument("--maxmove", type=float, default=0.6)
    ap.add_argument("--lead", type=float, default=0.12)
    ap.add_argument("--tail", type=float, default=0.15)
    args = ap.parse_args()

    pieces = json.load(open(args.edl))
    for n, p in enumerate(pieces):
        sil = silences(resolve_stem(p["src"]), args.db)
        # in: speech should start right after a silence ends
        best = min(sil, key=lambda s: abs(s[1] - p["in"]), default=None)
        if best and abs(best[1] - p["in"]) <= args.maxmove:
            new_in = max(best[0], best[1] - args.lead)
        else:
            new_in = None
        # out: speech should stop right before a silence starts
        best = min(sil, key=lambda s: abs(s[0] - p["out"]), default=None)
        if best and abs(best[0] - p["out"]) <= args.maxmove:
            new_out = min(best[1], best[0] + args.tail)
        else:
            new_out = None
        flags = []
        for key, new in (("in", new_in), ("out", new_out)):
            if key in p.get("lock", []):
                flags.append(f"{key} locked")
            elif new is None:
                flags.append(f"{key} NOT IN SILENCE")
            else:
                if abs(new - p[key]) > 0.005:
                    flags.append(f"{key} {p[key]:.2f}->{new:.2f}")
                p[key] = round(new, 2)
        print(f"{n:3d} {p['src']:>9} {' | '.join(flags) or 'ok'}  {p.get('text', '')[:50]}")

    with open(args.edl, "w") as fh:
        fh.write(json.dumps(pieces, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
