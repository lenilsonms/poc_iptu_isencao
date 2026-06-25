"""Adapters de LLM para DEMONSTRAÇÃO OFFLINE (sem Azure).

Devolvem a classificação e a extração do caso-ouro SEI 5737 independentemente do PDF enviado.
Servem para demonstrar o pipeline completo quando o Azure OpenAI não está configurado. A UI
deixa claro que está em "modo demonstração". Para análise real de um PDF arbitrário, use os
adapters Azure.

Fonte única dos dados do caso-ouro: este módulo é reutilizado pelos testes.
"""

from __future__ import annotations

from ...domain.enums import (
    BenefitType,
    IncomeStatus,
    PropertyRelationshipType,
)
from ...domain.models import (
    IncomeAnalysis,
    PropertyQualification,
    RequestIdentification,
)
from ...domain.pipeline_models import (
    ApplicantQualification,
    ClassifiedDocument,
    ExtractedDocument,
    ExtractedFields,
)
from ...ports.document_classification import DocumentClassificationPort
from ...ports.field_extraction import FieldExtractionPort


def golden_case_classified_documents() -> list[ClassifiedDocument]:
    """Documentos classificados do caso-ouro (com a CARTA no lugar do extrato próprio)."""

    def doc(document_type: str, page: int, evidence: str, confidence: float) -> ClassifiedDocument:
        return ClassifiedDocument(
            document_type=document_type,
            page_start=page,
            page_end=page,
            evidence=evidence,
            confidence=confidence,
        )

    return [
        doc("RG", 3, "RG do requerente localizado.", 0.98),
        doc("MATRICULA_IMOVEL", 5, "Matrícula do imóvel inscrição 111.62.26.0166.01.000.", 0.93),
        doc("CARTA_CONCESSAO_BENEFICIO", 7, "Carta de concessão de aposentadoria do INSS.", 0.95),
        doc("DECLARACAO_ISENTO_IRPF", 13, "Declaração de isento de IRPF.", 0.90),
        doc("DECLARACAO_OCUPACAO_IMOVEIS", 14, "Declaração do regime de ocupação dos imóveis.", 0.92),
        doc("CARNE_IPTU", 15, "Carnê de IPTU do exercício.", 0.94),
        doc("JUCESP_FICHA_CADASTRAL", 11, "Ficha cadastral JUCESP indica atividade econômica.", 0.88),
    ]


def golden_case_extracted_fields() -> ExtractedFields:
    """Campos extraídos do caso-ouro."""
    return ExtractedFields(
        request=RequestIdentification(
            benefit_type=BenefitType.APOSENTADO,
            requested_year=2024,
            explicit_decree_mention="Decreto nº 34.767/2018",
            page=1,
        ),
        applicant=ApplicantQualification(
            name="MIGUEL ANGEL CAMACHO VISCARRA",
            cpf_masked="***.***.***-**",
        ),
        property=PropertyQualification(
            registration_number="111.62.26.0166.01.000",
            relationship_type=PropertyRelationshipType.PROPRIETARIO,
            multiple_inscriptions_detected=True,
            residence_confirmed=False,
        ),
        income=IncomeAnalysis(
            benefit_condition=BenefitType.APOSENTADO,
            benefit_document_found=True,
            income_document_found=False,
            other_sources_flag="JUCESP_MEI",
            income_status=IncomeStatus.VERIFICAR,
        ),
    )


class OfflineDemoClassification(DocumentClassificationPort):
    """Classificação fixa (caso-ouro) para demonstração sem Azure."""

    def classify(self, document: ExtractedDocument) -> list[ClassifiedDocument]:
        return golden_case_classified_documents()


class OfflineDemoExtraction(FieldExtractionPort):
    """Extração fixa (caso-ouro) para demonstração sem Azure."""

    def extract(
        self,
        document: ExtractedDocument,
        classified_documents: list[ClassifiedDocument],
    ) -> ExtractedFields:
        return golden_case_extracted_fields()
