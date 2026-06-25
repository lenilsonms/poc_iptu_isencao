"""Funções de apoio aos adapters de LLM."""

from __future__ import annotations

import json
from typing import Any

from ...domain.errors import PocIptuError
from ...domain.pipeline_models import ClassifiedDocument, ExtractedDocument


class LlmResponseError(PocIptuError):
    """Resposta do LLM ausente, não-JSON ou fora do contrato esperado."""


def serialize_pages(document: ExtractedDocument, max_page_chars: int) -> str:
    """Serializa as páginas para o prompt, truncando o texto por página."""
    blocks: list[str] = []
    for page in document.pages:
        text = page.text or ""
        if len(text) > max_page_chars:
            text = text[:max_page_chars] + " […]"
        blocks.append(f"=== Página {page.page_number} (origem: {page.source.value}) ===\n{text}")
    return "\n\n".join(blocks)


def serialize_classified(documents: list[ClassifiedDocument]) -> str:
    """Serializa os documentos classificados em JSON compacto para o prompt de extração."""
    payload = [
        {
            "document_type": doc.document_type,
            "page_start": doc.page_start,
            "page_end": doc.page_end,
            "evidence": doc.evidence,
        }
        for doc in documents
    ]
    return json.dumps(payload, ensure_ascii=False)


def parse_json_object(content: str) -> dict[str, Any]:
    """Faz parse de JSON, tolerando cercas de markdown eventualmente devolvidas pelo modelo."""
    cleaned = _strip_markdown_fences(content).strip()
    if not cleaned:
        raise LlmResponseError("Resposta vazia do LLM.")
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LlmResponseError(f"Resposta do LLM não é JSON válido: {exc}") from exc
    if not isinstance(data, dict):
        raise LlmResponseError("Resposta do LLM não é um objeto JSON.")
    return data


def _strip_markdown_fences(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        # remove a primeira linha (```json ou ```) e a última cerca
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text
