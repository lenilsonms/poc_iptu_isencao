"""Teste do runner da aplicação (modo demonstração offline)."""

from __future__ import annotations

from pathlib import Path

from poc_iptu.app.analysis_runner import AnalysisMode, build_runner, run_analysis
from poc_iptu.domain import ConclusionStatus
from tests.fakes.pdf_factory import build_pdf_with_text_pages

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def test_sem_azure_usa_modo_demonstracao():
    context = build_runner(config_dir=CONFIG_DIR, env={})  # ambiente sem Azure
    assert context.mode == AnalysisMode.OFFLINE_DEMO
    assert context.prompt_version == "offline-demo"


def test_com_azure_no_ambiente_seleciona_modo_azure():
    env = {
        "AZURE_OPENAI_ENDPOINT": "https://exemplo.openai.azure.com",
        "AZURE_OPENAI_API_KEY": "chave-fake",
        "AZURE_OPENAI_DEPLOYMENT": "gpt-4o",
    }
    context = build_runner(config_dir=CONFIG_DIR, env=env)
    assert context.mode == AnalysisMode.AZURE
    assert context.prompt_version == "1.0.0-poc"
    assert context.llm_provider == "azure-openai"


def test_runner_demo_executa_ponta_a_ponta():
    context = build_runner(config_dir=CONFIG_DIR, env={})
    pdf = build_pdf_with_text_pages(["Pedido inicial", "RG", "Matrícula"])
    result = run_analysis(context, pdf, "demo.pdf", process_id="DEMO-1")

    assert result.conclusion.status == ConclusionStatus.INDEFERIMENTO_SUGERIDO
    assert "DECISÃO ADMINISTRATIVA" in (result.draft_text or "")
    assert result.metadata.prompt_version == "offline-demo"
