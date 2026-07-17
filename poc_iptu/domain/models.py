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
    AdmissibilityStatus,
    DenialGround,
)

from .enums import (  # acrescentar ao import existente
    AdmissibilityStatus,
    DenialGround,
)

class _Frozen(BaseModel):
    """Base imutável comum a todos os modelos de domínio."""

    model_config = ConfigDict(frozen=True)


class IncomeSource(_Frozen):
    """Uma fonte de renda identificada no processo, com valor bruto mensal quando extraível.

    monthly_gross_amount = None significa 'fonte identificada, valor não comprovado' —
    exatamente o cenário que dispara VERIFICAR (nunca presumimos valor).
    """

    description: str                        # ex.: "Aposentadoria INSS", "MEI (JUCESP)"
    monthly_gross_amount: float | None = None
    evidence: str | None = None
    page: int | None = None


class AdmissibilityFacts(_Frozen):
    """Fatos de admissibilidade (Etapas 2 e 3 do fluxo SRC). Produzidos no Sprint 3;
    até lá, os defaults NAO_AVALIADO tornam este modelo neutro na precedência."""

    tempestividade: AdmissibilityStatus = AdmissibilityStatus.NAO_AVALIADO
    tempestividade_detail: str | None = None
    legitimidade: AdmissibilityStatus = AdmissibilityStatus.NAO_AVALIADO
    legitimidade_detail: str | None = None
    perda_de_objeto_detectada: bool = False
    perda_de_objeto_detail: str | None = None


class IncomeAnalysis(_Frozen):
    """Análise de renda agregada do requerente.

    A partir do Sprint 2, `income_status` deixa de ser palavra final do LLM: o
    IncomeLimitCalculator o recalcula deterministicamente a partir de `sources`.
    """

    benefit_condition: BenefitType
    benefit_document_found: bool
    income_document_found: bool
    other_sources_flag: str | None = None
    income_status: IncomeStatus
    sources: list[IncomeSource] = Field(default_factory=list)      # NOVO
    total_monthly_gross: float | None = None                       # NOVO: preenchido pelo calculador
    applied_income_limit: float | None = None                      # NOVO: 5 × SM[exercício]


class ProcessAnalysisInput(_Frozen):
    request: RequestIdentification
    property: PropertyQualification
    income: IncomeAnalysis
    checklist: list[ChecklistItemResult]
    admissibility: AdmissibilityFacts = Field(default_factory=AdmissibilityFacts)  # NOVO


class ConclusionResult(_Frozen):
    status: ConclusionStatus
    main_reason: str
    denial_ground: DenialGround | None = None      # NOVO (ADR-S2-02)
    missing_required_documents: list[str] = Field(default_factory=list)
    items_to_verify: list[str] = Field(default_factory=list)
    legal_basis: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    generate_merit_draft: bool = True

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


