"""Carregamento e validação das configurações YAML.

O loader é o único ponto que conhece o formato bruto dos arquivos. Ele:
  1. lê os YAMLs de um diretório injetado (sem estado global, sem caminhos mágicos);
  2. extrai os sub-dicionários que o núcleo consome;
  3. valida-os contra os schemas tipados;
  4. verifica a coerência da dependência declarada (business_rules.depends_on -> legal_references).

Qualquer inconsistência vira ConfigValidationError com mensagem acionável.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..domain.errors import ConfigValidationError
from .schemas import (
    AppConfig,
    BusinessRulesConfig,
    ChecklistConfig,
    ConclusionMappingConfig,
    DecreeConfig,
    LegalReferencesConfig,
)


class ConfigLoader:
    """Carrega e valida as configurações da POC a partir de um diretório."""

    BUSINESS_RULES_FILE = "business_rules.yaml"
    LEGAL_REFERENCES_FILE = "legal_references.yaml"
    CHECKLIST_FILE = "checklist_iptu.yaml"
    CONCLUSION_MAPPING_FILE = "conclusion_mapping.yaml"

    def __init__(self, config_dir: Path | str) -> None:
        self._config_dir = Path(config_dir)

    def load(self) -> AppConfig:
        """Carrega tudo, valida e retorna o agregado coerente. Ponto de entrada único."""
        business_rules = self._load_business_rules()
        legal_references = self._load_legal_references()
        checklist = self._load_checklist()
        conclusion_mapping = self._load_conclusion_mapping()
        self._assert_version_compatibility(business_rules, legal_references)
        return AppConfig(
            business_rules=business_rules,
            legal_references=legal_references,
            checklist=checklist,
            conclusion_mapping=conclusion_mapping,
        )

    # ----------------------------------------------------------------- helpers

    def _read_yaml(self, filename: str) -> dict[str, Any]:
        path = self._config_dir / filename
        if not path.exists():
            raise ConfigValidationError(f"Arquivo de configuração não encontrado: {path}")
        try:
            with path.open(encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:  # pragma: no cover - defensivo
            raise ConfigValidationError(f"YAML inválido em {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigValidationError(
                f"Configuração inválida em {path}: esperado um mapeamento no topo."
            )
        return data

    @staticmethod
    def _require(data: dict[str, Any], key: str, source: str) -> Any:
        if key not in data:
            raise ConfigValidationError(f"Chave obrigatória ausente em {source}: '{key}'.")
        return data[key]

    def _load_business_rules(self) -> BusinessRulesConfig:
        raw = self._read_yaml(self.BUSINESS_RULES_FILE)
        src = self.BUSINESS_RULES_FILE
        metadata = self._require(raw, "metadata", src)
        depends_on = self._require(metadata, "depends_on", f"{src}.metadata")
        payload = {
            "version": self._require(metadata, "version", f"{src}.metadata"),
            "depends_on_legal_references_version": self._require(
                depends_on, "legal_references_version", f"{src}.metadata.depends_on"
            ),
            "scope": self._require(raw, "scope", src),
            "confidence": self._require(raw, "confidence_policy", src),
            "summary_denial": self._require(raw, "summary_denial", src),
            "income_limit": self._require(raw, "income_limit", src),
            "admissibility": self._require(raw, "admissibility", src),
        }
        try:
            return BusinessRulesConfig.model_validate(payload)
        except Exception as exc:  # pydantic ValidationError -> erro de domínio claro
            raise ConfigValidationError(f"business_rules.yaml inválido: {exc}") from exc

    def _load_legal_references(self) -> LegalReferencesConfig:
        raw = self._read_yaml(self.LEGAL_REFERENCES_FILE)
        src = self.LEGAL_REFERENCES_FILE
        metadata = self._require(raw, "metadata", src)
        regulatory = self._require(raw, "regulatory_decrees", src)
        items = self._require(regulatory, "items", f"{src}.regulatory_decrees")
        strategy = self._require(regulatory, "selection_strategy", f"{src}.regulatory_decrees")

        decrees: dict[str, DecreeConfig] = {}
        for item in items:
            decree = DecreeConfig.model_validate(item)
            decrees[decree.id.value] = decree

        payload = {
            "version": self._require(metadata, "version", f"{src}.metadata"),
            "decrees": decrees,
            "selection_priority": self._require(
                strategy, "priority", f"{src}.regulatory_decrees.selection_strategy"
            ),
            "fallback_status": self._require(
                strategy, "fallback_status", f"{src}.regulatory_decrees.selection_strategy"
            ),
            # NOVO: expande "2004-2017" -> {2004: ..., ..., 2017: ...}
            "year_to_regime": self._expand_year_ranges(
                strategy.get("conservative_year_to_regime", {}), src
            ),
        }
        try:
            return LegalReferencesConfig.model_validate(payload)
        except Exception as exc:
            raise ConfigValidationError(f"legal_references.yaml inválido: {exc}") from exc

    @staticmethod
    def _expand_year_ranges(
        raw_map: dict, source: str
    ) -> dict[int, str]:
        """Converte chaves '2004-2017' ou '2026' em um mapa ano->regime.

        Falha alto (ConfigValidationError) em intervalos malformados ou sobrepostos —
        um mapa ambíguo de regime é inadmissível num motor de fundamentação legal.
        """
        expanded: dict[int, str] = {}
        for key, regime_id in (raw_map or {}).items():
            key_text = str(key).strip()
            try:
                if "-" in key_text:
                    start_text, end_text = key_text.split("-", maxsplit=1)
                    start_year, end_year = int(start_text), int(end_text)
                else:
                    start_year = end_year = int(key_text)
            except ValueError as exc:
                raise ConfigValidationError(
                    f"Intervalo de exercício inválido em {source}."
                    f"conservative_year_to_regime: '{key_text}'."
                ) from exc
            if end_year < start_year:
                raise ConfigValidationError(
                    f"Intervalo invertido em conservative_year_to_regime: '{key_text}'."
                )
            for year in range(start_year, end_year + 1):
                if year in expanded:
                    raise ConfigValidationError(
                        f"Exercício {year} mapeado para mais de um regime em "
                        "conservative_year_to_regime."
                    )
                expanded[year] = regime_id
        return expanded

    def _load_checklist(self) -> ChecklistConfig:
        raw = self._read_yaml(self.CHECKLIST_FILE)
        src = self.CHECKLIST_FILE
        metadata = self._require(raw, "metadata", src)
        payload = {
            "version": self._require(metadata, "version", f"{src}.metadata"),
            "items": self._require(raw, "items", src),
        }
        try:
            return ChecklistConfig.model_validate(payload)
        except Exception as exc:
            raise ConfigValidationError(f"checklist_iptu.yaml inválido: {exc}") from exc

    def _load_conclusion_mapping(self) -> ConclusionMappingConfig:
        raw = self._read_yaml(self.CONCLUSION_MAPPING_FILE)
        src = self.CONCLUSION_MAPPING_FILE
        metadata = self._require(raw, "metadata", src)
        appeal = self._require(raw, "appeal_notice", src)
        payload = {
            "version": self._require(metadata, "version", f"{src}.metadata"),
            "states": self._require(raw, "states", src),
            "mandatory_sections": self._require(raw, "mandatory_sections", src),
            "appeal_notice_enabled": self._require(appeal, "enabled", f"{src}.appeal_notice"),
            "appeal_notice_text": self._require(appeal, "text", f"{src}.appeal_notice"),
        }
        try:
            return ConclusionMappingConfig.model_validate(payload)
        except Exception as exc:
            raise ConfigValidationError(f"conclusion_mapping.yaml inválido: {exc}") from exc

    @staticmethod
    def _assert_version_compatibility(
        business_rules: BusinessRulesConfig,
        legal_references: LegalReferencesConfig,
    ) -> None:
        declared = business_rules.depends_on_legal_references_version
        actual = legal_references.version
        if declared != actual:
            raise ConfigValidationError(
                "Incompatibilidade de versão entre configs: "
                f"business_rules depende de legal_references '{declared}', "
                f"mas o arquivo carregado é '{actual}'."
            )
