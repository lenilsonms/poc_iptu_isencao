"""Geração determinística da minuta de decisão administrativa de 1ª instância.

Responsabilidade única: a partir de um `ProcessAnalysisResult` (já produzido pelo caso de uso)
e do `conclusion_mapping.yaml`, montar a minuta revisável. NÃO usa LLM: todo o conteúdo
jurídico vem do resultado determinístico e dos textos canônicos da configuração.

Guardrails desta camada:
  - a minuta NUNCA escreve "DEFIRO" (no máximo, aptidão à análise de deferimento — art. 5.2 do requisito);
  - o CPF circula MASCARADO; um CPF aparentemente não mascarado é rejeitado;
  - nenhuma página do PDF é citada sem evidência ancorada (invariante anti-alucinação);
  - minutas de mérito SEMPRE contêm a seção de ciência/recurso.

Conclusões sem mérito (FORA_DO_ESCOPO_POC) geram apenas um aviso curto, sem seções de mérito.
"""

from __future__ import annotations

import re

from ..config.schemas import ConclusionMappingConfig
from ..domain.enums import ChecklistStatus, ConclusionStatus
from ..domain.errors import PocIptuError
from ..domain.pipeline_models import (
    ApplicantQualification,
    DecisionDraft,
    DraftSection,
    ProcessAnalysisResult,
)

from ..ports.decision_drafting import DecisionDraftingPort
from . import draft_layout
from .draft_layout import apply_cpf_mask
from .draft_guardrails import DraftGuardrailValidator, DraftGuardrailViolation

_FORBIDDEN_DECISION_PATTERN = re.compile(r"\bDEFIRO\b")
_NORMA_BASE = "Lei Municipal nº 4.158/1992"
_FOOTER = (
    "Observação: esta minuta foi gerada por assistente de IA e deve ser revisada pela "
    "autoridade competente antes de qualquer ato oficial."
)

_SECTION_TITLES: dict[str, str] = {
    "RELATORIO": "RELATÓRIO",
    "ADMISSIBILIDADE": "ADMISSIBILIDADE",
    "ANALISE_DOCUMENTAL": "ANÁLISE DOCUMENTAL E MATERIAL",
    "CONCLUSAO": "CONCLUSÃO SUGERIDA",
    "CIENCIA_E_RECURSO": "CIÊNCIA E RECURSO",
    "RASTREABILIDADE": "RASTREABILIDADE",
}

_STATUS_LABELS: dict[ChecklistStatus, str] = {
    ChecklistStatus.OK: "Regular",
    ChecklistStatus.NAO_APRESENTADO: "Não apresentado",
    ChecklistStatus.VERIFICAR: "A verificar",
    ChecklistStatus.NAO_APLICAVEL: "Não aplicável",
}

_ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


class DraftGenerationError(PocIptuError):
    """Falha ou violação de guardrail ao gerar a minuta."""


