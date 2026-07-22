from __future__ import annotations
from ..config.schemas import BusinessRulesConfig
from ..domain.enums import (
    AdmissibilityStatus,
    ChecklistStatus,
    ConclusionStatus,
    DenialGround,
    IncomeStatus,
)
from ..domain.models import (
    ChecklistItemResult,
    ConclusionResult,
    ProcessAnalysisInput,
    SelectedRegime,
)

_SUMMARY_DENIAL_FALLBACK = ConclusionStatus.VERIFICAR_MANUALMENTE

# Fundamentos das regras de admissibilidade (espelham admissibility_legal_basis do YAML;
# se preferir 100% config-driven, carregue-os no BusinessRulesConfig — deixei constantes
# aqui para reduzir o diff do loader neste sprint).
_BASIS_INTEMPESTIVIDADE = ["Lei Municipal nº 7.774/2019, art. 40 (subsidiariamente)"]
_BASIS_ILEGITIMIDADE = [
    "Lei Municipal nº 7.774/2019, art. 40, inciso II",
    "Decreto nº 21.066/2000, art. 11",
    "Decreto nº 25.345/2008, art. 7º",
]
_BASIS_PERDA_DE_OBJETO = [
    "Lei Municipal nº 7.774/2019, art. 35",
    "Decreto nº 21.066/2000, art. 10",
]


