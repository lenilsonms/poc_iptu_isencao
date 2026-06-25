"""Fixture do caso-ouro SEI 1101.2023/0005737-8.

Representa os FATOS já extraídos do processo (como se PDF/OCR/LLM já tivessem rodado),
fielmente ao gabarito da seção 13.2 do documento de requisitos — porém usando os CÓDIGOS
CANÔNICOS do checklist congelado (P0):

    EXTRATO_RENDIMENTO_FONTE_PAGADORA   (não 'EXTRATO_RENDIMENTO')
    IRPF_OU_DECLARACAO_ISENTO           (não 'IRPF_OU_ISENTO')

Cenário: aposentado, exercício 2024, proprietário, múltiplas inscrições; comprovante de
residência NÃO apresentado; extrato de rendimento a verificar; indício de outra renda
(JUCESP/MEI) sem comprovação. Resultado oficial: INDEFERIDO.
"""

from __future__ import annotations

from poc_iptu.domain import (
    BenefitType,
    ChecklistItemResult,
    ChecklistStatus,
    IncomeAnalysis,
    IncomeStatus,
    ProcessAnalysisInput,
    PropertyQualification,
    PropertyRelationshipType,
    RequestIdentification,
)


def build_golden_case_5737() -> ProcessAnalysisInput:
    """Monta o ProcessAnalysisInput do caso-ouro."""
    request = RequestIdentification(
        benefit_type=BenefitType.APOSENTADO,
        requested_year=2024,
        explicit_decree_mention="Decreto nº 34.767/2018",
        page=1,
    )

    property_qualification = PropertyQualification(
        registration_number="111.62.26.0166.01.000",
        relationship_type=PropertyRelationshipType.PROPRIETARIO,
        multiple_inscriptions_detected=True,
        residence_confirmed=False,
    )

    income = IncomeAnalysis(
        benefit_condition=BenefitType.APOSENTADO,
        benefit_document_found=True,
        income_document_found=False,
        other_sources_flag="JUCESP_MEI",
        income_status=IncomeStatus.VERIFICAR,
    )

    checklist = [
        ChecklistItemResult(
            code="DOCUMENTO_IDENTIFICACAO",
            label="Documento de identificação oficial do requerente",
            required=True,
            status=ChecklistStatus.OK,
            page=3,
            evidence="RG de MIGUEL ANGEL CAMACHO VISCARRA localizado na folha.",
            confidence=0.98,
        ),
        ChecklistItemResult(
            code="DOCUMENTO_IMOVEL",
            label="Documento que comprove vínculo com o imóvel",
            required=True,
            status=ChecklistStatus.OK,
            page=5,
            evidence="Matrícula do imóvel inscrição 111.62.26.0166.01.000.",
            confidence=0.93,
        ),
        ChecklistItemResult(
            code="CARTA_CONCESSAO_BENEFICIO",
            label="Carta de concessão do benefício previdenciário ou assistencial",
            required=True,
            status=ChecklistStatus.OK,
            page=7,
            evidence="Carta de concessão de aposentadoria do INSS.",
            confidence=0.95,
        ),
        # Item determinante 1: extrato de rendimento da fonte pagadora -> VERIFICAR
        # (há apenas documento parecido / insuficiente; carta de concessão não substitui).
        ChecklistItemResult(
            code="EXTRATO_RENDIMENTO_FONTE_PAGADORA",
            label="Extrato atualizado de rendimento da fonte pagadora",
            required=True,
            status=ChecklistStatus.VERIFICAR,
            page=7,
            evidence="Documento de renda presente parece insuficiente para o extrato exigido.",
            confidence=0.80,
        ),
        # Item determinante 2: comprovante de residência -> NÃO APRESENTADO.
        ChecklistItemResult(
            code="COMPROVANTE_RESIDENCIA",
            label="Comprovante de residência",
            required=True,
            status=ChecklistStatus.NAO_APRESENTADO,
            page=None,
            evidence=None,
            confidence=0.99,
        ),
        # Item determinante 3: outras rendas disparado por JUCESP/MEI -> VERIFICAR.
        ChecklistItemResult(
            code="COMPROVANTE_OUTRAS_RENDAS",
            label="Comprovação de proventos de diversas fontes",
            required=False,
            status=ChecklistStatus.VERIFICAR,
            page=11,
            evidence="Ficha cadastral JUCESP indica atividade econômica; proventos não comprovados.",
            confidence=0.88,
        ),
        ChecklistItemResult(
            code="IRPF_OU_DECLARACAO_ISENTO",
            label="Declaração de IRPF ou declaração de isento",
            required=True,
            status=ChecklistStatus.OK,
            page=13,
            evidence="Declaração de isento de IRPF apresentada.",
            confidence=0.90,
        ),
    ]

    return ProcessAnalysisInput(
        request=request,
        property=property_qualification,
        income=income,
        checklist=checklist,
    )
