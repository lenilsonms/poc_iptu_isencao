"""Compositor do andar de admissibilidade: produz o AdmissibilityFacts completo.

Responsabilidade única: orquestrar TimelinessEvaluator e LegitimacyEvaluator e
materializar os fatos que a precedência A1–A3 do ConclusionResolver consome.
Perda de objeto (A2) permanece NAO detectada aqui — depende de dados de lançamentos
do SIRF (Sprint 4/backlog); o campo continua com default False.
"""

from __future__ import annotations

from ..config.schemas import AdmissibilityConfig
from ..domain.models import (
    AdmissibilityFacts,
    ApplicantQualification,
    PropertyQualification,
    RequestIdentification,
)
from .legitimacy_evaluator import LegitimacyEvaluator
from .timeliness_evaluator import TimelinessEvaluator


class AdmissibilityEvaluator:
    """Produz os fatos das Etapas 2 e 3 do fluxo SRC a partir dos dados extraídos."""

    def __init__(self, admissibility_config: AdmissibilityConfig) -> None:
        self._timeliness = TimelinessEvaluator(admissibility_config.timeliness)
        self._legitimacy = LegitimacyEvaluator(admissibility_config.legitimacy)

    def evaluate(
        self,
        request: RequestIdentification,
        applicant: ApplicantQualification,
        property_facts: PropertyQualification,
    ) -> AdmissibilityFacts:
        timeliness_status, timeliness_detail = self._timeliness.evaluate(request)
        legitimacy_status, legitimacy_detail = self._legitimacy.evaluate(
            applicant, property_facts
        )
        return AdmissibilityFacts(
            tempestividade=timeliness_status,
            tempestividade_detail=timeliness_detail,
            legitimidade=legitimacy_status,
            legitimidade_detail=legitimacy_detail,
        )