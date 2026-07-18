"""ASR engine base classes — independent of PPTAgent."""

from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Optional


@dataclass
class ASRResult:
    """Unified output for all ASR engines. Matches SURF manual Section 11.1 format."""

    utterance_id: str
    asr_id: str  # "ASR-1", "ASR-2", ...
    transcript: str
    language: str = "en"
    segments: list = field(default_factory=list)
    word_timestamps: list = field(default_factory=list)
    confidence: list = field(default_factory=list)
    decode_config: dict = field(default_factory=dict)
    duration_sec: float = 0.0
    error: Optional[str] = None


class BaseASREngine(ABC):
    """Every ASR engine inherits from this."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self._model = None

    @property
    @abstractmethod
    def asr_id(self) -> str:
        """Return the SURF ASR ID, e.g. 'ASR-2'."""
        ...

    @abstractmethod
    def transcribe(self, audio_path: str, **kwargs) -> ASRResult:
        """Transcribe an audio file. Return ASRResult."""
        ...
