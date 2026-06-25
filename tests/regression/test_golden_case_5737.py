"""Teste GATING #1 — caso-ouro SEI 1101.2023/0005737-8.

Este é o teste bloqueante da POC. Ele falha se o fundamento legal, o checklist ou a conclusão
divergirem do gabarito. Enquanto este teste estiver verde, todo o restante do pipeline
(classificação, extração, minuta) tem um alvo objetivo a respeitar.

Critérios de aprovação (seção 13.3 do documento de requisitos):
  1. conclusion.status == INDEFERIMENTO_SUGERIDO
  2. COMPROVANTE_RESIDENCIA == NAO_APRESENTADO
  3. EXTRATO_RENDIMENTO_FONTE_PAGADORA == VERIFICAR
  4. COMPROVANTE_OUTRAS_RENDAS == VERIFICAR
  5. a minuta deve citar o Decreto nº 34.767/2018 (NÃO o 42.621/2025)
  6. nenhuma página pode ser citada sem evidência ancorada
  7. (seção de ciência/recurso e CPF mascarado pertencem à camada de minuta — fora deste núcleo)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from poc_iptu.domain import ConclusionStatus
from poc_iptu.rules import build_evaluator
from tests.fixtures.golden_case_5737 import build_golden_case_5737

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@pytest.fixture(scope="module")
def conclusion():
    """Avalia o caso-ouro pelo núcleo determinístico real, com os YAMLs do projeto."""
    evaluator = build_evaluator(CONFIG_DIR)
    return evaluator.evaluate(build_golden_case_5737())


def test_status_is_indeferimento_sugerido(conclusion):
    assert conclusion.status == ConclusionStatus.INDEFERIMENTO_SUGERIDO


def test_comprovante_residencia_consta_como_ausente(conclusion):
    assert "COMPROVANTE_RESIDENCIA" in conclusion.missing_required_documents


def test_extrato_rendimento_consta_para_verificar(conclusion):
    # Usa o CÓDIGO CANÔNICO do checklist congelado (ajuste P0).
    assert "EXTRATO_RENDIMENTO_FONTE_PAGADORA" in conclusion.items_to_verify


def test_outras_rendas_consta_para_verificar(conclusion):
    assert "COMPROVANTE_OUTRAS_RENDAS" in conclusion.items_to_verify


def test_fundamento_cita_decreto_correto_34767(conclusion):
    basis = conclusion.legal_basis
    assert any("34.767" in entry for entry in basis), basis
    assert any("art. 3º" in entry for entry in basis), basis
    assert any("art. 7º" in entry for entry in basis), basis


def test_fundamento_nao_cita_decreto_42621(conclusion):
    # O caso-ouro é regido pelo regime antigo; citar o 42.621 seria erro jurídico.
    assert all("42.621" not in entry for entry in conclusion.legal_basis), conclusion.legal_basis


def test_indeferimento_gera_minuta_de_merito(conclusion):
    assert conclusion.generate_merit_draft is True


def test_multiplas_inscricoes_geram_aviso_sem_alterar_estado(conclusion):
    # Múltiplas inscrições são sinal de atenção, não determinante: o estado segue INDEFERIMENTO.
    assert any("inscrições" in w.lower() for w in conclusion.warnings), conclusion.warnings
    assert conclusion.status == ConclusionStatus.INDEFERIMENTO_SUGERIDO


def test_nenhuma_pagina_citada_sem_evidencia_apos_normalizacao():
    """Invariante anti-alucinação: todo item com página citada possui evidência ancorada."""
    from poc_iptu.config import ConfigLoader
    from poc_iptu.rules import ConfidencePolicy

    config = ConfigLoader(CONFIG_DIR).load()
    policy = ConfidencePolicy(config.business_rules.confidence)
    normalized = [policy.normalize(item) for item in build_golden_case_5737().checklist]

    for item in normalized:
        if item.page is not None:
            assert item.evidence, f"Item {item.code} cita página {item.page} sem evidência."
