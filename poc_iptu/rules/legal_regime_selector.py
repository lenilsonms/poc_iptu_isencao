"""Seleção do regime legal aplicável ao processo.

Responsabilidade única: dado o pedido (e seus sinais), decidir QUAL decreto regulamentador
fundamenta a análise, resolvendo-o num `SelectedRegime` com fatos acionáveis.

Estratégia (regulatory_decrees.selection_strategy.priority):
  1. menção explícita ao decreto no PDF (sinal mais forte e único confiável hoje);
  2. data de protocolo / exercício pleiteado — heurística conservadora, só quando inequívoca;
  3. caso contrário -> None (o ConclusionResolver converte em VERIFICAR_MANUALMENTE).

Regra P0 embutida: `summary_denial_confirmed` só é verdadeiro quando o regime habilita a
autoridade de indeferimento de plano (business_rules) E o artigo correspondente é real em
legal_references (não 'PENDING_CONFIRMATION'). É isso que impede o sistema de indeferir
sumariamente sob o Decreto 42.621/2025 enquanto sua base não estiver confirmada.
"""

from __future__ import annotations

import re

from ..config.schemas import BusinessRulesConfig, LegalReferencesConfig
from ..domain.enums import LegalRegimeId
from ..domain.errors import RegimeSelectionError
from ..domain.models import RequestIdentification, SelectedRegime

# Exercício a partir do qual, na ausência de menção explícita, NÃO se assume o regime novo
# enquanto a data de corte entre os decretos não estiver confirmada.
_CONSERVATIVE_OLD_REGIME_MAX_YEAR = 2024


class LegalRegimeSelector:
    """Seleciona o regime regulamentador aplicável."""

    def __init__(
        self,
        legal_references: LegalReferencesConfig,
        business_rules: BusinessRulesConfig,
    ) -> None:
        self._legal_references = legal_references
        self._business_rules = business_rules

    def select(self, request: RequestIdentification) -> SelectedRegime | None:
        """Retorna o regime selecionado, ou None quando não há seleção segura."""
        regime_id, reason = self._resolve_regime_id(request)
        if regime_id is None:
            return None
        return self._build_selected_regime(regime_id, reason)

    # ----------------------------------------------------------------- helpers

    def _resolve_regime_id(
        self, request: RequestIdentification
    ) -> tuple[LegalRegimeId | None, str]:
        # 1) menção explícita no PDF
        if request.explicit_decree_mention:
            matched = self._match_decree_by_mention(request.explicit_decree_mention)
            if matched is not None:
                return matched, "Menção explícita ao decreto no processo (PDF)."

        # 2) heurística conservadora por exercício (somente quando inequívoca)
        if request.requested_year <= _CONSERVATIVE_OLD_REGIME_MAX_YEAR:
            if LegalRegimeId.DEC_34767_2018.value in self._legal_references.decrees:
                return (
                    LegalRegimeId.DEC_34767_2018,
                    "Exercício até 2024 sem menção explícita; preferência conservadora pelo "
                    "regime do Decreto nº 34.767/2018 (data de corte ainda não confirmada).",
                )

        # 3) sem seleção segura
        return None, self._legal_references.fallback_status.value

    def _match_decree_by_mention(self, mention: str) -> LegalRegimeId | None:
        """Casa a menção textual ao decreto pelo seu número (ex.: '34.767/2018')."""
        for regime_id_str, decree in self._legal_references.decrees.items():
            number = self._extract_decree_number(decree.name)
            if number and number in mention:
                return LegalRegimeId(regime_id_str)
        return None

    @staticmethod
    def _extract_decree_number(decree_name: str) -> str | None:
        """Extrai o núcleo numérico de um nome de decreto (ex.: 'Decreto nº 34.767/2018' -> '34.767/2018')."""
        match = re.search(r"\d{1,3}(?:\.\d{3})*/\d{4}", decree_name)
        return match.group(0) if match else None

    def _build_selected_regime(
        self, regime_id: LegalRegimeId, reason: str
    ) -> SelectedRegime:
        decree = self._legal_references.decrees.get(regime_id.value)
        if decree is None:  # pragma: no cover - inconsistência estrutural
            raise RegimeSelectionError(
                f"Regime '{regime_id.value}' selecionado mas inexistente em legal_references."
            )

        summary_denial_enabled = self._is_summary_denial_enabled(regime_id)
        summary_denial_article = decree.article_map.get("summary_denial")
        summary_denial_confirmed = summary_denial_enabled and self._is_real_article(
            summary_denial_article
        )

        return SelectedRegime(
            id=regime_id,
            name=decree.name,
            article_map=decree.article_map,
            summary_denial_enabled=summary_denial_enabled,
            summary_denial_confirmed=summary_denial_confirmed,
            selection_reason=reason,
        )

    def _is_summary_denial_enabled(self, regime_id: LegalRegimeId) -> bool:
        rule = self._business_rules.summary_denial.legal_regime_rules.get(regime_id.value)
        return bool(rule and rule.enabled)

    @staticmethod
    def _is_real_article(value: str | None) -> bool:
        """True apenas para referências de artigo de verdade (descarta 'PENDING_CONFIRMATION', None)."""
        return isinstance(value, str) and value.strip().lower().startswith("art")
