"""Testes do montador determinístico de checklist."""

from __future__ import annotations

from pathlib import Path

import pytest

from poc_iptu.config import ConfigLoader
from poc_iptu.domain import (
    BenefitType,
    ChecklistStatus,
    ClassifiedDocument,
    IncomeAnalysis,
    IncomeStatus,
)
from poc_iptu.domain.pipeline_models import ApplicantQualification
from poc_iptu.rules import ChecklistAssembler

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@pytest.fixture(scope="module")
def assembler():
    config = ConfigLoader(CONFIG_DIR).load()
    return ChecklistAssembler(config.checklist)


def _doc(document_type: str, page: int = 1) -> ClassifiedDocument:
    return ClassifiedDocument(
        document_type=document_type,
        page_start=page,
        page_end=page,
        evidence=f"evidência de {document_type}",
        confidence=0.95,
    )


def _applicant() -> ApplicantQualification:
    return ApplicantQualification(name="Fulano de Tal")


def _income(status: IncomeStatus = IncomeStatus.OK, flag: str | None = None) -> IncomeAnalysis:
    return IncomeAnalysis(
        benefit_condition=BenefitType.APOSENTADO,
        benefit_document_found=True,
        income_document_found=status == IncomeStatus.OK,
        other_sources_flag=flag,
        income_status=status,
    )


def _by_code(items):
    return {item.code: item for item in items}


def test_documento_aceito_resulta_ok(assembler):
    items = assembler.assemble([_doc("RG", page=3)], _applicant(), _income())
    identificacao = _by_code(items)["DOCUMENTO_IDENTIFICACAO"]
    assert identificacao.status == ChecklistStatus.OK
    assert identificacao.page == 3
    assert identificacao.evidence


def test_documento_obrigatorio_ausente_resulta_nao_apresentado(assembler):
    items = assembler.assemble([_doc("RG")], _applicant(), _income())
    residencia = _by_code(items)["COMPROVANTE_RESIDENCIA"]
    assert residencia.status == ChecklistStatus.NAO_APRESENTADO


def test_documento_parecido_nao_satisfaz_vira_verificar(assembler):
    # Carta de concessão satisfaz seu próprio item, mas é parecida (não equivalente) ao extrato.
    items = _by_code(
        assembler.assemble([_doc("CARTA_CONCESSAO_BENEFICIO")], _applicant(), _income())
    )
    assert items["CARTA_CONCESSAO_BENEFICIO"].status == ChecklistStatus.OK
    assert items["EXTRATO_RENDIMENTO_FONTE_PAGADORA"].status == ChecklistStatus.VERIFICAR


def test_extrato_proprio_satisfaz(assembler):
    items = _by_code(assembler.assemble([_doc("EXTRATO_INSS")], _applicant(), _income()))
    assert items["EXTRATO_RENDIMENTO_FONTE_PAGADORA"].status == ChecklistStatus.OK


def test_condicional_nao_disparado_fica_nao_aplicavel(assembler):
    items = _by_code(assembler.assemble([_doc("RG")], _applicant(), _income()))
    assert items["COMPROVANTE_OUTRAS_RENDAS"].status == ChecklistStatus.NAO_APLICAVEL
    assert items["PROCURACAO"].status == ChecklistStatus.NAO_APLICAVEL


def test_outras_rendas_disparado_por_jucesp_vira_verificar(assembler):
    items = _by_code(
        assembler.assemble([_doc("JUCESP_FICHA_CADASTRAL")], _applicant(), _income())
    )
    assert items["COMPROVANTE_OUTRAS_RENDAS"].status == ChecklistStatus.VERIFICAR


def test_outras_rendas_disparado_por_flag_de_renda(assembler):
    items = _by_code(
        assembler.assemble(
            [_doc("RG")], _applicant(), _income(IncomeStatus.VERIFICAR, flag="JUCESP_MEI")
        )
    )
    assert items["COMPROVANTE_OUTRAS_RENDAS"].status == ChecklistStatus.VERIFICAR


def test_procuracao_aplicavel_quando_ha_representante(assembler):
    applicant = ApplicantQualification(name="Fulano", has_representative=True)
    items = _by_code(assembler.assemble([_doc("RG")], applicant, _income()))
    # Aplicável e sem procuração -> exige verificação.
    assert items["PROCURACAO"].status == ChecklistStatus.VERIFICAR
