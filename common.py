"""Shared paths, settings and transcript helpers for the current project (see project.py)."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
_current = ROOT / ".project"
if not _current.exists():
    raise SystemExit("No project selected. Run: venv/bin/python project.py MATERIALS_DIR [--lang LANG]")

DATA = Path(_current.read_text().strip())
_settings = json.loads((DATA / "project.json").read_text())
SRC_DIR = Path(_settings["src"])
LANG = _settings.get("lang")
ASR = _settings.get("asr", "auto")
WORK = DATA / "work"
REVIEW = DATA / "review"

# the Whisper model each speech recognition backend uses (see asr.py)
MODELS = {"mlx": "mlx-community/whisper-large-v3-turbo", "faster-whisper": "large-v3-turbo"}

VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi")


def in_data(path):
    """File arguments: relative paths (e.g. work/edl.json) are relative to the project's DATA folder."""
    path = Path(path).expanduser()
    return path if path.is_absolute() else DATA / path


def fmt(t):
    m, s = divmod(t, 60)
    h, m = divmod(int(m), 60)
    return f"{h:d}:{m:02d}:{s:05.2f}"


def load(stem):
    return json.loads((WORK / f"{stem}.json").read_text())


def all_stems():
    """Transcribed clips in recording order (filenames are timestamps)."""
    return sorted(p.stem for p in WORK.glob("*.json") if not p.stem.endswith((".edl", ".timeline")))


def resolve_stem(name):
    """Accept a full stem or a unique suffix like '11-45-45'."""
    matches = [s for s in all_stems() if s == name or s.endswith(name)]
    if len(matches) != 1:
        raise SystemExit(f"'{name}' matches {matches or 'nothing'}")
    return matches[0]


def clips():
    """Video files in SRC_DIR, in recording order."""
    return sorted(p for p in SRC_DIR.iterdir() if p.suffix.lower() in VIDEO_EXTS) if SRC_DIR.is_dir() else []


def clip_path(stem):
    """The source video for a transcribed clip stem."""
    for p in clips():
        if p.stem == stem:
            return p
    raise SystemExit(f"no video for '{stem}' in {SRC_DIR}")
