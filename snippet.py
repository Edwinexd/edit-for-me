"""Re-transcribe short stretches of a clip in isolation.

Usage: venv/bin/python snippet.py CLIP FROM TO [FROM TO ...]

A full-file Whisper pass often collapses restarts and drops words (for
example one word "stretched" over several seconds hides a whole retake).
Transcribing just the stretch shows what was actually said. Word times are
printed in source seconds.
"""
import sys
import wave

import numpy as np

import asr
from common import LANG, WORK, resolve_stem


def load_audio(stem):
    w = wave.open(str(WORK / f"{stem}.wav"))
    return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768, w.getframerate()


def main():
    stem = resolve_stem(sys.argv[1])
    bounds = [float(x) for x in sys.argv[2:]]
    audio, sr = load_audio(stem)
    for lo, hi in zip(bounds[::2], bounds[1::2]):
        r = asr.transcribe(audio[int(lo * sr):int(hi * sr)], LANG)
        words = [f"{w['start'] + lo:.2f}:{w['word'].strip()}" for s in r["segments"] for w in s.get("words", [])]
        print(f"=== {lo}-{hi}: {' '.join(words) or '(nothing)'}")


if __name__ == "__main__":
    main()
