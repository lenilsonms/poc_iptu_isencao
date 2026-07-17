"""Layout canônico da minuta — elementos estruturais compartilhados.

Fonte única do cabeçalho, títulos numerados, rodapé, rótulos de status e da seção de
rastreabilidade. Tanto o redator determinístico quanto o redator LLM compõem a minuta
sobre este esqueleto: o LLM jamais controla a estrutura, apenas o texto discursivo.
"""

from __future__ import annotations
import re
from ..domain.enums import ChecklistStatus
from ..domain.pipeline_models import ProcessAnalysisResult
from ..domain.enums import PropertyRelationshipType

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

RELATIONSHIP_LABELS: dict[PropertyRelationshipType, str] = {
    PropertyRelationshipType.PROPRIETARIO: "Proprietário(a)",
    PropertyRelationshipType.COPROPRIETARIO: "Coproprietário(a)",
    PropertyRelationshipType.COMPROMISSARIO: "Compromissário(a)",
    PropertyRelationshipType.TITULAR_DOMINIO_UTIL: "Titular do domínio útil",
    PropertyRelationshipType.POSSUIDOR: "Possuidor(a)",
    PropertyRelationshipType.CESSIONARIO: "Cessionário(a)",
    PropertyRelationshipType.USUFRUTUARIO: "Usufrutuário(a)",
    PropertyRelationshipType.VERIFICAR: "A verificar",
}

_SIRF_INSCRIPTION_GROUPS = (3, 2, 2, 4, 2, 3)  # 000.00.00.0000.00.000 (15 dígitos)

def relationship_label(relationship: PropertyRelationshipType) -> str:
    return RELATIONSHIP_LABELS.get(relationship, relationship.value)

def format_inscricao_sirf(raw_inscription: str | None) -> str:
    """Normaliza a inscrição imobiliária para o padrão SIRF WEB 000.00.00.0000.00.000.

    Se o valor não tiver exatamente 15 dígitos, devolve o original inalterado —
    nunca inventamos dígitos num identificador cadastral.
    """
    if not raw_inscription:
        return "(não informada)"
    digits = "".join(ch for ch in raw_inscription if ch.isdigit())
    if len(digits) != sum(_SIRF_INSCRIPTION_GROUPS):
        return raw_inscription
    parts, cursor = [], 0
    for size in _SIRF_INSCRIPTION_GROUPS:
        parts.append(digits[cursor:cursor + size])
        cursor += size
    return ".".join(parts)

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
            "PREFEITURA MUNICIPAL DE GUARULHOS",
            "SECRETARIA DA RECEITA – SRC",
            "",
            "DECISÃO ADMINISTRATIVA DE 1ª INSTÂNCIA",
            "",
            f"Processo nº: {result.process_id}",
            "Assunto: Isenção de IPTU – Aposentados, Pensionistas e Beneficiários do LOAS",
            f"Requerente: {result.applicant.name}",
            f"CPF: {cpf}",
            f"Inscrição Cadastral: {format_inscricao_sirf(registration)}",
            f"Vínculo: {relationship_label(result.property.relationship_type)}",
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
