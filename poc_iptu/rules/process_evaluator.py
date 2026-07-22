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
from ..rules.admissibility_evaluator import AdmissibilityEvaluator
from ..domain.models import ConclusionResult, ProcessAnalysisInput
from .conclusion_resolver import ConclusionResolver
from .confidence_policy import ConfidencePolicy
from .legal_regime_selector import LegalRegimeSelector
from .income_limit_calculator import IncomeLimitCalculator


class ProcessEvaluator:
    """Compõe as regras do núcleo numa única operação determinística."""

    def __init__(
        self,
        confidence_policy: ConfidencePolicy,
        income_limit_calculator: IncomeLimitCalculator,
        admissibility_evaluator: AdmissibilityEvaluator,
        regime_selector: LegalRegimeSelector,
        conclusion_resolver: ConclusionResolver,
    ) -> None:
        self._confidence_policy = confidence_policy
        self._income_limit_calculator = income_limit_calculator
        self._admissibility_evaluator = admissibility_evaluator
        self._regime_selector = regime_selector
        self._conclusion_resolver = conclusion_resolver

    def evaluate(self, analysis_input: ProcessAnalysisInput) -> ConclusionResult:
        normalized_checklist = [
            self._confidence_policy.normalize(item) for item in analysis_input.checklist
        ]
        normalized_income, income_warnings = self._income_limit_calculator.normalize(
            analysis_input.income, analysis_input.request.requested_year
        )
        normalized_input = analysis_input.model_copy(
            update={"checklist": normalized_checklist, "income": normalized_income}
        )
        admissibility_facts = self._admissibility_evaluator.evaluate(
            analysis_input.request, analysis_input.applicant, analysis_input.property
        )
        normalized_input = analysis_input.model_copy(update={
            "checklist": normalized_checklist,
            "income": normalized_income,
            "admissibility": admissibility_facts,
        })
        regime = self._regime_selector.select(normalized_input.request)
        conclusion = self._conclusion_resolver.resolve(normalized_input, regime)
        if income_warnings:
            conclusion = conclusion.model_copy(
                update={"warnings": [*conclusion.warnings, *income_warnings]}
            )
        return conclusion


def build_evaluator(config_dir: Path | str) -> ProcessEvaluator:
    app_config: AppConfig = ConfigLoader(config_dir).load()
    return ProcessEvaluator(
        confidence_policy=ConfidencePolicy(app_config.business_rules.confidence),
        income_limit_calculator=IncomeLimitCalculator(app_config.business_rules.income_limit),
        admissibility_evaluator=AdmissibilityEvaluator(app_config.business_rules.admissibility),
        regime_selector=LegalRegimeSelector(app_config.legal_references, app_config.business_rules),
        conclusion_resolver=ConclusionResolver(app_config.business_rules),
    )

