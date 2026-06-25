"""Schemas tipados das configurações consumidas pelo núcleo determinístico.

Princípio: parsear apenas o que o núcleo realmente usa. Os YAMLs têm muitos campos
(documentação, pendências, metadados) que esta versão não consome; modelá-los todos
criaria acoplamento desnecessário e fragilidade. O loader extrai os sub-dicionários
relevantes e os valida contra estes schemas, falhando alto se uma chave essencial faltar.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..domain.enums import BenefitType, ConclusionStatus, LegalRegimeId


class _StrictConfig(BaseModel):
    """Base estrita para configs: rejeita coerções silenciosas perigosas."""

    model_config = ConfigDict(extra="ignore")


class ScopeConfig(_StrictConfig):
    allowed_benefit_types: list[BenefitType]
    out_of_scope_benefit_types: list[BenefitType]
    out_of_scope_result: ConclusionStatus


class ConfidencePolicyConfig(_StrictConfig):
    minimum_confidence_for_ok: float
    require_evidence_anchor: bool
    below_threshold_status: str


class SummaryDenialRegimeRule(_StrictConfig):
    enabled: bool
    legal_basis: str | None = None
    status: str | None = None


class SummaryDenialConfig(_StrictConfig):
    if_any_required_document_missing: bool
    status: ConclusionStatus
    applies_only_when_legal_regime_allows_summary_denial: bool
    legal_regime_rules: dict[str, SummaryDenialRegimeRule]


class BusinessRulesConfig(_StrictConfig):
    version: str
    depends_on_legal_references_version: str
    scope: ScopeConfig
    confidence: ConfidencePolicyConfig
    summary_denial: SummaryDenialConfig


class DecreeConfig(_StrictConfig):
    id: LegalRegimeId
    name: str
    status: str
    article_map: dict[str, str]


class LegalReferencesConfig(_StrictConfig):
    version: str
    decrees: dict[LegalRegimeId, DecreeConfig]
    selection_priority: list[str]
    fallback_status: ConclusionStatus


class ChecklistItemConfig(_StrictConfig):
    code: str
    label: str
    required: bool
    conditional: bool = False
    accepted_document_types: list[str] = []
    not_equivalent_document_types: list[str] = []
    trigger_document_types: list[str] = []
    missing_impacts_conclusion: bool = True


class ChecklistConfig(_StrictConfig):
    version: str
    items: list[ChecklistItemConfig]


class ConclusionStateConfig(_StrictConfig):
    display_label: str
    draft_text: str
    generate_merit_draft: bool


class ConclusionMappingConfig(_StrictConfig):
    version: str
    states: dict[ConclusionStatus, ConclusionStateConfig]
    mandatory_sections: list[str]
    appeal_notice_enabled: bool
    appeal_notice_text: str


class AppConfig(_StrictConfig):
    """Agregado de configuração validado e coerente, pronto para alimentar o núcleo."""

    business_rules: BusinessRulesConfig
    legal_references: LegalReferencesConfig
    checklist: ChecklistConfig
    conclusion_mapping: ConclusionMappingConfig
