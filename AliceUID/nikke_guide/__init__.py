"""Extensible multi-author Blablalink guide query system."""
from .registry import CATEGORY_LABELS, GuideAuthor, SYUEN_AUTHOR, load_authors
from .service import GuideResult, GuideService, get_guide_service
from .commands import setup

__all__ = [
    'CATEGORY_LABELS',
    'GuideAuthor',
    'GuideResult',
    'GuideService',
    'SYUEN_AUTHOR',
    'get_guide_service',
    'load_authors',
    'setup',
]
