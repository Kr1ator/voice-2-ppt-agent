"""ASR-6: Qwen3-ASR-1.7B engine.

Uses the official `qwen-asr` SDK.
"""

import time
from pathlib import Path
from typing import Optional

from ..engine import ASRResult, BaseASREngine

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "voice-to-ppt-agent" / "qwen3-asr"

# The qwen-asr SDK uses the original repo (not -hf variant)
MODEL_ID = "Qwen/Qwen3-ASR-1.7B"
MODEL_ID_0_6B = "Qwen/Qwen3-ASR-0.6B"


class QwenASREngine(BaseASREngine):
    """Qwen3-ASR-1.7B (ASR-6), using the official qwen-asr SDK.

    For the smaller variant pass model_id='Qwen/Qwen3-ASR-0.6B'.
    """

    asr_id = "ASR-6"

    def __init__(
        self,
        model_id: str = MODEL_ID,
        cache_dir: Optional[Path] = None,
        device: str = "auto",
        torch_dtype: str = "auto",
        max_new_tokens: int = 512,
    ):
        super().__init__(model_path=str(cache_dir or DEFAULT_CACHE_DIR))
        self.model_id = model_id
        self.cache_dir = str(cache_dir or DEFAULT_CACHE_DIR)
        self.device = device
        self.torch_dtype = torch_dtype
        self.max_new_tokens = max_new_tokens
        self._model = None

    def _resolve_device(self):
        """Pick the best available device: cuda > mps > cpu."""
        import torch

        if self.device != "auto":
            return self.device, self.torch_dtype

        if torch.cuda.is_available():
            return "cuda:0", "bfloat16"
        elif torch.backends.mps.is_available():
            # MPS doesn't support bfloat16; use float32
            return "mps", "float32"
        else:
            return "cpu", "float32"

    def _load_model(self):
        if self._model is not None:
            return

        import os
        import logging
        import torch
        from qwen_asr import Qwen3ASRModel

        # Suppress HuggingFace progress bars & warnings during load
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
        logging.getLogger("transformers").setLevel(logging.ERROR)
        logging.getLogger("qwen_asr").setLevel(logging.ERROR)
        logging.getLogger("tqdm").setLevel(logging.WARNING)

        device_str, dtype_str = self._resolve_device()

        dtype = getattr(torch, dtype_str) if dtype_str in ("float32", "bfloat16", "float16") else torch.float32

        self._model = Qwen3ASRModel.from_pretrained(
            self.model_id,
            dtype=dtype,
            device_map=device_str,
            cache_dir=self.cache_dir,
            max_new_tokens=self.max_new_tokens,
        )

    def transcribe(self, audio_path: str, utterance_id: str = "", language: str = None, **kwargs) -> ASRResult:
        t0 = time.time()
        audio_path = str(audio_path)

        try:
            self._load_model()
            results = self._model.transcribe(
                audio=audio_path,
                language=language,
            )
            r = results[0]
            transcript = r.text
            lang = r.language or "en"
        except Exception as exc:
            return ASRResult(
                utterance_id=utterance_id,
                asr_id=self.asr_id,
                transcript="",
                language=language or "en",
                duration_sec=round(time.time() - t0, 3),
                error=str(exc),
            )

        duration = time.time() - t0

        return ASRResult(
            utterance_id=utterance_id,
            asr_id=self.asr_id,
            transcript=transcript.strip() if transcript else "",
            language=lang,
            decode_config={
                "model": self.model_id,
                "device": str(self._model.device) if hasattr(self._model, "device") else self.device,
                "dtype": self.torch_dtype,
                "max_new_tokens": self.max_new_tokens,
            },
            duration_sec=round(duration, 3),
        )
