"""Choose the project the tools work on: a folder of recording clips.

Usage: venv/bin/python project.py MATERIALS_DIR [--lang sv] [--asr auto|mlx|faster-whisper] [--data DIR]
       venv/bin/python project.py              (show the current project)

Everything a project produces (settings, transcripts, renders, review rounds,
STATUS.md) goes in its data folder, MATERIALS_DIR/edit-for-me by default, and
never in this repo. The repo only remembers which project is current, in the
gitignored .project file. Run this again on an old project to switch back:
its settings are kept in DATA/project.json, and flags update them.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent
CURRENT = ROOT / ".project"

STATUS = """# Status

## Project
- Recording:
- Special requests:

## Clip notes

## Current round

## Decisions and preferences

## Signed off
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("materials", nargs="?")
    ap.add_argument("--lang", help="Whisper language code, e.g. sv, en (omit to autodetect)")
    ap.add_argument("--asr", choices=["auto", "mlx", "faster-whisper"])
    ap.add_argument("--data", help="where the project's output goes (default MATERIALS/edit-for-me)")
    args = ap.parse_args()

    if args.materials:
        src = Path(args.materials).expanduser().resolve()
        if not src.is_dir():
            raise SystemExit(f"{src} is not a folder")
        data = Path(args.data).expanduser().resolve() if args.data else src / "edit-for-me"
        data.mkdir(parents=True, exist_ok=True)
        settings_path = data / "project.json"
        settings = json.loads(settings_path.read_text()) if settings_path.exists() else {"lang": None, "asr": "auto"}
        settings["src"] = str(src)
        settings.update({k: v for k, v in (("lang", args.lang), ("asr", args.asr)) if v})
        settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=1) + "\n")
        if not (data / "STATUS.md").exists():
            (data / "STATUS.md").write_text(STATUS)
        CURRENT.write_text(f"{data}\n")
    elif not CURRENT.exists():
        raise SystemExit("no project yet: project.py MATERIALS_DIR [--lang LANG]")

    data = Path(CURRENT.read_text().strip())
    settings = json.loads((data / "project.json").read_text())
    print(f"project: {data}\n  clips: {settings['src']}\n  lang:  {settings['lang'] or 'autodetect'}"
          f"\n  asr:   {settings['asr']}\n  state: {data / 'STATUS.md'}")


if __name__ == "__main__":
    main()
