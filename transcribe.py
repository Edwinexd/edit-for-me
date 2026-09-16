"""Transcribe a video/audio file with word-level timestamps.

Usage: venv/bin/python transcribe.py [INPUT ...] [--lang LANG]

Without inputs, transcribes every clip in the project. Relative inputs are in the
project folder (e.g. work/preview.mp4).

Already-transcribed inputs are skipped. Writes work/<stem>.json (full whisper output), work/<stem>.txt
(readable, one segment per line with [start-end] and segment id) and work/<stem>.wav (16 kHz mono).
The backend is the project's asr setting (project.py --asr); models are in MODELS in common.py.
"""
import argparse
import json
import subprocess

import asr
from common import LANG, WORK, clips, fmt, in_data


def extract_audio(src, dst):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
         "-vn", "-ac", "1", "-ar", "16000", str(dst)],
        check=True,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="*", type=in_data)
    ap.add_argument("--lang", default=LANG, help="e.g. en, sv; defaults to the project's lang")
    args = ap.parse_args()

    for src in args.inputs or clips():
        if (WORK / f"{src.stem}.json").exists():
            print(f"skip {src.name} (already transcribed)")
            continue
        transcribe(src, args.lang)


def transcribe(src, lang):
    WORK.mkdir(parents=True, exist_ok=True)
    wav = WORK / f"{src.stem}.wav"
    if not wav.exists():
        extract_audio(src, wav)

    result = asr.transcribe(str(wav), lang)

    (WORK / f"{src.stem}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
    lines = [
        f"#{i} [{fmt(s['start'])}-{fmt(s['end'])}] {s['text'].strip()}"
        for i, s in enumerate(result["segments"])
    ]
    (WORK / f"{src.stem}.txt").write_text("\n".join(lines) + "\n")
    print(f"{len(lines)} segments -> {WORK / (src.stem + '.txt')}", flush=True)


if __name__ == "__main__":
    main()
