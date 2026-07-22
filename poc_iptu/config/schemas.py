"""Schemas tipados das configurações consumidas pelo núcleo determinístico.

Princípio: parsear apenas o que o núcleo realmente usa. Os YAMLs têm muitos campos
(documentação, pendências, metadados) que esta versão não consome; modelá-los todos
criaria acoplamento desnecessário e fragilidade. O loader extrai os sub-dicionários
relevantes e os valida contra estes schemas, falhando alto se uma chave essencial faltar.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..domain.enums import BenefitType, ConclusionStatus, LegalRegimeId
from datetime import date

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

class IncomeLimitConfig(_StrictConfig):
    """Parâmetros do limite de renda (5 SM por exercício)."""

    multiplier: int
    salario_minimo_por_ano: dict[int, float]

    def limit_for_year(self, year: int) -> float | None:
        """5 × SM do exercício; None se o ano não estiver na tabela (nunca extrapola)."""
        minimum_wage = self.salario_minimo_por_ano.get(year)
        return None if minimum_wage is None else self.multiplier * minimum_wage

class TimelinessConfig(_StrictConfig):
    """Prazos de tempestividade por exercício (Tabela 1 da SRC)."""

    deadlines_by_year: dict[int, date]

    def deadline_for_year(self, year: int) -> date | None:
        return self.deadlines_by_year.get(year)


class LegitimacyConfig(_StrictConfig):
    """Parâmetros da verificação de legitimidade (Etapa 3)."""

    qualifying_relationship_types: list[str]


class AdmissibilityConfig(_StrictConfig):
    timeliness: TimelinessConfig
    legitimacy: LegitimacyConfig


class BusinessRulesConfig(_StrictConfig):
    version: str
    depends_on_legal_references_version: str
    scope: ScopeConfig
    confidence: ConfidencePolicyConfig
    summary_denial: SummaryDenialConfig
    income_limit: IncomeLimitConfig
    admissibility: AdmissibilityConfig

class DecreeConfig(_StrictConfig):
    id: LegalRegimeId
    name: str
    status: str
    article_map: dict[str, str]
    # NOVO — janela de vigência confirmada; None quando desconhecida.
    valid_from: date | None = None
    valid_until: date | None = None

    def is_in_force_on(self, reference_date: date) -> bool:
        """True se a data está dentro da janela de vigência CONFIRMADA do decreto."""
        if self.valid_from is None:
            return False  # sem vigência confirmada, nunca seleciona por data
        if reference_date < self.valid_from:
            return False
        return self.valid_until is None or reference_date <= self.valid_until

class LegalReferencesConfig(_StrictConfig):
    version: str
    decrees: dict[LegalRegimeId, DecreeConfig]
    selection_priority: list[str]
    fallback_status: ConclusionStatus
    year_to_regime: dict[int, LegalRegimeId] = {}


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
