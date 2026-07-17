"""Guardrails jurídicos da minuta — validação independente do redator.

Responsabilidade única: dado o texto final de uma minuta de mérito, verificar os
invariantes inegociáveis da POC. Usado tanto no caminho determinístico quanto no
caminho LLM (onde é a última linha de defesa antes de aceitar o texto gerado).
"""

from __future__ import annotations

import re

from ..domain.errors import PocIptuError
from ..domain.pipeline_models import ProcessAnalysisResult
from . import draft_layout

_FORBIDDEN_DECISION = re.compile(r"\bDEFIRO\b|\bJULGO\s+PROCEDENTE\b", re.IGNORECASE)
# CPF completo (11 dígitos, com ou sem máscara de pontuação) não pode aparecer no texto.
_UNMASKED_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
# Referências de página escritas no corpo da minuta (ex.: 'página 7').
_PAGE_CITATION = re.compile(r"p[áa]gina\s+(\d+)", re.IGNORECASE)


class DraftGuardrailViolation(PocIptuError):
    """O texto da minuta viola um invariante jurídico da POC."""


class DraftGuardrailValidator:
    """Valida o texto final da minuta contra os invariantes da POC."""

    def validate_merit_draft(self, text: str, result: ProcessAnalysisResult) -> None:
        """Levanta DraftGuardrailViolation na primeira violação encontrada."""
        self._assert_no_forbidden_decision(text)
        self._assert_no_unmasked_cpf(text)
        self._assert_mandatory_titles_present(text)
        self._assert_cited_pages_are_anchored(text, result)

    # ------------------------------------------------------------- invariantes

    @staticmethod
    def _assert_no_forbidden_decision(text: str) -> None:
        if _FORBIDDEN_DECISION.search(text):
            raise DraftGuardrailViolation(
                "A minuta não pode conter a decisão 'DEFIRO'; o máximo permitido é indicar "
                "aptidão à análise de deferimento pela autoridade competente."
            )

    @staticmethod
    def _assert_no_unmasked_cpf(text: str) -> None:
        if _UNMASKED_CPF.search(text):
            raise DraftGuardrailViolation(
                "CPF aparentemente não mascarado no texto da minuta; a saída deve usar "
                "exclusivamente CPF mascarado."
            )

    @staticmethod
    def _assert_mandatory_titles_present(text: str) -> None:
        for title in draft_layout.SECTION_TITLES.values():
            if title not in text:
                raise DraftGuardrailViolation(
                    f"Minuta de mérito sem a seção obrigatória '{title}'."
                )

    @staticmethod
    def _assert_cited_pages_are_anchored(text: str, result: ProcessAnalysisResult) -> None:
        """Nenhuma página pode ser citada sem evidência ancorada (anti-alucinação)."""
        anchored_pages: set[int] = set()
        for item in result.checklist:
            if draft_layout.has_anchored_page(item):
                anchored_pages.add(item.page)
        for document in result.documents:
            if document.evidence:
                anchored_pages.update(range(document.page_start, document.page_end + 1))
        # As páginas totais citáveis em rastreabilidade também são válidas por definição.
        cited = {int(match) for match in _PAGE_CITATION.findall(text)}
        unanchored = cited - anchored_pages
        if unanchored:
            raise DraftGuardrailViolation(
                "A minuta cita página(s) sem evidência textual ancorada: "
                f"{sorted(unanchored)}."
            )