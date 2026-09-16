"""Print a loudness (RMS dB) profile around points in a clip, to place mid-speech cuts.

Usage: venv/bin/python rms.py CLIP T [T ...] [--half 0.5] [--step 0.02]

Cut in the dip between words. Beware of stop-consonant closures (p/t/k/g),
which are just as quiet but sit inside a word; cross-check with snippet.py.
"""
import argparse

import numpy as np

from common import resolve_stem
from snippet import load_audio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("points", nargs="+", type=float)
    ap.add_argument("--half", type=float, default=0.5)
    ap.add_argument("--step", type=float, default=0.02)
    args = ap.parse_args()

    audio, sr = load_audio(resolve_stem(args.clip))
    hop = int(sr * args.step)
    for t in args.points:
        print(f"=== around {t}")
        for s in np.arange(t - args.half, t + args.half, args.step):
            x = audio[int(s * sr):int(s * sr) + hop]
            if not len(x):
                print(f"{s:8.2f}  (past end of audio)")
                break
            db = 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)
            print(f"{s:8.2f} {db:4.0f} {'#' * max(0, int((db + 70) / 2))}")


if __name__ == "__main__":
    main()
