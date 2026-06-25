"""Política de confiança — guardrail anti-alucinação.

Responsabilidade única: normalizar o status de um item de checklist segundo dois invariantes
inegociáveis da POC:

  1. confiança abaixo do mínimo configurado (0.70) rebaixa o item para VERIFICAR;
  2. página citada sem evidência textual ancorada rebaixa o item para VERIFICAR.

Nenhuma página do PDF pode ser afirmada na minuta sem evidência. A normalização é pura e
produz uma NOVA instância do item (modelos são imutáveis), acumulando os avisos pertinentes.
"""

from __future__ import annotations

from ..config.schemas import ConfidencePolicyConfig
from ..domain.enums import ChecklistStatus
from ..domain.models import ChecklistItemResult


class ConfidencePolicy:
    """Aplica a política de confiança a itens de checklist."""

    def __init__(self, config: ConfidencePolicyConfig) -> None:
        self._minimum_confidence = config.minimum_confidence_for_ok
        self._require_evidence_anchor = config.require_evidence_anchor

    def normalize(self, item: ChecklistItemResult) -> ChecklistItemResult:
        """Retorna o item possivelmente rebaixado para VERIFICAR, com avisos acumulados."""
        new_status = item.status
        new_warnings = list(item.warnings)

        if item.confidence < self._minimum_confidence:
            new_status = ChecklistStatus.VERIFICAR
            new_warnings.append(
                f"Confiança {item.confidence:.2f} abaixo do mínimo "
                f"({self._minimum_confidence:.2f}); status forçado para VERIFICAR."
            )

        if self._require_evidence_anchor and item.page is not None and not item.evidence:
            new_status = ChecklistStatus.VERIFICAR
            new_warnings.append(
                "Página informada sem evidência textual ancorada; status forçado para VERIFICAR."
            )

        if new_status == item.status and new_warnings == item.warnings:
            return item
        return item.model_copy(update={"status": new_status, "warnings": new_warnings})
