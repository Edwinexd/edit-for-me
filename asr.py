"""Speech recognition backends, all returning Whisper-style results.

transcribe(audio, lang) takes a 16 kHz mono file path or float32 numpy array
and returns {"text", "language", "segments": [{"start", "end", "text",
"words": [{"start", "end", "word", "probability"}]}]}.

ASR in common.py picks the backend:
  "mlx"             mlx-whisper (Apple Silicon)
  "faster-whisper"  faster-whisper (CPU or CUDA, any platform)
  "auto"            mlx on Apple Silicon, faster-whisper elsewhere
"""
import platform
import sys

from common import ASR, MODELS


def backend():
    if ASR != "auto":
        return ASR
    return "mlx" if sys.platform == "darwin" and platform.machine() == "arm64" else "faster-whisper"


def transcribe(audio, lang):
    name = backend()
    if name == "mlx":
        import mlx_whisper
        return mlx_whisper.transcribe(audio, path_or_hf_repo=MODELS[name], language=lang,
                                      word_timestamps=True, condition_on_previous_text=False)
    if name == "faster-whisper":
        return _faster_whisper(audio, lang)
    raise SystemExit(f"unknown ASR backend '{name}'")


_fw_model = None


def _faster_whisper(audio, lang):
    global _fw_model
    from faster_whisper import WhisperModel
    if _fw_model is None:
        _fw_model = WhisperModel(MODELS["faster-whisper"], device="auto", compute_type="default")
    segments, info = _fw_model.transcribe(audio, language=lang, word_timestamps=True,
                                          condition_on_previous_text=False)
    segments = [{"start": float(s.start), "end": float(s.end), "text": s.text,
                 "words": [{"start": float(w.start), "end": float(w.end), "word": w.word,
                            "probability": float(w.probability)}
                           for w in s.words or []]}
                for s in segments]
    return {"text": "".join(s["text"] for s in segments), "language": info.language, "segments": segments}
