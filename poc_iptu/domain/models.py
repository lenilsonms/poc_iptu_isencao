"""Modelos de domínio da POC (Pydantic v2).

Os modelos são imutáveis (frozen) para reforçar o caráter determinístico do núcleo:
uma vez construído um fato, ele não é mutado — transformações produzem novas instâncias
via `model_copy`. Isso elimina toda uma classe de bugs de estado compartilhado no motor de regras.

Estes modelos representam FATOS JÁ EXTRAÍDOS. A produção desses fatos (PDF, OCR, LLM) é
responsabilidade de adapters externos; o núcleo apenas os consome.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    BenefitType,
    ChecklistStatus,
    ConclusionStatus,
    IncomeStatus,
    LegalRegimeId,
    PropertyRelationshipType,
)


class _Frozen(BaseModel):
    """Base imutável comum a todos os modelos de domínio."""

    model_config = ConfigDict(frozen=True)


class ChecklistItemResult(_Frozen):
    """Resultado da verificação de um item documental do checklist."""

    code: str
    label: str
    required: bool
    status: ChecklistStatus
    page: int | None = None
    evidence: str | None = None
    confidence: float = 1.0
    legal_basis: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class IncomeAnalysis(_Frozen):
    """Análise de renda agregada do requerente."""

    benefit_condition: BenefitType
    benefit_document_found: bool
    income_document_found: bool
    other_sources_flag: str | None = None
    income_status: IncomeStatus


class PropertyQualification(_Frozen):
    """Qualificação do vínculo com o imóvel."""

    registration_number: str | None = None
    relationship_type: PropertyRelationshipType = PropertyRelationshipType.VERIFICAR
    multiple_inscriptions_detected: bool = False
    residence_confirmed: bool = False


class RequestIdentification(_Frozen):
    """Identificação do pedido inicial e sinais para seleção do regime legal."""

    benefit_type: BenefitType
    requested_year: int
    protocol_date: date | None = None
    explicit_decree_mention: str | None = None
    page: int | None = None


class ProcessAnalysisInput(_Frozen):
    """Visão determinística dos fatos extraídos, consumida pelo motor de regras.

    É a fronteira entre a parte estocástica (LLM/OCR) e a parte determinística (regras).
    Tudo aqui já é fato estruturado e tipado.
    """

    request: RequestIdentification
    property: PropertyQualification
    income: IncomeAnalysis
    checklist: list[ChecklistItemResult]


class SelectedRegime(_Frozen):
    """Regime legal selecionado para o processo, já resolvido em fatos acionáveis.

    `summary_denial_confirmed` encapsula a regra P0: indeferimento de plano só é permitido
    quando o regime confirma essa autoridade.
    """

    id: LegalRegimeId
    name: str
    article_map: dict[str, str]
    summary_denial_enabled: bool
    summary_denial_confirmed: bool
    selection_reason: str


class ConclusionResult(_Frozen):
    """Conclusão sugerida pelo motor determinístico. NUNCA é uma decisão final."""

    status: ConclusionStatus
    main_reason: str
    missing_required_documents: list[str] = Field(default_factory=list)
    items_to_verify: list[str] = Field(default_factory=list)
    legal_basis: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    generate_merit_draft: bool = True