class DecisionDraftService:
    """Gera a minuta de decisão a partir do resultado da análise e do conclusion_mapping."""

    def __init__(self, conclusion_mapping: ConclusionMappingConfig) -> None:
        self._config = conclusion_mapping
        self._guardrails = DraftGuardrailValidator()
        self._renderers = {
            "RELATORIO": self._render_relatorio,
            "ADMISSIBILIDADE": self._render_admissibilidade,
            "ANALISE_DOCUMENTAL": self._render_analise_documental,
            "CONCLUSAO": self._render_conclusao,
            "CIENCIA_E_RECURSO": self._render_ciencia_recurso,
            "RASTREABILIDADE": self._render_rastreabilidade,
        }

    def generate(self, result: ProcessAnalysisResult) -> DecisionDraft:
        state_config = self._state_config(result.conclusion.status)
        header = self._render_header(result)

        if not state_config.generate_merit_draft:
            text = "\n\n".join([header, state_config.draft_text, draft_layout.FOOTER])
            # SANITIZAÇÃO GLOBAL
            text = re.sub(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", "***.***.***-**", text)
            return DecisionDraft(status=result.conclusion.status,
                                 is_merit_draft=False, sections=[], text=text)

        sections = self._render_sections(result)
        text = self._compose_text(header, sections)
        
        # SANITIZAÇÃO GLOBAL ANTES DO GUARDRAIL
        text = re.sub(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", "***.***.***-**", text)
        
        try:
            self._guardrails.validate_merit_draft(text, result)
        except DraftGuardrailViolation as exc:
            raise DraftGenerationError(str(exc)) from exc
            
        return DecisionDraft(status=result.conclusion.status,
                             is_merit_draft=True, sections=sections, text=text)

    # --------------------------------------------------------------- montagem

    def _render_sections(self, result: ProcessAnalysisResult) -> list[DraftSection]:
        sections: list[DraftSection] = []
        for index, code in enumerate(self._config.mandatory_sections, start=1):
            renderer = self._renderers.get(code)
            if renderer is None:
                raise DraftGenerationError(
                    f"Seção obrigatória sem renderizador definido: '{code}'."
                )
            sections.append(
                DraftSection(code=code, title=self._title(index, code), body=renderer(result))
            )
        return sections

    def _compose_text(self, header: str, sections: list[DraftSection]) -> str:
        blocks = [header]
        for section in sections:
            blocks.append(f"{section.title}\n{section.body}")
        blocks.append(_FOOTER)
        return "\n\n".join(blocks)

    @staticmethod
    def _title(index: int, code: str) -> str:
        roman = _ROMAN[index] if index < len(_ROMAN) else str(index)
        name = _SECTION_TITLES.get(code, code)
        return f"{roman}. {name}"

    # --------------------------------------------------------------- seções

    @staticmethod
    def _render_header(result: ProcessAnalysisResult) -> str:
        cpf_raw = result.applicant.cpf_masked
        cpf = apply_cpf_mask(cpf_raw) or "(não informado)" # <-- APLICAR MÁSCARA AQUI
        registration = result.property.registration_number or "(não informada)"
        return "\n".join(
            [
                "DECISÃO ADMINISTRATIVA DE 1ª INSTÂNCIA",
                "",
                f"PAT: {result.process_id}",
                "Assunto: Isenção de IPTU – Aposentados, Pensionistas e Beneficiários do LOAS",
                f"Requerente: {result.applicant.name} | CPF: {cpf} | "
                f"Inscrição Imobiliária: {registration}",
                f"Exercício: {result.request.requested_year}",
            ]
        )

    def _render_relatorio(self, result: ProcessAnalysisResult) -> str:
        regime_label = self._regime_label(result)
        suffix = f", em especial o {regime_label}" if regime_label else ""
        return (
            f"Trata-se de pedido de isenção de IPTU referente ao exercício de "
            f"{result.request.requested_year}, apresentado por {result.applicant.name}, "
            f"analisado sob a égide da {_NORMA_BASE} e do regime regulamentar aplicável ao "
            f"processo{suffix}."
        )

    @staticmethod
    def _render_admissibilidade(result: ProcessAnalysisResult) -> str:
        relationship = result.property.relationship_type.value
        sentences = [
            "Foram analisados os elementos de qualificação do requerente, sua legitimidade, "
            "a representação (quando aplicável) e o vínculo com o imóvel, qualificado como "
            f"{relationship}.",
        ]
        if result.property.multiple_inscriptions_detected:
            sentences.append(
                "Registra-se a detecção de múltiplas inscrições imobiliárias, recomendando-se "
                "a conferência manual da inscrição efetivamente pleiteada."
            )
        if result.applicant.has_representative:
            sentences.append(
                "O pedido envolve representação, cuja regularidade deve ser conferida."
            )
        sentences.append("Os achados constam da tabela de rastreabilidade.")
        return " ".join(sentences)

    def _render_analise_documental(self, result: ProcessAnalysisResult) -> str:
        lines = [
            "A documentação apresentada foi confrontada com o checklist parametrizado para o "
            "regime legal aplicável. Foram identificados os seguintes status:",
            "",
        ]
        for item in result.checklist:
            page_ref = self._page_reference(item)
            lines.append(f"- {item.label}: {self._status_label(item.status)}{page_ref}")
        return "\n".join(lines)

    def _render_conclusao(self, result: ProcessAnalysisResult) -> str:
        conclusion = result.conclusion
        body = [self._state_config(conclusion.status).draft_text]
        if conclusion.legal_basis:
            body.append(
                "Fundamento normativo utilizado: " + "; ".join(conclusion.legal_basis) + "."
            )
        if conclusion.missing_required_documents:
            body.append(
                "Documento(s) obrigatório(s) não apresentado(s): "
                + ", ".join(conclusion.missing_required_documents)
                + "."
            )
        if conclusion.items_to_verify:
            body.append("Itens a verificar: " + ", ".join(conclusion.items_to_verify) + ".")
        return "\n\n".join(body)

    def _render_ciencia_recurso(self, result: ProcessAnalysisResult) -> str:
        if not self._config.appeal_notice_enabled or not self._config.appeal_notice_text.strip():
            raise DraftGenerationError(
                "Minuta de mérito exige seção de ciência/recurso, mas appeal_notice está "
                "desabilitado ou vazio no conclusion_mapping.yaml."
            )
        return self._config.appeal_notice_text.strip()

    def _render_rastreabilidade(self, result: ProcessAnalysisResult) -> str:
        meta = result.metadata
        lines = ["Itens verificados (código | status | página | evidência):", ""]
        for item in result.checklist:
            page = f"pág. {item.page}" if self._has_anchored_page(item) else "—"
            evidence = item.evidence if self._has_anchored_page(item) else "—"
            lines.append(
                f"- {item.code} | {self._status_label(item.status)} | {page} | {evidence}"
            )
        lines.extend(
            [
                "",
                "Parâmetros da análise:",
                f"- ID da análise: {meta.analysis_id}",
                f"- Data/hora (UTC): {meta.created_at.isoformat()}",
                f"- Versões de configuração: legal_references {meta.legal_references_version}; "
                f"business_rules {meta.business_rules_version}; checklist {meta.checklist_version}",
                f"- LLM: {meta.llm_provider}/{meta.llm_model} | OCR: {meta.ocr_engine}",
                f"- Fundamento aplicado: {self._regime_label(result) or '—'}",
                f"- Semântica de página: {meta.source_page_semantics}",
                f"- Política de PII: {meta.pii_policy}",
                f"- Páginas do PDF: {result.total_page_count} (processadas por OCR: "
                f"{result.ocr_page_count})",
            ]
        )
        return "\n".join(lines)

    # --------------------------------------------------------------- helpers

    def _state_config(self, status: ConclusionStatus):
        state = self._config.states.get(status)
        if state is None:
            raise DraftGenerationError(
                f"Estado de conclusão sem mapeamento no conclusion_mapping.yaml: {status.value}."
            )
        return state

    @staticmethod
    def _status_label(status: ChecklistStatus) -> str:
        return _STATUS_LABELS.get(status, status.value)

    @staticmethod
    def _has_anchored_page(item) -> bool:
        """Invariante: só há página citável quando existe evidência ancorada."""
        return item.page is not None and bool(item.evidence)

    def _page_reference(self, item) -> str:
        return f" — página {item.page} do PDF" if self._has_anchored_page(item) else ""

    @staticmethod
    def _regime_label(result: ProcessAnalysisResult) -> str | None:
        """Extrai o nome do decreto a partir do fundamento legal (ex.: 'Decreto nº 34.767/2018')."""
        names: list[str] = []
        for entry in result.conclusion.legal_basis:
            decree_name = entry.split(", art")[0].strip()
            if decree_name and decree_name not in names:
                names.append(decree_name)
        return "; ".join(names) if names else None

    @staticmethod
    def _assert_cpf_masked(applicant: ApplicantQualification) -> None:
        cpf = applicant.cpf_masked
        if cpf is None:
            return
        digit_count = sum(character.isdigit() for character in cpf)
        if digit_count >= 11:
            raise DraftGenerationError(
                "CPF aparentemente não mascarado na minuta; a saída deve usar CPF mascarado."
            )

    @staticmethod
    def _assert_no_forbidden_decision(text: str) -> None:
        if _FORBIDDEN_DECISION_PATTERN.search(text):
            raise DraftGenerationError(
                "A minuta não pode conter a decisão 'DEFIRO'; o máximo permitido é indicar "
                "aptidão à análise de deferimento pela autoridade competente."
            )
