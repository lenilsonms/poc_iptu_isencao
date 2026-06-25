"""Testes do PromptLibrary e do leitor de tipos da taxonomia."""

from __future__ import annotations

from pathlib import Path

from poc_iptu.adapters.llm import PromptLibrary, load_allowed_document_types

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def test_carrega_prompts_versionados():
    prompts = PromptLibrary.from_yaml(CONFIG_DIR / "prompts.yaml")
    assert prompts.version == "1.0.0-poc"
    assert prompts.temperature == 0.0
    assert "JSON" in prompts.classification.system
    assert "CPF" in prompts.extraction.system


def test_render_substitui_tokens_sem_quebrar_chaves_json():
    prompts = PromptLibrary.from_yaml(CONFIG_DIR / "prompts.yaml")
    rendered = prompts.classification.render_user(
        pages="=== Página 1 ===\nconteúdo", allowed_document_types="- RG\n- CPF"
    )
    assert "conteúdo" in rendered
    assert "- RG" in rendered
    assert "{{PAGES}}" not in rendered
    assert "{{ALLOWED_DOCUMENT_TYPES}}" not in rendered


def test_carrega_tipos_da_taxonomia():
    tipos = load_allowed_document_types(CONFIG_DIR)
    assert "RG" in tipos
    assert "MATRICULA_IMOVEL" in tipos
    assert "JUCESP_FICHA_CADASTRAL" in tipos
    # Relacionamentos de imóvel NÃO são tipos de documento.
    assert "PROPRIETARIO" not in tipos
    # Sem duplicatas.
    assert len(tipos) == len(set(tipos))
