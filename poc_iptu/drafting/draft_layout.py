"""Layout canônico da minuta — elementos estruturais compartilhados.

Fonte única do cabeçalho, títulos numerados, rodapé, rótulos de status e da seção de
rastreabilidade. Tanto o redator determinístico quanto o redator LLM compõem a minuta
sobre este esqueleto: o LLM jamais controla a estrutura, apenas o texto discursivo.
"""

from __future__ import annotations
import re
from ..domain.enums import ChecklistStatus
from ..domain.pipeline_models import ProcessAnalysisResult

FOOTER = (
    "Observação: esta minuta foi gerada por assistente de IA e deve ser revisada pela "
    "autoridade competente antes de qualquer ato oficial."
)

NORMA_BASE = "Lei Municipal nº 4.158/1992"

SECTION_TITLES: dict[str, str] = {
    "RELATORIO": "RELATÓRIO",
    "ADMISSIBILIDADE": "ADMISSIBILIDADE",
    "ANALISE_DOCUMENTAL": "ANÁLISE DOCUMENTAL E MATERIAL",
    "CONCLUSAO": "CONCLUSÃO SUGERIDA",
    "CIENCIA_E_RECURSO": "CIÊNCIA E RECURSO",
    "RASTREABILIDADE": "RASTREABILIDADE",
}

STATUS_LABELS: dict[ChecklistStatus, str] = {
    ChecklistStatus.OK: "Regular",
    ChecklistStatus.NAO_APRESENTADO: "Não apresentado",
    ChecklistStatus.VERIFICAR: "A verificar",
    ChecklistStatus.NAO_APLICAVEL: "Não aplicável",
}

_ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def section_title(index: int, code: str) -> str:
    """Título numerado em romano (ex.: 'III. ANÁLISE DOCUMENTAL E MATERIAL')."""
    roman = _ROMAN[index] if index < len(_ROMAN) else str(index)
    return f"{roman}. {SECTION_TITLES.get(code, code)}"


def status_label(status: ChecklistStatus) -> str:
    return STATUS_LABELS.get(status, status.value)


def has_anchored_page(item) -> bool:
    """Invariante anti-alucinação: só existe página citável com evidência ancorada."""
    return item.page is not None and bool(item.evidence)


def apply_cpf_mask(cpf: str | None) -> str | None:
    """Aplica a máscara padrão ao CPF antes de inseri-lo na minuta."""
    if not cpf:
        return cpf
    if "*" in cpf:
        return cpf
    digits = re.sub(r"\D", "", cpf)
    if len(digits) == 11:
        return f"***.{digits[3:6]}.{digits[6:9]}-**"
    return "***.***.***-**"


def render_header(result: ProcessAnalysisResult) -> str:
    """Cabeçalho oficial — sempre determinístico."""
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


def render_rastreabilidade(result: ProcessAnalysisResult) -> str:
    """Seção de auditoria — sempre determinística (o LLM não escreve metadados)."""
    meta = result.metadata
    lines = ["Itens verificados (código | status | página | evidência):", ""]
    for item in result.checklist:
        page = f"pág. {item.page}" if has_anchored_page(item) else "—"
        evidence = item.evidence if has_anchored_page(item) else "—"
        lines.append(f"- {item.code} | {status_label(item.status)} | {page} | {evidence}")
    lines.extend(
        [
            "",
            "Parâmetros da análise:",
            f"- ID da análise: {meta.analysis_id}",
            f"- Data/hora (UTC): {meta.created_at.isoformat()}",
            f"- Versões de configuração: legal_references {meta.legal_references_version}; "
            f"business_rules {meta.business_rules_version}; checklist {meta.checklist_version}",
            f"- Prompts: {meta.prompt_version}",
            f"- LLM: {meta.llm_provider}/{meta.llm_model} | OCR: {meta.ocr_engine}",
            f"- Semântica de página: {meta.source_page_semantics}",
            f"- Política de PII: {meta.pii_policy}",
            f"- Páginas do PDF: {result.total_page_count} (processadas por OCR: "
            f"{result.ocr_page_count})",
        ]
    )
    return "\n".join(lines)
