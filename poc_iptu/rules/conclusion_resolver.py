"""Resolução determinística da conclusão sugerida.

Responsabilidade única: dada a visão de fatos (ProcessAnalysisInput) e o regime selecionado,
produzir o estado canônico de conclusão segundo a tabela de precedência ordenada de
business_rules.yaml (seção conclusion_resolution).

A ORDEM das regras é o contrato. Em particular, documento obrigatório ausente (R3) tem
precedência sobre verificação manual (R4) — é isso que reproduz o resultado do caso-ouro,
onde há simultaneamente um documento ausente e itens a verificar, e a conclusão é
INDEFERIMENTO_SUGERIDO.

O fundamento legal é montado por agregação: a regra que define o estado contribui seu artigo
(ex.: summary_denial -> art. 7º), e a "augmentation" adiciona artigos de condições presentes
independentemente do estado (ex.: outras fontes em aberto -> art. 3º). É essa soma que produz
o fundamento [art. 3º, art. 7º] do caso-ouro.
"""

from __future__ import annotations

from ..config.schemas import BusinessRulesConfig
from ..domain.enums import ChecklistStatus, ConclusionStatus, IncomeStatus
from ..domain.models import (
    ChecklistItemResult,
    ConclusionResult,
    ProcessAnalysisInput,
    SelectedRegime,
)

# Estado para o qual R3 rebaixa quando o regime não confirma a autoridade de indeferimento de plano.
_SUMMARY_DENIAL_FALLBACK = ConclusionStatus.VERIFICAR_MANUALMENTE


