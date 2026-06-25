"""Orquestração do núcleo determinístico.

O `ProcessEvaluator` é a fachada pública do núcleo: recebe os fatos já extraídos
(ProcessAnalysisInput) e devolve a conclusão sugerida, compondo, nesta ordem:

    normalização de confiança  ->  seleção de regime  ->  resolução da conclusão

Não realiza nenhum I/O. O futuro AnalyzeProcessUseCase produzirá o ProcessAnalysisInput
via PDF/OCR/LLM e então delegará a este avaliador — mantendo a parte estocástica e a
determinística completamente separadas e testáveis em isolamento.
"""

from __future__ import annotations

from pathlib import Path

from ..config.loader import ConfigLoader
from ..config.schemas import AppConfig
from ..domain.models import ConclusionResult, ProcessAnalysisInput
from .conclusion_resolver import ConclusionResolver
from .confidence_policy import ConfidencePolicy
from .legal_regime_selector import LegalRegimeSelector


class ProcessEvaluator:
    """Compõe as regras do núcleo numa única operação determinística."""

    def __init__(
        self,
        confidence_policy: ConfidencePolicy,
        regime_selector: LegalRegimeSelector,
        conclusion_resolver: ConclusionResolver,
    ) -> None:
        self._confidence_policy = confidence_policy
        self._regime_selector = regime_selector
        self._conclusion_resolver = conclusion_resolver

    def evaluate(self, analysis_input: ProcessAnalysisInput) -> ConclusionResult:
        normalized_checklist = [
            self._confidence_policy.normalize(item) for item in analysis_input.checklist
        ]
        normalized_input = analysis_input.model_copy(
            update={"checklist": normalized_checklist}
        )
        regime = self._regime_selector.select(normalized_input.request)
        return self._conclusion_resolver.resolve(normalized_input, regime)


def build_evaluator(config_dir: Path | str) -> ProcessEvaluator:
    """Composition root do núcleo: carrega/valida config e injeta as dependências."""
    app_config: AppConfig = ConfigLoader(config_dir).load()
    confidence_policy = ConfidencePolicy(app_config.business_rules.confidence)
    regime_selector = LegalRegimeSelector(
        app_config.legal_references, app_config.business_rules
    )
    conclusion_resolver = ConclusionResolver(app_config.business_rules)
    return ProcessEvaluator(confidence_policy, regime_selector, conclusion_resolver)
