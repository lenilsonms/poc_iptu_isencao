"""Biblioteca de prompts versionada (carrega config/prompts.yaml).

A renderização usa substituição de TOKENS (e não str.format), porque os templates contêm
chaves de JSON que quebrariam o format. A versão é exposta para auditoria.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ...domain.errors import ConfigValidationError

_TOKEN_PAGES = "{{PAGES}}"
_TOKEN_ALLOWED_TYPES = "{{ALLOWED_DOCUMENT_TYPES}}"
_TOKEN_CLASSIFIED = "{{CLASSIFIED_DOCUMENTS}}"


class PromptTemplate:
    """Um par (system, user_template) com renderização por tokens."""

    def __init__(self, system: str, user_template: str) -> None:
        self.system = system
        self._user_template = user_template

    def render_user(
        self,
        pages: str,
        allowed_document_types: str | None = None,
        classified_documents: str | None = None,
    ) -> str:
        rendered = self._user_template.replace(_TOKEN_PAGES, pages)
        if allowed_document_types is not None:
            rendered = rendered.replace(_TOKEN_ALLOWED_TYPES, allowed_document_types)
        if classified_documents is not None:
            rendered = rendered.replace(_TOKEN_CLASSIFIED, classified_documents)
        return rendered
    
    def render(self, tokens: dict[str, str]) -> str:
        """Renderização genérica por tokens {{NOME}} — usada pelos prompts novos."""
        rendered = self._user_template
        for name, value in tokens.items():
            rendered = rendered.replace(f"{{{{{name}}}}}", value)
        return rendered

class PromptLibrary:
    """Conjunto de prompts carregado de prompts.yaml."""

    def __init__(
        self,
        version: str,
        classification: PromptTemplate,
        extraction: PromptTemplate,
        temperature: float,
        response_format: str,
        max_page_chars: int,
        drafting: PromptTemplate | None = None
    ) -> None:
        self.version = version
        self.classification = classification
        self.extraction = extraction
        self.temperature = temperature
        self.response_format = response_format
        self.max_page_chars = max_page_chars
        self.drafting = drafting

    @classmethod
    def from_yaml(cls, path: Path | str) -> "PromptLibrary":
        raw = cls._read_yaml(Path(path))
        metadata = cls._require(raw, "metadata", "prompts.yaml")
        defaults = raw.get("defaults", {})
        classification = cls._build_template(raw, "classification")
        extraction = cls._build_template(raw, "extraction")
        drafting = cls._build_template(raw, "drafting") if "drafting" in raw else None
        return cls(
            version=cls._require(metadata, "version", "prompts.yaml.metadata"),
            classification=classification,
            extraction=extraction,
            temperature=float(defaults.get("temperature", 0.0)),
            response_format=str(defaults.get("response_format", "json_object")),
            max_page_chars=int(defaults.get("max_page_chars", 4000)),
            drafting=drafting,
        )

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise ConfigValidationError(f"Arquivo de prompts não encontrado: {path}")
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        if not isinstance(data, dict):
            raise ConfigValidationError(f"prompts.yaml inválido: esperado mapeamento ({path}).")
        return data

    @staticmethod
    def _require(data: dict[str, Any], key: str, source: str) -> Any:
        if key not in data:
            raise ConfigValidationError(f"Chave obrigatória ausente em {source}: '{key}'.")
        return data[key]

    @classmethod
    def _build_template(cls, raw: dict[str, Any], section: str) -> PromptTemplate:
        block = cls._require(raw, section, "prompts.yaml")
        return PromptTemplate(
            system=cls._require(block, "system", f"prompts.yaml.{section}"),
            user_template=cls._require(block, "user_template", f"prompts.yaml.{section}"),
        )
