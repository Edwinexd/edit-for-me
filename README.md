# edit-for-me

Turn raw recording clips of a talk or lecture (retakes, false starts, pauses and all) into one clean video with a coding agent. The agent transcribes the clips with Whisper, makes the editorial cut by hand in an edit decision list (EDL), renders it with ffmpeg, and asks you to check it in a small local review page. There you click an item to play exactly that spot, answer it, and send your answers back.

## Requirements
- Python 3.12, and `ffmpeg`/`ffprobe` on PATH
- Transcription uses Whisper: mlx-whisper on Apple Silicon, faster-whisper (CPU, or CUDA if present) everywhere else. `requirements.txt` installs the right one. Set `ASR` in `common.py` to force one.
- Rendering uses `h264_videotoolbox` on macOS and `libx264` elsewhere.

```sh
python3.12 -m venv venv && venv/bin/pip install -r requirements.txt
```

## Start a project
1. Copy this repo, e.g. `cp -R edit-for-me-template my-lecture` (or use it as a GitHub template).
2. Put the clips in one folder (mp4/mov/mkv/…). Timestamp filenames sort into recording order.
3. Start an agent (Claude Code, Codex, …) in the copy and give it the prompt below, filled in.

## The prompt

```text
You are editing a recorded talk into a finished video, working in this repo.
Read AGENTS.md first and follow it exactly. STATUS.md holds the project state:
read it now and keep it up to date after every step. AGENTS.md is instructions
only, so never write state there.

The project:
- Recording: <what it is, e.g. "a 35-minute lecture on generative AI for course X">
- Clips: <folder, e.g. ~/Downloads/genai> (<all downloaded | still downloading>)
- Language: <e.g. Swedish>
- Special requests: <e.g. "use the outro from clip 14-32-21", "cut the Q&A", or "none">

Work like this:
1. Set SRC_DIR and LANG in common.py, fill in STATUS.md, and check that venv/
   works (see Setup in AGENTS.md).
2. Transcribe every clip. If clips are still downloading, run watch.py in the
   background and watch its output.
3. Read every transcript in full and build work/edl.json by hand, following
   the editing rules: the best (usually the last complete) take of every
   sentence, splices across takes at silences, no false starts, repeats,
   muttering or hallucinated text. Check stretched words, restarts and the
   edges of every clip with snippet.py and rms.py. Never group or cut
   automatically with a script.
4. Run snap.py, render a preview, transcribe the preview and read all of it.
   Fix everything you find before showing me anything.
5. Publish a review round (review.py publish). Fill in its notes and items:
   every risky join, every content decision, and every question you have for
   me, each with a mark so I can jump straight to it (use clips to compare
   takes). Check it with review.py show. Start review.py serve in the
   background, give me the URL, and run review.py wait in the background,
   watching its output for SENT lines.
   Put questions in the review round, not in chat.
6. When I send answers: read them with review.py show, apply them, give each
   handled item a reply and mark it resolved, record my decisions in
   STATUS.md, and publish the next round. Repeat until I sign off.
7. After I sign off, render work/final.mp4 at full quality and tell me its
   path and length.

Don't commit anything unless I ask.
```

## The review page
`venv/bin/python review.py serve` opens on http://localhost:8765/. It shows the latest round (older rounds are in the dropdown):
- **To check**: the agent's items. **▶ time** plays from a few seconds before the spot and stops at the item's end, so you never have to scrub. Take comparisons play the source clips. Answer with the choice buttons and/or a comment.
- **Comments at a time**: press `c` (or click the comment box) anywhere in the video to pause and leave a note at that moment. The agent gets the time, the EDL piece and the source-clip time.
- **Send to agent**: answers autosave to `review/responses/review-N.json` as you go. Sending tells the agent (`review.py wait`) that they're ready. You can send more than once.
- The progress bar marks piece boundaries (ticks), open items (orange, green once answered) and your comments (blue). Keys: `space` play/pause, `←`/`→` ±2 s, `n`/`p` next/previous item.
- When the agent replies to or resolves items, or publishes a new round, the page updates on its own.

## Layout
| Path | What |
| --- | --- |
| `AGENTS.md` (`CLAUDE.md` links to it) | Instructions for the agent: tools, editing rules, the review loop |
| `STATUS.md` | Project state, kept up to date by the agent |
| `common.py` | Paths and settings: `SRC_DIR`, `LANG`, `ASR` |
| `asr.py`, `transcribe.py`, `watch.py`, `words.py`, `snippet.py`, `rms.py` | Transcription and inspection |
| `snap.py`, `render.py`, `times.py` | EDL → video |
| `review.py`, `ui/index.html` | Review rounds: publish, serve, wait, show |
| `work/` | Transcripts, audio, EDL, piece cache, renders (ignored by git) |
| `review/` | Frozen review renders, rounds and your responses (ignored by git) |
