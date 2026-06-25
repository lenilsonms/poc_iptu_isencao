"""Camada de configuração: schemas tipados e loader com validação de versões."""
from .loader import ConfigLoader
from .schemas import (
    AppConfig,
    BusinessRulesConfig,
    ChecklistConfig,
    ChecklistItemConfig,
    ConclusionMappingConfig,
    LegalReferencesConfig,
)

__all__ = [
    "ConfigLoader",
    "AppConfig",
    "BusinessRulesConfig",
    "ChecklistConfig",
    "ChecklistItemConfig",
    "ConclusionMappingConfig",
    "LegalReferencesConfig",
]
