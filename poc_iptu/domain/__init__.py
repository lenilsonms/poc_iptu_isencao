"""Camada de domínio: enums, modelos e erros. Pura, sem I/O."""
from .enums import (
    BenefitType,
    ChecklistStatus,
    ConclusionStatus,
    IncomeStatus,
    LegalRegimeId,
    PropertyRelationshipType,
)
from .errors import ConfigValidationError, PocIptuError, RegimeSelectionError
from .models import (
    ChecklistItemResult,
    ConclusionResult,
    IncomeAnalysis,
    ProcessAnalysisInput,
    PropertyQualification,
    RequestIdentification,
    SelectedRegime,
)
from .pipeline_models import (
    AnalysisMetadata,
    ApplicantQualification,
    ClassifiedDocument,
    DecisionDraft,
    DraftSection,
    ExtractedDocument,
    ExtractedFields,
    ExtractedPage,
    PageSource,
    ProcessAnalysisResult,
)

__all__ = [
    # enums
    "BenefitType",
    "ChecklistStatus",
    "ConclusionStatus",
    "IncomeStatus",
    "LegalRegimeId",
    "PropertyRelationshipType",
    # errors
    "PocIptuError",
    "ConfigValidationError",
    "RegimeSelectionError",
    # core models
    "ChecklistItemResult",
    "ConclusionResult",
    "IncomeAnalysis",
    "ProcessAnalysisInput",
    "PropertyQualification",
    "RequestIdentification",
    "SelectedRegime",
    # pipeline models
    "AnalysisMetadata",
    "ApplicantQualification",
    "ClassifiedDocument",
    "DecisionDraft",
    "DraftSection",
    "ExtractedDocument",
    "ExtractedFields",
    "ExtractedPage",
    "PageSource",
    "ProcessAnalysisResult",
]
