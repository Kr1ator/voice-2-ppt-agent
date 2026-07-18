"""ASR interfaces. Concrete engines are imported lazily by the CLI."""

from .engine import ASRResult, BaseASREngine

__all__ = ["ASRResult", "BaseASREngine"]
