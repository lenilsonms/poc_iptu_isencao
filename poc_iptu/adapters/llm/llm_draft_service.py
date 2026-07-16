"""Redator de minuta via LLM, com guardrails e fallback determinístico.

Arquitetura híbrida:
  - o LLM redige SOMENTE as seções discursivas (relatório, admissibilidade, análise
    documental e conclusão), a partir do resultado determinístico já consolidado;
  - o esqueleto (cabeçalho, títulos, ciência/recurso canônica, rastreabilidade, rodapé)
    permanece determinístico (draft_layout);
  - o texto final passa pelo DraftGuardrailValidator; qualquer violação, erro de
    transporte ou de contrato aciona o fallback determinístico — a análise NUNCA fica
    sem minuta por falha do LLM.
"""

from __future__ import annotations
import re
import json
import logging

from ...config.schemas import ConclusionMappingConfig
from ...domain.pipeline_models import DecisionDraft, DraftSection, ProcessAnalysisResult
from ...drafting import draft_layout
from ...drafting.decision_draft_service import DecisionDraftService
from ...drafting.draft_guardrails import DraftGuardrailValidator, DraftGuardrailViolation
from ...ports.decision_drafting import DecisionDraftingPort
from .chat_client import ChatCompletionClient, LlmTransportError
from .prompt_library import PromptLibrary
from .serialization import LlmResponseError, parse_json_object
from ...drafting.draft_layout import apply_cpf_mask

logger = logging.getLogger(__name__)

# Seções que o LLM redige; as demais são sempre determinísticas.
_LLM_AUTHORED_SECTIONS = ("RELATORIO", "ADMISSIBILIDADE", "ANALISE_DOCUMENTAL", "CONCLUSAO")


class LlmDecisionDraftService(DecisionDraftingPort):
    """Gera a minuta com redação do LLM sobre o esqueleto determinístico."""

    def __init__(
        self,
        chat_client: ChatCompletionClient,
        prompts: PromptLibrary,
        conclusion_mapping: ConclusionMappingConfig,
        fallback: DecisionDraftService,
    ) -> None:
        if prompts.drafting is None:
            raise LlmResponseError(
                "prompts.yaml não define a seção 'drafting'; atualize para a versão "
                "1.1.0-poc-llm-draft ou superior."
            )
        self._chat = chat_client
        self._prompts = prompts
        self._config = conclusion_mapping
        self._fallback = fallback
        self._guardrails = DraftGuardrailValidator()

    # ------------------------------------------------------------------ público

    def generate(self, result: ProcessAnalysisResult) -> DecisionDraft:
        state_config = self._config.states.get(result.conclusion.status)
        if state_config is None or not state_config.generate_merit_draft:
            # Estados sem mérito (FORA_DO_ESCOPO_POC) não passam pelo LLM.
            return self._fallback.generate(result)

        try:
            return self._generate_with_llm(result, state_config.draft_text)
        except (LlmTransportError, LlmResponseError, DraftGuardrailViolation) as exc:
            # Falha do LLM não pode derrubar a análise: rebaixa para o determinístico.
            logger.warning(
                "Minuta LLM indisponível ou reprovada nos guardrails (%s); "
                "usando redator determinístico. process_id=%s",
                exc, result.process_id,
            )
            return self._fallback.generate(result)

    # ----------------------------------------------------------------- pipeline

    import re  # Certifique-se de que isto está no topo do arquivo

