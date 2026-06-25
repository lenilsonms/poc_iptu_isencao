"""Leitura dos tipos de documento da taxonomia (document_taxonomy.yaml).

Mantido fora do ConfigLoader do núcleo: a taxonomia é insumo dos prompts de LLM, não do motor
determinístico. Achata as categorias num conjunto ordenado de tipos válidos.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ...domain.errors import ConfigValidationError

# Chaves de document_types que representam relacionamentos, não tipos documentais.
_NON_DOCUMENT_KEYS = {"accepted_property_relationships"}


def load_allowed_document_types(config_dir: Path | str) -> list[str]:
    """Retorna a lista ordenada e sem duplicatas dos tipos de documento da taxonomia."""
    path = Path(config_dir) / "document_taxonomy.yaml"
    if not path.exists():
        raise ConfigValidationError(f"document_taxonomy.yaml não encontrado: {path}")
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    document_types = raw.get("document_types") if isinstance(raw, dict) else None
    if not isinstance(document_types, dict):
        raise ConfigValidationError("document_taxonomy.yaml inválido: 'document_types' ausente.")

    collected: list[str] = []
    seen: set[str] = set()
    for category, values in document_types.items():
        if category in _NON_DOCUMENT_KEYS or not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, str) and value not in seen:
                seen.add(value)
                collected.append(value)
    return collected
