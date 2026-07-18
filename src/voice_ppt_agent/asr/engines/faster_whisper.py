"""ASR-2: faster-whisper large-v3-turbo engine."""

import time
from pathlib import Path
from typing import Optional

from ..engine import ASRResult, BaseASREngine

# A portable default; override with --model-cache or VOICE_PPT_MODEL_CACHE.
DEFAULT_MODEL_ROOT = Path.home() / ".cache" / "voice-to-ppt-agent" / "faster-whisper"


class FasterWhisperEngine(BaseASREngine):
    """faster-whisper large-v3-turbo (ASR-2).

    Also supports large-v3 (ASR-1) by passing model_size="large-v3".
    """

    asr_id = "ASR-2"

    def __init__(
        self,
        model_size: str = "large-v3-turbo",
        model_root: Optional[Path] = None,
        device: str = "auto",
        compute_type: str = "auto",
        beam_size: int = 5,
    ):
        super().__init__(model_path=str(model_root or DEFAULT_MODEL_ROOT))
        self.model_size = model_size
        self.model_root = str(model_root or DEFAULT_MODEL_ROOT)
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self._model = None  # lazy init

    def _load_model(self):
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            self.model_size,
            download_root=self.model_root,
            device=self.device,
            compute_type=self.compute_type,
        )

    def transcribe(self, audio_path: str, utterance_id: str = "", language: str = None, **kwargs) -> ASRResult:
        """Transcribe audio. Set language=None for auto-detect."""
        t0 = time.time()
        audio_path = str(audio_path)
        try:
            self._load_model()
            segments_raw, info = self._model.transcribe(
                audio_path,
                language=language,
                beam_size=kwargs.get("beam_size", self.beam_size),
                vad_filter=kwargs.get("vad_filter", True),
                **{k: v for k, v in kwargs.items() if k not in ("beam_size", "vad_filter")},
            )
        except Exception as exc:
            return ASRResult(
                utterance_id=utterance_id,
                asr_id=self.asr_id,
                transcript="",
                language=language or "en",
                duration_sec=round(time.time() - t0, 3),
                error=str(exc),
            )

        segments = list(segments_raw)
        transcript = " ".join(seg.text.strip() for seg in segments if seg.text.strip())

        word_timestamps = []
        confidence_list = []
        for seg in segments:
            if seg.words:
                for w in seg.words:
                    word_timestamps.append({
                        "word": w.word,
                        "start": round(w.start, 3),
                        "end": round(w.end, 3),
                        "probability": round(w.probability, 3),
                    })
                    confidence_list.append(w.probability)

        duration = time.time() - t0
        avg_conf = round(sum(confidence_list) / len(confidence_list), 3) if confidence_list else None

        return ASRResult(
            utterance_id=utterance_id,
            asr_id=self.asr_id,
            transcript=transcript,
            language=info.language,
            segments=[
                {
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                    "text": seg.text.strip(),
                }
                for seg in segments
            ],
            word_timestamps=word_timestamps,
            confidence=[avg_conf] if avg_conf is not None else [],
            decode_config={
                "model": f"faster-whisper {self.model_size}",
                "beam_size": self.beam_size,
                "device": self.device,
                "compute_type": self.compute_type,
            },
            duration_sec=round(duration, 3),
        )