class ConclusionResolver:
    """Aplica a tabela de precedência e devolve a conclusão sugerida."""

    def __init__(self, business_rules: BusinessRulesConfig) -> None:
        self._rules = business_rules
        self._out_of_scope = set(business_rules.scope.out_of_scope_benefit_types)

    def resolve(
        self, analysis: ProcessAnalysisInput, regime: SelectedRegime | None
    ) -> ConclusionResult:
        base_warnings = self._collect_non_determinant_warnings(analysis)

        # R1 — fora do escopo
        if analysis.request.benefit_type in self._out_of_scope:
            return ConclusionResult(
                status=ConclusionStatus.FORA_DO_ESCOPO_POC,
                main_reason="Tipo de pedido fora do escopo da POC.",
                warnings=base_warnings,
                generate_merit_draft=False,
            )

        # R0 — regime não identificado com segurança
        if regime is None:
            return ConclusionResult(
                status=ConclusionStatus.VERIFICAR_MANUALMENTE,
                main_reason="Regime regulamentador não identificado com segurança.",
                warnings=[
                    *base_warnings,
                    "Sem regime confirmado não é possível ancorar fundamento normativo definitivo.",
                ],
            )

        missing_required = self._missing_required_codes(analysis.checklist)
        to_verify = self._items_to_verify_codes(analysis.checklist)
        augmented_basis = self._augment_basis(analysis, regime)

        # R2 — renda acima do limite
        if analysis.income.income_status == IncomeStatus.ACIMA_DO_LIMITE:
            basis = self._dedupe(
                [*augmented_basis, *self._basis_from(regime, "other_income_sources")]
            )
            return ConclusionResult(
                status=ConclusionStatus.INDEFERIMENTO_SUGERIDO,
                main_reason="Renda bruta mensal total acima do limite de 5 salários mínimos.",
                items_to_verify=to_verify,
                legal_basis=basis,
                warnings=base_warnings,
            )

        # R3 — documento obrigatório ausente (com guarda de summary_denial)
        if missing_required:
            return self._resolve_missing_required(
                regime, missing_required, to_verify, augmented_basis, base_warnings
            )

        # R4 — verificação manual
        if to_verify or analysis.income.income_status == IncomeStatus.VERIFICAR:
            verify_codes = self._with_income_marker(to_verify, analysis.income.income_status)
            return ConclusionResult(
                status=ConclusionStatus.VERIFICAR_MANUALMENTE,
                main_reason="Há itens que exigem verificação manual antes da decisão.",
                items_to_verify=verify_codes,
                legal_basis=self._dedupe(augmented_basis),
                warnings=base_warnings,
            )

        # R5 — apto
        return ConclusionResult(
            status=ConclusionStatus.APTO_PARA_ANALISE_DE_DEFERIMENTO,
            main_reason="Pedido regularmente instruído quanto aos itens verificados pela POC.",
            warnings=base_warnings,
        )

    # ----------------------------------------------------------------- R3

    def _resolve_missing_required(
        self,
        regime: SelectedRegime,
        missing_required: list[str],
        to_verify: list[str],
        augmented_basis: list[str],
        base_warnings: list[str],
    ) -> ConclusionResult:
        regime_allows = self._rules.summary_denial.applies_only_when_legal_regime_allows_summary_denial
        if regime.summary_denial_confirmed or not regime_allows:
            basis = self._dedupe(
                [*augmented_basis, *self._basis_from(regime, "summary_denial")]
            )
            return ConclusionResult(
                status=ConclusionStatus.INDEFERIMENTO_SUGERIDO,
                main_reason="Documento(s) obrigatório(s) não apresentado(s); indeferimento de plano.",
                missing_required_documents=missing_required,
                items_to_verify=to_verify,
                legal_basis=basis,
                warnings=base_warnings,
            )

        # Regime não confirma autoridade de indeferimento de plano -> rebaixa (regra P0).
        return ConclusionResult(
            status=_SUMMARY_DENIAL_FALLBACK,
            main_reason=(
                "Documento(s) obrigatório(s) ausente(s), mas o regime "
                f"{regime.name} não confirma autoridade de indeferimento de plano; "
                "rebaixado para verificação manual."
            ),
            items_to_verify=self._dedupe([*missing_required, *to_verify]),
            legal_basis=self._dedupe(augmented_basis),
            warnings=[
                *base_warnings,
                f"Indeferimento de plano não autorizado sob {regime.name} "
                "(summary_denial PENDING_CONFIRMATION).",
            ],
        )

    # ----------------------------------------------------------------- cálculos

    @staticmethod
    def _missing_required_codes(checklist: list[ChecklistItemResult]) -> list[str]:
        return [
            item.code
            for item in checklist
            if item.required and item.status == ChecklistStatus.NAO_APRESENTADO
        ]

    @staticmethod
    def _items_to_verify_codes(checklist: list[ChecklistItemResult]) -> list[str]:
        return [
            item.code for item in checklist if item.status == ChecklistStatus.VERIFICAR
        ]

    def _augment_basis(
        self, analysis: ProcessAnalysisInput, regime: SelectedRegime
    ) -> list[str]:
        """AUG_OUTRAS_FONTES_EM_ABERTO: cita o dispositivo de outras fontes quando há renda em aberto."""
        income = analysis.income
        open_other_source = income.other_sources_flag and income.income_status in (
            IncomeStatus.VERIFICAR,
            IncomeStatus.ACIMA_DO_LIMITE,
        )
        if open_other_source:
            return self._basis_from(regime, "other_income_sources")
        return []

    @staticmethod
    def _basis_from(regime: SelectedRegime, article_key: str) -> list[str]:
        """Constrói uma entrada de fundamento 'Decreto X, art. Yº' se o artigo for real."""
        article = regime.article_map.get(article_key)
        if isinstance(article, str) and article.strip().lower().startswith("art"):
            return [f"{regime.name}, {article}"]
        return []

    @staticmethod
    def _with_income_marker(
        verify_codes: list[str], income_status: IncomeStatus
    ) -> list[str]:
        if income_status == IncomeStatus.VERIFICAR and "RENDA" not in verify_codes:
            return [*verify_codes, "RENDA"]
        return verify_codes

    def _collect_non_determinant_warnings(
        self, analysis: ProcessAnalysisInput
    ) -> list[str]:
        warnings: list[str] = []
        if analysis.property.multiple_inscriptions_detected:
            warnings.append(
                "Múltiplas inscrições detectadas; recomenda-se conferência manual da "
                "inscrição pleiteada."
            )
        return warnings

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        """Remove duplicatas preservando a ordem de inserção."""
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result
