"""Render an edit decision list (EDL) spliced from any number of source clips.

Usage: venv/bin/python render.py EDL.json OUTPUT [--fade 0.03] [--preview] [--jobs 4]

Relative paths are in the project folder, e.g. render.py work/edl.json work/preview.mp4 --preview

EDL.json is a list played in the given order, no sorting:
  [{"src": "11-42-47", "in": 1.68, "out": 14.29, "text": "..."}, ...]
src is a clip stem or unique suffix (its video is looked up in SRC_DIR); "text" and "lock"
are notes for editing/snap.py and ignored here. Optional per piece:
  "gain_db": 20              boost/cut the piece's audio
  "audio": {"src": "12-17-36", "in": 693.6}
                             take the audio from another clip (same duration),
                             e.g. a line spoken over a different slide
  "hold_before": 0.4         freeze the first frame (with silence) this many
                             seconds before the piece starts, for a longer pause

Each piece is cut to its own cached file (work/pieces/, keyed by src/in/out/
fade/quality) with lossless PCM audio and short fades so splices don't click,
then all pieces are joined with the concat demuxer and the audio is encoded
once. Changing one piece only re-renders that piece.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import WORK, clip_path, in_data, resolve_stem

PIECES = WORK / "pieces"

# hardware H.264 on macOS, x264 elsewhere
if sys.platform == "darwin":
    VENC = {True: ["-c:v", "h264_videotoolbox", "-b:v", "2M", "-s", "960x540"],
            False: ["-c:v", "h264_videotoolbox", "-q:v", "65"]}
else:
    VENC = {True: ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-s", "960x540"],
            False: ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]}


def piece_path(p, fade, preview):
    audio = p.get("audio") or {}
    key = (f"{p['stem']}|{p['in']:.3f}|{p['out']:.3f}|{fade}|{preview}"
           f"|{p.get('gain_db', 0)}|{audio.get('src', '')}|{audio.get('in', '')}|{p.get('hold_before', 0)}")
    return PIECES / f"{hashlib.sha1(key.encode()).hexdigest()[:16]}.mkv"


def cut_piece(p, fade, preview):
    dst = piece_path(p, fade, preview)
    if dst.exists():
        return dst
    d = p["out"] - p["in"]
    f = min(fade, d / 4)
    inputs = ["-ss", f"{p['in']:.3f}", "-t", f"{d:.3f}", "-i", str(clip_path(p['stem']))]
    amap = "0:a"
    if p.get("audio"):
        a = p["audio"]
        inputs += ["-ss", f"{a['in']:.3f}", "-t", f"{d:.3f}", "-i", str(clip_path(resolve_stem(a['src'])))]
        amap = "1:a"
    gain = f"volume={p['gain_db']}dB," if p.get("gain_db") else ""
    hold = p.get("hold_before", 0)
    vf = ["-vf", f"tpad=start_duration={hold}:start_mode=clone"] if hold else []
    delay = f",adelay={int(hold * 1000)}:all=1" if hold else ""
    tmp = dst.with_suffix(".part.mkv")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-map", "0:v", "-map", amap, *vf,
         "-af", f"{gain}afade=t=in:d={f},afade=t=out:st={d - f}:d={f}{delay}",
         *VENC[preview], "-r", "30", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(tmp)],
        check=True,
    )
    tmp.rename(dst)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edl", type=in_data)
    ap.add_argument("output", type=in_data)
    ap.add_argument("--fade", type=float, default=0.03)
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()

    pieces = json.load(open(args.edl))
    for p in pieces:
        p["stem"] = resolve_stem(p["src"])
        assert p["out"] > p["in"], p
    PIECES.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(args.jobs) as pool:
        files = list(pool.map(lambda p: cut_piece(p, args.fade, args.preview), pieces))

    # real start time of every piece in the output (concat advances by each file's duration)
    t, timeline = 0.0, []
    for p, f in zip(pieces, files):
        timeline.append({"start": round(t, 3), "src": p["src"], "in": p["in"], "text": p.get("text", "")})
        t += float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout)
    Path(args.output).with_suffix(".timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=1) + "\n")

    listing = WORK / "concat.txt"
    listing.write_text("".join(f"file '{f}'\n" for f in files))
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", str(args.output)],
        check=True,
    )
    total = sum(p["out"] - p["in"] for p in pieces)
    print(f"{len(pieces)} pieces, {total / 60:.1f} min -> {args.output}")


if __name__ == "__main__":
    main()
