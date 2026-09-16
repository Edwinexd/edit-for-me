"""Print where pieces start in a render (from the OUTPUT.timeline.json render.py writes).

Usage: venv/bin/python times.py [--timeline FILE] PREFIX[@SRC_TIME] [...]

Defaults to work/preview.timeline.json. PREFIX matches the start of a
piece's "text". With @SRC_TIME (source seconds inside that piece) the time
of that moment is printed instead of the piece start, e.g.
"Sammanfattningsvis@285.88". Review rounds accept the same marks as "at".
"""
import argparse
import json

from common import WORK, fmt, in_data


def resolve(timeline, mark):
    """Output seconds of a PREFIX[@SRC_TIME] mark, or None if no piece matches."""
    prefix, _, src_t = mark.partition("@")
    p = next((p for p in timeline if p["text"].startswith(prefix)), None)
    if p is None:
        return None
    return p["start"] + (float(src_t) - p["in"] if src_t else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", type=in_data, default=str(WORK / "preview.timeline.json"))
    ap.add_argument("marks", nargs="+")
    args = ap.parse_args()

    timeline = json.load(open(args.timeline))
    for arg in args.marks:
        at = resolve(timeline, arg)
        if at is None:
            print(f"   ?      {arg} (no such piece)")
        else:
            print(f"{fmt(at)[2:10]}  {arg}")


if __name__ == "__main__":
    main()
