"""Modelos da etapa de extração (lado de entrada do pipeline) e o resultado agregado.

Estes modelos atravessam as portas: o adapter de PDF produz `ExtractedDocument`; as portas de
LLM produzem `ClassifiedDocument` e `ExtractedFields`; o caso de uso consolida tudo em
`ProcessAnalysisResult`. Todos imutáveis, como o restante do domínio.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field

from .enums import ConclusionStatus
from .models import (
    ConclusionResult,
    IncomeAnalysis,
    PropertyQualification,
    RequestIdentification,
    _Frozen,
)


class PageSource(str, Enum):
    """Origem do texto de uma página: extração textual direta ou OCR."""

    PDF_TEXT = "PDF_TEXT"
    OCR = "OCR"


class ExtractedPage(_Frozen):
    """Uma página do PDF, com seu texto e a origem do texto."""

    page_number: int
    text: str
    source: PageSource


class ExtractedDocument(_Frozen):
    """O PDF inteiro, consolidado em páginas. Semântica de página = 'página do PDF'."""

    file_name: str
    pages: list[ExtractedPage]

    @property
    def ocr_page_count(self) -> int:
        return sum(1 for page in self.pages if page.source == PageSource.OCR)


class ClassifiedDocument(_Frozen):
    """Documento identificado dentro do PDF, com evidência ancorada.

    `document_type` é o código da taxonomia (document_taxonomy.yaml). Mantido como string
    para não acoplar a um enum que tende a defasar frente à taxonomia (fonte da verdade).
    """

    document_type: str
    page_start: int
    page_end: int
    title_detected: str | None = None
    text_excerpt: str = ""
    confidence: float = 1.0
    evidence: str = ""


class ApplicantQualification(_Frozen):
    """Qualificação do requerente. O CPF circula MASCARADO nesta camada (UI/minuta/logs)."""

    name: str
    cpf_masked: str | None = Field(default=None, alias="cpf_row")
    estado_civil: str | None = None
    process_indicates_spouse_or_partner: bool = False
    has_representative: bool = False
    has_civil_incapacity: bool = False
    has_disability_requiring_legal_representative: bool = False


class ExtractedFields(_Frozen):
    """Campos estruturados extraídos do processo (saída da porta de extração)."""

    request: RequestIdentification
    applicant: ApplicantQualification
    property: PropertyQualification
    income: IncomeAnalysis


class AnalysisMetadata(_Frozen):
    """Metadados de auditoria/rastreabilidade da análise."""

    analysis_id: str
    created_at: datetime
    app_version: str
    legal_references_version: str
    business_rules_version: str
    checklist_version: str
    llm_provider: str
    llm_model: str
    ocr_engine: str
    pii_policy: str
    prompt_version: str = "n/a"
    source_page_semantics: str = "PDF_PAGE"


class ProcessAnalysisResult(_Frozen):
    """Resultado completo da análise de um processo. NÃO é decisão final."""

    process_id: str
    file_name: str
    request: RequestIdentification
    applicant: ApplicantQualification
    property: PropertyQualification
    income: IncomeAnalysis
    documents: list[ClassifiedDocument]
    checklist: list  # list[ChecklistItemResult] — evita import circular de tipagem estrita
    conclusion: ConclusionResult
    metadata: AnalysisMetadata
    draft_text: str | None = None
    ocr_page_count: int = 0
    total_page_count: int = 0


class DraftSection(_Frozen):
    """Uma seção numerada da minuta (ex.: RELATORIO, CONCLUSAO, CIENCIA_E_RECURSO)."""

    code: str
    title: str
    body: str


class DecisionDraft(_Frozen):
    """Minuta de decisão administrativa de 1ª instância. Sempre revisável por humano."""

    status: ConclusionStatus
    is_merit_draft: bool
    sections: list[DraftSection]
    text: str