# ... role até o método _generate_with_llm ...

    def _generate_with_llm(
        self, result: ProcessAnalysisResult, state_draft_text: str
    ) -> DecisionDraft:
        template = self._prompts.drafting
        user_prompt = template.render(
            {
                "ANALYSIS_JSON": self._serialize_analysis_context(result),
                "STATE_DRAFT_TEXT": state_draft_text,
                "ANCHORED_PAGES": self._render_anchored_pages(result),
            }
        )
        content = self._chat.complete(
            template.system, user_prompt, temperature=self._prompts.temperature
        )
        section_bodies = self._parse_sections(content)
        sections = self._compose_sections(result, section_bodies)
        text = self._compose_text(result, sections)

        # SANITIZAÇÃO GLOBAL ANTES DO GUARDRAIL
        text = re.sub(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", "***.***.***-**", text)

        # Última linha de defesa: guardrails sobre o TEXTO FINAL.
        self._guardrails.validate_merit_draft(text, result)

        return DecisionDraft(
            status=result.conclusion.status,
            is_merit_draft=True,
            sections=sections,
            text=text,
        )

    # ------------------------------------------------------------- serialização

    @staticmethod
    def _serialize_analysis_context(result: ProcessAnalysisResult) -> str:
        """Contexto compacto e SEM PII bruta para o prompt de redação."""
        payload = {
           "process_id": result.process_id,
            "request": {
                "benefit_type": result.request.benefit_type.value,
                "requested_year": result.request.requested_year,
                "explicit_decree_mention": result.request.explicit_decree_mention,
            },
            "applicant": {
                "name": result.applicant.name,
                "cpf_masked": apply_cpf_mask(result.applicant.cpf_masked), # <-- APLICAR MÁSCARA AQUI
                "has_representative": result.applicant.has_representative,
            },
            "property": {
                "registration_number": result.property.registration_number,
                "relationship_type": result.property.relationship_type.value,
                "multiple_inscriptions_detected": result.property.multiple_inscriptions_detected,
            },
            "income": {
                "income_status": result.income.income_status.value,
                "other_sources_flag": result.income.other_sources_flag,
            },
            "conclusion": {
                "status": result.conclusion.status.value,
                "main_reason": result.conclusion.main_reason,
                "missing_required_documents": result.conclusion.missing_required_documents,
                "items_to_verify": result.conclusion.items_to_verify,
                "legal_basis": result.conclusion.legal_basis,
                "warnings": result.conclusion.warnings,
            },
            "checklist": [
                {
                    "code": item.code,
                    "label": item.label,
                    "required": item.required,
                    "status": item.status.value,
                    "page": item.page if draft_layout.has_anchored_page(item) else None,
                    "evidence": item.evidence if draft_layout.has_anchored_page(item) else None,
                }
                for item in result.checklist
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @staticmethod
    def _render_anchored_pages(result: ProcessAnalysisResult) -> str:
        pages = sorted(
            {item.page for item in result.checklist if draft_layout.has_anchored_page(item)}
        )
        return ", ".join(str(page) for page in pages) if pages else "(nenhuma)"

    # ----------------------------------------------------------------- parsing

    @staticmethod
    def _parse_sections(content: str) -> dict[str, str]:
        data = parse_json_object(content)
        raw_sections = data.get("sections")
        if not isinstance(raw_sections, dict):
            raise LlmResponseError("Campo 'sections' ausente ou inválido na minuta.")
        bodies: dict[str, str] = {}
        for code in _LLM_AUTHORED_SECTIONS:
            body = raw_sections.get(code)
            if not isinstance(body, str) or not body.strip():
                raise LlmResponseError(f"Seção '{code}' ausente ou vazia na resposta do LLM.")
            bodies[code] = body.strip()
        return bodies

    # ---------------------------------------------------------------- montagem

    def _compose_sections(
        self, result: ProcessAnalysisResult, llm_bodies: dict[str, str]
    ) -> list[DraftSection]:
        """Ordem e títulos vêm do conclusion_mapping; corpos do LLM ou do sistema."""
        deterministic_bodies = {
            "CIENCIA_E_RECURSO": self._config.appeal_notice_text.strip(),
            "RASTREABILIDADE": draft_layout.render_rastreabilidade(result),
        }
        sections: list[DraftSection] = []
        for index, code in enumerate(self._config.mandatory_sections, start=1):
            body = llm_bodies.get(code) or deterministic_bodies.get(code)
            if body is None:
                raise LlmResponseError(f"Seção obrigatória sem corpo definido: '{code}'.")
            sections.append(
                DraftSection(
                    code=code,
                    title=draft_layout.section_title(index, code),
                    body=body,
                )
            )
        return sections

    @staticmethod
    def _compose_text(result: ProcessAnalysisResult, sections: list[DraftSection]) -> str:
        blocks = [draft_layout.render_header(result)]
        blocks.extend(f"{section.title}\n{section.body}" for section in sections)
        blocks.append(draft_layout.FOOTER)
        return "\n\n".join(blocks)