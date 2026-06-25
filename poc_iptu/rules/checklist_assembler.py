"""Montagem determinística do checklist documental.

Responsabilidade única: dado o conjunto de documentos classificados (com evidência) e o
contexto do requerente/renda, derivar o status de cada item do checklist conforme
checklist_iptu.yaml. A IA classifica e extrai evidência; ESTE serviço aplica as regras —
inclusive a regra "documento parecido não satisfaz o item exigido".

Lógica por item:
  1. há documento de tipo ACEITO? -> OK (com a evidência do documento).
  2. senão, item condicional não aplicável? -> NAO_APLICAVEL.
  3. senão, há documento PARECIDO (not_equivalent) ou condicional disparado/aplicável? -> VERIFICAR.
  4. senão, item obrigatório? -> NAO_APRESENTADO.
  5. senão -> NAO_APLICAVEL.
"""

from __future__ import annotations

from ..config.schemas import ChecklistConfig, ChecklistItemConfig
from ..domain.enums import ChecklistStatus
from ..domain.models import ChecklistItemResult
from ..domain.pipeline_models import ApplicantQualification, ClassifiedDocument, IncomeAnalysis

# Código do item de outras rendas, cuja aplicabilidade também depende da renda extraída.
_CODE_OUTRAS_RENDAS = "COMPROVANTE_OUTRAS_RENDAS"
_CODE_ESTADO_CIVIL = "COMPROVANTE_ESTADO_CIVIL"
_CODE_PROCURACAO = "PROCURACAO"

_ESTADO_CIVIL_EXIGE_COMPROVACAO = {"CASADO", "UNIAO_ESTAVEL", "VIUVO"}


class ChecklistAssembler:
    """Deriva os itens do checklist a partir dos documentos classificados."""

    def __init__(self, checklist_config: ChecklistConfig) -> None:
        self._items = checklist_config.items

    def assemble(
        self,
        classified_documents: list[ClassifiedDocument],
        applicant: ApplicantQualification,
        income: IncomeAnalysis,
    ) -> list[ChecklistItemResult]:
        by_type = self._index_by_type(classified_documents)
        return [self._evaluate_item(item, by_type, applicant, income) for item in self._items]

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _index_by_type(
        documents: list[ClassifiedDocument],
    ) -> dict[str, ClassifiedDocument]:
        """Mapeia tipo -> primeiro documento daquele tipo (suficiente para a POC)."""
        index: dict[str, ClassifiedDocument] = {}
        for document in documents:
            index.setdefault(document.document_type, document)
        return index

    def _evaluate_item(
        self,
        item: ChecklistItemConfig,
        by_type: dict[str, ClassifiedDocument],
        applicant: ApplicantQualification,
        income: IncomeAnalysis,
    ) -> ChecklistItemResult:
        accepted = self._first_match(item.accepted_document_types, by_type)
        if accepted is not None:
            return self._result(item, ChecklistStatus.OK, document=accepted)

        is_conditional_applicable = self._is_conditional_applicable(
            item, by_type, applicant, income
        )
        if item.conditional and not is_conditional_applicable:
            return self._result(item, ChecklistStatus.NAO_APLICAVEL)

        similar = self._first_match(item.not_equivalent_document_types, by_type)
        if similar is not None:
            return self._result(
                item,
                ChecklistStatus.VERIFICAR,
                document=similar,
                warning="Documento semelhante encontrado, mas não satisfaz o item exigido.",
            )

        if item.conditional and is_conditional_applicable:
            return self._result(
                item,
                ChecklistStatus.VERIFICAR,
                warning="Condição disparada sem documento comprobatório suficiente.",
            )

        if item.required:
            return self._result(item, ChecklistStatus.NAO_APRESENTADO)

        return self._result(item, ChecklistStatus.NAO_APLICAVEL)

    @staticmethod
    def _first_match(
        document_types: list[str], by_type: dict[str, ClassifiedDocument]
    ) -> ClassifiedDocument | None:
        for document_type in document_types:
            if document_type in by_type:
                return by_type[document_type]
        return None

    def _is_conditional_applicable(
        self,
        item: ChecklistItemConfig,
        by_type: dict[str, ClassifiedDocument],
        applicant: ApplicantQualification,
        income: IncomeAnalysis,
    ) -> bool:
        """Avalia a condição de exigibilidade dos itens condicionais (semântica do required_when)."""
        if not item.conditional:
            return True

        triggered_by_document = any(t in by_type for t in item.trigger_document_types)

        if item.code == _CODE_OUTRAS_RENDAS:
            return triggered_by_document or bool(income.other_sources_flag)

        if item.code == _CODE_ESTADO_CIVIL:
            estado = (applicant.estado_civil or "").upper()
            return (
                estado in _ESTADO_CIVIL_EXIGE_COMPROVACAO
                or applicant.process_indicates_spouse_or_partner
                or triggered_by_document
            )

        if item.code == _CODE_PROCURACAO:
            return (
                applicant.has_representative
                or applicant.has_civil_incapacity
                or applicant.has_disability_requiring_legal_representative
                or triggered_by_document
            )

        # Condicional desconhecido: aplicável apenas se houver documento-gatilho.
        return triggered_by_document

    @staticmethod
    def _result(
        item: ChecklistItemConfig,
        status: ChecklistStatus,
        document: ClassifiedDocument | None = None,
        warning: str | None = None,
    ) -> ChecklistItemResult:
        warnings = [warning] if warning else []
        return ChecklistItemResult(
            code=item.code,
            label=item.label,
            required=item.required,
            status=status,
            page=document.page_start if document else None,
            evidence=document.evidence if document else None,
            confidence=document.confidence if document else 1.0,
            warnings=warnings,
        )
