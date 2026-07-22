"""Avaliador determinístico de legitimidade (Etapa 3 do fluxo SRC).

FALHA (inépcia) exige evidência POSITIVA de ilegitimidade (ADR-S3-04):
  requerente declaradamente NÃO é o titular do benefício e NÃO há representante legal.
Dúvida sobre a titularidade, ou vínculo com o imóvel não comprovado -> VERIFICAR.
"""

from __future__ import annotations

from ..config.schemas import LegitimacyConfig
from ..domain.enums import AdmissibilityStatus, PropertyRelationshipType
from ..domain.models import ApplicantQualification, PropertyQualification


class LegitimacyEvaluator:
    """Verifica titularidade do benefício e vínculo qualificado com o imóvel."""

    def __init__(self, legitimacy_config: LegitimacyConfig) -> None:
        self._qualifying_types = set(legitimacy_config.qualifying_relationship_types)

    def evaluate(
        self, applicant: ApplicantQualification, property_facts: PropertyQualification
    ) -> tuple[AdmissibilityStatus, str | None]:
        # 1) Evidência positiva de ilegitimidade: terceiro sem representação.
        if applicant.requester_is_benefit_holder is False and not applicant.has_representative:
            return AdmissibilityStatus.FALHA, (
                "Requerente não é o titular do benefício e não há representante legal "
                "constituído nos autos — sugere-se indeferimento por inépcia da inicial."
            )

        # 2) Titularidade indeterminável: humano decide (ADR-S3-04).
        if applicant.requester_is_benefit_holder is None:
            return AdmissibilityStatus.VERIFICAR, (
                "Não foi possível determinar se o requerente é o titular do benefício — "
                "verificar legitimidade manualmente."
            )

        # 3) Vínculo com o imóvel não comprovado ou fora da tabela de tipos.
        relationship = property_facts.relationship_type
        if (
            relationship == PropertyRelationshipType.VERIFICAR
            or relationship.value not in self._qualifying_types
        ):
            return AdmissibilityStatus.VERIFICAR, (
                "Vínculo do requerente com o imóvel não comprovado ou não qualificado "
                f"({relationship.value}) — verificar legitimidade manualmente."
            )

        return AdmissibilityStatus.OK, "Titularidade do benefício e vínculo com o imóvel comprovados."