"""
Services package for VCBot.

This package contains service modules that encapsulate business logic,
separating it from Discord interaction handling.
"""

from .ai_service import AIService, AIResponse
from .bill_service import BillService, BillResult
from .reference_service import ReferenceService

__all__ = [
    'AIService',
    'AIResponse',
    'BillService',
    'BillResult',
    'ReferenceService',
]