class ConclusionResolver:
    """Aplica a tabela de precedência v2 e devolve a conclusão sugerida."""

    def __init__(self, business_rules: BusinessRulesConfig) -> None:
        self._rules = business_rules
        self._out_of_scope = set(business_rules.scope.out_of_scope_benefit_types)

    def resolve(
        self, analysis: ProcessAnalysisInput, regime: SelectedRegime | None
    ) -> ConclusionResult:
        base_warnings = self._collect_non_determinant_warnings(analysis)
        base_warnings = [*base_warnings, *self._admissibility_warnings(analysis)]
        # R1 — fora do escopo (inalterado).
        if analysis.request.benefit_type in self._out_of_scope:
            return ConclusionResult(
                status=ConclusionStatus.FORA_DO_ESCOPO_POC,
                main_reason="Tipo de pedido fora do escopo da POC.",
                warnings=base_warnings,
                generate_merit_draft=False,
            )

        # -------- ANDAR DE ADMISSIBILIDADE (novo) --------
        admissibility_conclusion = self._resolve_admissibility(analysis, base_warnings)
        if admissibility_conclusion is not None:
            return admissibility_conclusion

        admissibility_to_verify = self._admissibility_items_to_verify(analysis)

        return self._resolve_merit(analysis, regime, base_warnings, admissibility_to_verify)

    # ------------------------------------------------------- admissibilidade

    @staticmethod
    def _admissibility_items_to_verify(analysis: ProcessAnalysisInput) -> list[str]:
        """Detalhes das verificações com status VERIFICAR (divergência inconclusiva)."""
        facts = analysis.admissibility
        items: list[str] = []
        if facts.tempestividade == AdmissibilityStatus.VERIFICAR and facts.tempestividade_detail:
            items.append(facts.tempestividade_detail)
        if facts.legitimidade == AdmissibilityStatus.VERIFICAR and facts.legitimidade_detail:
            items.append(facts.legitimidade_detail)
        return items

    @staticmethod
    def _admissibility_warnings(analysis: ProcessAnalysisInput) -> list[str]:
        """Detalhes das verificações NAO_AVALIADO (insumo ausente) viram avisos."""
        facts = analysis.admissibility
        warnings: list[str] = []
        if facts.tempestividade == AdmissibilityStatus.NAO_AVALIADO and facts.tempestividade_detail:
            warnings.append(facts.tempestividade_detail)
        if facts.legitimidade == AdmissibilityStatus.NAO_AVALIADO and facts.legitimidade_detail:
            warnings.append(facts.legitimidade_detail)
        return warnings
    
    def _resolve_admissibility(
        self, analysis: ProcessAnalysisInput, base_warnings: list[str]
    ) -> ConclusionResult | None:
        """Aplica A1–A3; devolve None quando a admissibilidade não determina o desfecho."""
        facts = analysis.admissibility

        # A1 — intempestividade -> não conhecimento (mérito não é examinado).
        if facts.tempestividade == AdmissibilityStatus.FALHA:
            return ConclusionResult(
                status=ConclusionStatus.NAO_CONHECIMENTO_SUGERIDO,
                main_reason=facts.tempestividade_detail
                or "Pedido intempestivo; sugere-se o não conhecimento.",
                legal_basis=list(_BASIS_INTEMPESTIVIDADE),
                warnings=base_warnings,
            )

        # A2 — perda de objeto -> julgamento prejudicado.
        if facts.perda_de_objeto_detectada:
            return ConclusionResult(
                status=ConclusionStatus.JULGAMENTO_PREJUDICADO_SUGERIDO,
                main_reason=facts.perda_de_objeto_detail
                or "Exercícios já tratados em processos anteriores; julgamento prejudicado.",
                legal_basis=list(_BASIS_PERDA_DE_OBJETO),
                warnings=base_warnings,
            )

        # A3 — ilegitimidade -> indeferimento por inépcia da inicial.
        if facts.legitimidade == AdmissibilityStatus.FALHA:
            return ConclusionResult(
                status=ConclusionStatus.INDEFERIMENTO_SUGERIDO,
                denial_ground=DenialGround.INEPCIA_DA_INICIAL,
                main_reason=facts.legitimidade_detail
                or "Requerente sem legitimidade; sugere-se indeferimento por inépcia da inicial.",
                legal_basis=list(_BASIS_ILEGITIMIDADE),
                warnings=base_warnings,
            )

        return None

    # ----------------------------------------------------------------- mérito

    def _resolve_merit(
        self,
        analysis: ProcessAnalysisInput,
        regime: SelectedRegime | None,
        base_warnings: list[str],
        admissibility_to_verify: list[str],
    ) -> ConclusionResult:
        # M0 — regime não identificado (inalterado, era R0).
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

        # M1 — renda acima do limite (agora só produzida pelo IncomeLimitCalculator).
        if analysis.income.income_status == IncomeStatus.ACIMA_DO_LIMITE:
            return ConclusionResult(
                status=ConclusionStatus.INDEFERIMENTO_SUGERIDO,
                denial_ground=DenialGround.RENDA_ACIMA_DO_LIMITE,
                main_reason=self._income_above_limit_reason(analysis),
                items_to_verify=to_verify,
                legal_basis=self._dedupe(
                    [*augmented_basis, *self._basis_from(regime, "other_income_sources")]
                ),
                warnings=base_warnings,
            )

        # M2 — documento obrigatório ausente (inalterado, era R3), com denial_ground.
        if missing_required:
            return self._resolve_missing_required(
                regime, missing_required, to_verify, augmented_basis, base_warnings
            )

        # M3 — verificação manual (inalterado, era R4).
        merged_to_verify = [*admissibility_to_verify, *to_verify]
        if merged_to_verify or analysis.income.income_status == IncomeStatus.VERIFICAR:
            return ConclusionResult(
                status=ConclusionStatus.VERIFICAR_MANUALMENTE,
                main_reason="Há itens que exigem verificação manual antes da decisão.",
                items_to_verify=self._with_income_marker(
                    merged_to_verify, analysis.income.income_status
                ),
                legal_basis=self._dedupe(augmented_basis),
                warnings=base_warnings,
            )

        # M4 — apto (procedência a ser declarada pela autoridade — ADR-S2-01).
        return ConclusionResult(
            status=ConclusionStatus.APTO_PARA_ANALISE_DE_DEFERIMENTO,
            main_reason="Pedido regularmente instruído quanto aos itens verificados pela POC.",
            warnings=base_warnings,
        )

    @staticmethod
    def _income_above_limit_reason(analysis: ProcessAnalysisInput) -> str:
        """Motivo com os números que o calculador ancorou (transparência da decisão)."""
        income = analysis.income
        if income.total_monthly_gross is not None and income.applied_income_limit is not None:
            return (
                f"Renda bruta mensal comprovada de R$ {income.total_monthly_gross:,.2f} "
                f"acima do limite de R$ {income.applied_income_limit:,.2f} "
                f"(5 salários mínimos do exercício {analysis.request.requested_year})."
            )
        return "Renda bruta mensal total acima do limite de 5 salários mínimos."

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
