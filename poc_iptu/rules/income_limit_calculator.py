"""Cálculo determinístico do status de renda (Item 5 — consideração 3.2 da SRC).

Responsabilidade única: dado o IncomeAnalysis extraído (com fontes e valores) e o
exercício pleiteado, recalcular o income_status contra 5 × SM[exercício]:

  1. soma comprovada > limite            -> ACIMA_DO_LIMITE (única forma de produzi-lo);
  2. fonte identificada sem valor        -> VERIFICAR (nunca presumimos valor);
  3. exercício fora da tabela de SM      -> VERIFICAR (nunca extrapolamos a tabela);
  4. soma comprovada <= limite, completa -> OK.

Guardrail ADR-S2-05: o LLM não conclui renda. Um ACIMA_DO_LIMITE vindo da extração
sem soma comprovada que o sustente é REBAIXADO para VERIFICAR, com aviso.
"""

from __future__ import annotations

from ..config.schemas import IncomeLimitConfig
from ..domain.enums import IncomeStatus
from ..domain.models import IncomeAnalysis


class IncomeLimitCalculator:
    """Recalcula deterministicamente o status de renda de um processo."""

    def __init__(self, income_limit_config: IncomeLimitConfig) -> None:
        self._config = income_limit_config

    def normalize(self, income: IncomeAnalysis, requested_year: int) -> IncomeAnalysis:
        """Devolve um NOVO IncomeAnalysis com status/total/limite calculados."""
        applied_limit = self._config.limit_for_year(requested_year)  # ADR-S2-04
        documented_total = self._sum_documented_sources(income)
        has_undocumented_source = self._has_undocumented_source(income)

        computed_status, warning = self._compute_status(
            income, applied_limit, documented_total, has_undocumented_source
        )

        if (
            computed_status == income.income_status
            and income.total_monthly_gross == documented_total
            and income.applied_income_limit == applied_limit
            and warning is None
        ):
            return income  # nada mudou; preserva a instância (modelos imutáveis)

        return income.model_copy(
            update={
                "income_status": computed_status,
                "total_monthly_gross": documented_total,
                "applied_income_limit": applied_limit,
            }
        ), warning  # ver nota abaixo sobre a tupla

    # ----------------------------------------------------------------- cálculo

    def _compute_status(
        self,
        income: IncomeAnalysis,
        applied_limit: float | None,
        documented_total: float | None,
        has_undocumented_source: bool,
    ) -> tuple[IncomeStatus, str | None]:
        # 3) Exercício fora da tabela: não sabemos o limite — VERIFICAR.
        if applied_limit is None:
            return IncomeStatus.VERIFICAR, (
                "Exercício sem salário mínimo na tabela configurada; "
                "limite de renda não pôde ser calculado."
            )

        # 1) Soma comprovada acima do limite: única via para ACIMA_DO_LIMITE.
        if documented_total is not None and documented_total > applied_limit:
            return IncomeStatus.ACIMA_DO_LIMITE, None

        # Guardrail ADR-S2-05: LLM alegou ACIMA sem soma que sustente -> rebaixa.
        if income.income_status == IncomeStatus.ACIMA_DO_LIMITE:
            return IncomeStatus.VERIFICAR, (
                "Extração indicou renda acima do limite sem valores comprovados que "
                "sustentem a soma; status rebaixado para VERIFICAR."
            )

        # 2) Fonte identificada sem valor comprovado -> VERIFICAR (consideração 3.2:
        # renda só é DIVERGÊNCIA acima do limite, mas fonte não comprovada continua
        # exigindo verificação — engineering_guardrails.income_policy).
        if has_undocumented_source or income.other_sources_flag:
            if not self._all_flagged_sources_documented(income):
                return IncomeStatus.VERIFICAR, None

        # Sem documento de renda algum: mantém a política existente (VERIFICAR).
        if not income.income_document_found and documented_total is None:
            return IncomeStatus.VERIFICAR, None

        # 4) Tudo comprovado e dentro do limite.
        return IncomeStatus.OK, None

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _sum_documented_sources(income: IncomeAnalysis) -> float | None:
        amounts = [
            source.monthly_gross_amount
            for source in income.sources
            if source.monthly_gross_amount is not None
        ]
        return sum(amounts) if amounts else None

    @staticmethod
    def _has_undocumented_source(income: IncomeAnalysis) -> bool:
        return any(source.monthly_gross_amount is None for source in income.sources)

    @staticmethod
    def _all_flagged_sources_documented(income: IncomeAnalysis) -> bool:
        """other_sources_flag só deixa de exigir verificação se TODAS as fontes têm valor."""
        return bool(income.sources) and all(
            source.monthly_gross_amount is not None for source in income.sources
        )