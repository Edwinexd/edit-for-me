# edit-for-me

Talk/lecture video editing. Transcribe the raw recording clips, make the editorial cut by hand (pick the best take of each sentence, splice across clips and retakes), have the user review it in the review web UI, and render.

This repo is the tool. It is cloned once and pointed at any number of recordings, so nothing project-specific goes in it: never edit the code, this file or the README for a project, and never write project state here.

## Projects
- `project.py MATERIALS_DIR [--lang sv] [--asr …]` selects the project. The tools then work on it, and all of its output goes in its data folder (`MATERIALS_DIR/edit-for-me/` by default): `project.json` (settings), `work/`, `review/` and `STATUS.md`. `project.py` with no arguments shows the current project. Run it at the start of every session.
- Relative file arguments (`work/edl.json`, `work/preview.mp4`) are resolved inside the data folder, not the current directory.
- Keep the project's state in its `STATUS.md`: what is being edited, special requests, clip quirks found (e.g. "12-58-18 ends on an old outro, cut at 364.45 s"), the current review round, the user's decisions and preferences, and what is signed off. Update it after every step, so that a fresh session can pick up from `STATUS.md` alone.

## Setup
- `venv/` is Python 3.12: `python3.12 -m venv venv && venv/bin/pip install -r requirements.txt`. `requirements.txt` lists only the top-level dependencies, pinned by hand with platform markers. Keep it up to date, but don't overwrite it with `pip freeze`.
- Needs `ffmpeg` and `ffprobe` on PATH. `render.py` encodes with `h264_videotoolbox` on macOS and `libx264` elsewhere.
- Speech recognition (`asr.py`, set per project with `project.py --asr`, default `auto`): mlx-whisper on Apple Silicon, faster-whisper (CPU or CUDA) everywhere else. Both give the same Whisper-style JSON, and the model per backend is in `MODELS` in `common.py`.
- Clips are the video files directly inside the materials folder, in any common format (`VIDEO_EXTS`). The review page plays whatever the browser supports. When the filenames are recording timestamps, sorted order is recording order.

## Tools
- `watch.py [--interval SECS]` transcribes each clip in the materials folder once it has finished downloading. Run it in the background and act on its READY/DONE/FAILED lines (e.g. under Monitor in Claude Code).
- `transcribe.py [FILE...]` (no arguments: every clip) writes `work/<stem>.json` (word timestamps), `.txt` (numbered segments) and `.wav` (16 kHz mono). Files already transcribed are skipped.
- `words.py CLIP [FROM [TO]]` prints word timings and gaps. CLIP can be a unique suffix such as `11-45-45`.
- `words.py CLIP --stretched` lists words lasting 1.2 s or more, which usually hide restarts. Check each one with `snippet.py`.
- `snippet.py CLIP FROM TO [...]` re-transcribes short stretches in isolation. This is the ground truth for what was actually said (see below).
- `rms.py CLIP T [...]` prints a loudness profile around a point, for placing mid-speech cuts.
- `snap.py [work/edl.json]` moves each in/out point into the nearest real silence (ffmpeg silencedetect) and edits the file in place. Pieces with `"lock": ["in"|"out"]` are left untouched.
- `render.py work/edl.json OUT.mp4 [--preview]` cuts each piece to `work/pieces/` (cached) with PCM audio and 30 ms fades, concatenates them, and writes `OUT.timeline.json` (where every piece starts in the output). Optional per-piece settings:
  - `"gain_db"` changes the level (e.g. a quiet closing line).
  - `"audio": {"src", "in"}` plays audio from another clip over this piece's video (e.g. a line spoken over a different slide).
  - `"hold_before": seconds` freezes the first frame over silence to lengthen a pause. Only use it on full-screen slides, where the presenter is off camera.
- `times.py [--timeline F] PREFIX[@SRC_TIME]` prints exact positions in a render from its timeline (default: `work/preview.timeline.json`). Never use frame-rounded sums, which drift.
- `review.py` runs the review rounds (details under "Review with the user"): `publish [work/preview.mp4]`, `serve [--port]`, `wait [ROUND]`, `show [ROUND]`. The UI is `ui/index.html`.

## Editing rules (the editorial work is done by hand, never grouped automatically)
- Read every transcript. For each retake, use the final complete take unless an earlier one is better, and splice halves of sentences across takes when neither take is clean on its own.
- Cut false starts, trailing-off fragments, the speaker muttering to themselves, and repeated content. Trim hesitation pauses of 1.5 s or more that fall in the middle of a sentence.
- Whisper word times can be off by up to about 0.5 s. Use the silencedetect map as the ground truth for where speech starts and stops, but soft onsets (an F, or a quiet "thanks") can fall below -38 dB. Check them with `rms.py`.
- A full-file Whisper pass collapses restarts: a single word "stretched" over several seconds, or speech in the silence map that has no words, usually hides a retake or a misspoken word. Always `snippet.py` those stretches before splicing across them.
- For a cut that has to fall mid-speech, cut in the RMS dip between words. Watch out for stop-consonant closures (the silent p in "A-pache"): they look like gaps but are inside a word.
- Whisper hallucinates text over trailing silence (typically subtitle credits or "thanks for watching"). Drop it.
- The EDL is `work/edl.json`, an ordered list of `{"src", "in", "out", "text", "lock"?}` played in that order. `text` is a short summary of the piece ("First words ... last words."); `times.py` and review marks match on its start, so keep the starts unique.
- Check the first and last seconds of every clip that is used at an edge: recordings often start or end on a desktop, the recording software, or an old outro.

## QA
- After a round of edits: `snap.py`, render with `--preview` to `work/preview.mp4`, delete the old `work/preview.json`/`.txt`/`.wav`, run `transcribe.py work/preview.mp4`, and read the whole transcript for doubled or clipped words and wrong content. `snippet.py preview A B` works on the preview too.

## Review with the user
- `review.py publish` copies `work/preview.mp4`, its timeline and the EDL to `review/review-N.*` (so the times stay fixed while editing continues) and writes a skeleton `review/review-N.json`. Fill in its `notes` (what changed) and `items`: every risky join, content decision and open question, each with a stable `id`, `kind`, `title`, `question`, optional `choices`, and `at`/`to` (seconds or a `times.py` mark like `"Formatet@15.62"`) or `clips` (source ranges, for comparing takes). The item format is in the `review.py` docstring. Run `review.py show` to check that every mark resolves.
- Questions that have no render yet (e.g. "which of these takes?") also go in a round as items with `clips`, not in chat.
- Keep `review.py serve` running in the background and give the user the URL (http://localhost:8765/). They click an item to play exactly that spot, answer it, add comments at any time, then press "Send to agent". Run `review.py wait` in the background too (e.g. under Monitor in Claude Code). Each `SENT review-N` line means read `review.py show review-N` and act on it.
- Answers are autosaved to `review/responses/review-N.json`. After handling an item, add `"reply"` (what you did, e.g. "redone in review-3") and `"resolved": true` to it in `review-N.json`. The UI picks up edits and new rounds on its own.
- Record the user's decisions and any new standing preferences in `STATUS.md`.

## Defaults from earlier projects
- Seams at pauses sound best. Mid-word joins between different takes often sound off, so splice whole takes at silences.
- Final render: 1080p (`render.py work/edl.json work/final.mp4` without `--preview`), only after the user signs off.
