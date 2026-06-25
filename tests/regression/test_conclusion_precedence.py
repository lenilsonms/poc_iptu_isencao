"""Testes da tabela de precedência da conclusão (todos os ramos).

Cobrem R1 (fora do escopo), R2 (renda acima do limite), o rebaixamento P0 sob o
Decreto 42.621/2025, R4 (verificação manual) e R5 (apto). Estes testes blindam a ordem
das regras e a regra de autoridade de indeferimento de plano.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from poc_iptu.config import ConfigLoader
from poc_iptu.domain import (
    BenefitType,
    ChecklistItemResult,
    ChecklistStatus,
    ConclusionStatus,
    IncomeAnalysis,
    IncomeStatus,
    ProcessAnalysisInput,
    PropertyQualification,
    PropertyRelationshipType,
    RequestIdentification,
)
from poc_iptu.rules import build_evaluator

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@pytest.fixture(scope="module")
def evaluator():
    return build_evaluator(CONFIG_DIR)


def _income(status: IncomeStatus, other_sources: str | None = None) -> IncomeAnalysis:
    return IncomeAnalysis(
        benefit_condition=BenefitType.APOSENTADO,
        benefit_document_found=True,
        income_document_found=status == IncomeStatus.OK,
        other_sources_flag=other_sources,
        income_status=status,
    )


def _request(
    benefit: BenefitType = BenefitType.APOSENTADO,
    decree_mention: str | None = "Decreto nº 34.767/2018",
    year: int = 2024,
) -> RequestIdentification:
    return RequestIdentification(
        benefit_type=benefit, requested_year=year, explicit_decree_mention=decree_mention
    )


def _item(code: str, status: ChecklistStatus, required: bool = True) -> ChecklistItemResult:
    return ChecklistItemResult(
        code=code,
        label=code,
        required=required,
        status=status,
        page=1,
        evidence="evidência ancorada",
        confidence=0.95,
    )


def _input(request, checklist, income, multiple=False) -> ProcessAnalysisInput:
    return ProcessAnalysisInput(
        request=request,
        property=PropertyQualification(
            relationship_type=PropertyRelationshipType.PROPRIETARIO,
            multiple_inscriptions_detected=multiple,
        ),
        income=income,
        checklist=checklist,
    )


# --------------------------------------------------------------------------- R1

def test_r1_produtor_rural_fora_do_escopo(evaluator):
    analysis = _input(
        _request(benefit=BenefitType.PRODUTOR_RURAL),
        [_item("DOCUMENTO_IDENTIFICACAO", ChecklistStatus.OK)],
        _income(IncomeStatus.OK),
    )
    result = evaluator.evaluate(analysis)
    assert result.status == ConclusionStatus.FORA_DO_ESCOPO_POC
    assert result.generate_merit_draft is False


# --------------------------------------------------------------------------- R2

def test_r2_renda_acima_do_limite_indefere(evaluator):
    analysis = _input(
        _request(),
        [_item("DOCUMENTO_IDENTIFICACAO", ChecklistStatus.OK)],
        _income(IncomeStatus.ACIMA_DO_LIMITE, other_sources="JUCESP_MEI"),
    )
    result = evaluator.evaluate(analysis)
    assert result.status == ConclusionStatus.INDEFERIMENTO_SUGERIDO
    # Renda acima do limite cita o dispositivo de outras fontes (art. 3º no regime de 2018).
    assert any("art. 3º" in b for b in result.legal_basis), result.legal_basis


# --------------------------------------------------------- R3 + guarda P0 (42.621)

def test_r3_documento_ausente_indefere_sob_regime_2018(evaluator):
    analysis = _input(
        _request(decree_mention="Decreto nº 34.767/2018"),
        [_item("COMPROVANTE_RESIDENCIA", ChecklistStatus.NAO_APRESENTADO)],
        _income(IncomeStatus.OK),
    )
    result = evaluator.evaluate(analysis)
    assert result.status == ConclusionStatus.INDEFERIMENTO_SUGERIDO
    assert any("art. 7º" in b for b in result.legal_basis), result.legal_basis


def test_p0_documento_ausente_sob_42621_rebaixa_para_verificar(evaluator):
    """Regra P0: sob o Decreto 42.621/2025 (summary_denial não confirmado) NÃO se indefere de plano."""
    analysis = _input(
        _request(decree_mention="Decreto nº 42.621/2025", year=2025),
        [_item("COMPROVANTE_RESIDENCIA", ChecklistStatus.NAO_APRESENTADO)],
        _income(IncomeStatus.OK),
    )
    result = evaluator.evaluate(analysis)
    assert result.status == ConclusionStatus.VERIFICAR_MANUALMENTE
    assert "COMPROVANTE_RESIDENCIA" in result.items_to_verify
    assert any("indeferimento de plano não autorizado" in w.lower() for w in result.warnings)


# --------------------------------------------------------------------------- R4

def test_r4_item_verificar_vai_para_verificacao_manual(evaluator):
    analysis = _input(
        _request(),
        [
            _item("DOCUMENTO_IDENTIFICACAO", ChecklistStatus.OK),
            _item("EXTRATO_RENDIMENTO_FONTE_PAGADORA", ChecklistStatus.VERIFICAR),
        ],
        _income(IncomeStatus.OK),
    )
    result = evaluator.evaluate(analysis)
    assert result.status == ConclusionStatus.VERIFICAR_MANUALMENTE
    assert "EXTRATO_RENDIMENTO_FONTE_PAGADORA" in result.items_to_verify


# --------------------------------------------------------------------------- R5

def test_r5_tudo_ok_fica_apto(evaluator):
    """Caminho positivo (APTO) — antes sem caso-ouro; agora coberto."""
    analysis = _input(
        _request(),
        [
            _item("DOCUMENTO_IDENTIFICACAO", ChecklistStatus.OK),
            _item("DOCUMENTO_IMOVEL", ChecklistStatus.OK),
            _item("CARTA_CONCESSAO_BENEFICIO", ChecklistStatus.OK),
            _item("EXTRATO_RENDIMENTO_FONTE_PAGADORA", ChecklistStatus.OK),
            _item("COMPROVANTE_RESIDENCIA", ChecklistStatus.OK),
            _item("IRPF_OU_DECLARACAO_ISENTO", ChecklistStatus.OK),
        ],
        _income(IncomeStatus.OK),
    )
    result = evaluator.evaluate(analysis)
    assert result.status == ConclusionStatus.APTO_PARA_ANALISE_DE_DEFERIMENTO
    assert result.generate_merit_draft is True


def test_precedencia_documento_ausente_vence_verificar(evaluator):
    """R3 (ausente) tem precedência sobre R4 (verificar): é a lógica do caso-ouro."""
    analysis = _input(
        _request(decree_mention="Decreto nº 34.767/2018"),
        [
            _item("COMPROVANTE_RESIDENCIA", ChecklistStatus.NAO_APRESENTADO),
            _item("EXTRATO_RENDIMENTO_FONTE_PAGADORA", ChecklistStatus.VERIFICAR),
        ],
        _income(IncomeStatus.VERIFICAR, other_sources="JUCESP_MEI"),
    )
    result = evaluator.evaluate(analysis)
    assert result.status == ConclusionStatus.INDEFERIMENTO_SUGERIDO
