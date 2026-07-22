"""YouDo Photo — AI-отбор фотографий по сходству с эталоном."""

from .pipeline import PhotoSelector
from .similarity import MatchResult

__all__ = ["PhotoSelector", "MatchResult"]
