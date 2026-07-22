"""Avaliador determinístico de tempestividade (Etapa 2 do fluxo SRC).

Regra, com a sub-regra da data de concessão do benefício:
  autuação <= prazo do exercício                    -> OK
  autuação  > prazo:
      concessão do benefício  > prazo               -> OK (o benefício nem existia no prazo)
      concessão do benefício <= prazo               -> FALHA (não conhecimento)
      concessão desconhecida                        -> VERIFICAR (ADR-S3-03)
  prazo não configurado para o exercício            -> NAO_AVALIADO + aviso (ADR-S3-01)
  data de autuação não extraída                     -> NAO_AVALIADO + aviso (ADR-S3-02)

Responsabilidade única: produzir (status, detalhe). Não conhece conclusão nem minuta.
"""

from __future__ import annotations

from ..config.schemas import TimelinessConfig
from ..domain.enums import AdmissibilityStatus
from ..domain.models import RequestIdentification


class TimelinessEvaluator:
    """Aplica a Tabela 1 da SRC à data de autuação do processo."""

    def __init__(self, timeliness_config: TimelinessConfig) -> None:
        self._config = timeliness_config

    def evaluate(
        self, request: RequestIdentification
    ) -> tuple[AdmissibilityStatus, str | None]:
        deadline = self._config.deadline_for_year(request.requested_year)

        if deadline is None:
            return AdmissibilityStatus.NAO_AVALIADO, (
                f"Tempestividade não avaliada: exercício {request.requested_year} sem "
                "prazo configurado na tabela de tempestividade (ADR-S3-01)."
            )

        if request.protocol_date is None:
            return AdmissibilityStatus.NAO_AVALIADO, (
                "Tempestividade não avaliada: data de autuação não localizada no "
                "processo (ADR-S3-02)."
            )

        if request.protocol_date <= deadline:
            return AdmissibilityStatus.OK, (
                f"Autuação em {request.protocol_date.isoformat()} dentro do prazo "
                f"({deadline.isoformat()}) do exercício {request.requested_year}."
            )

        # Autuação após o prazo: sub-regra da data de concessão do benefício.
        concession = request.benefit_concession_date
        if concession is None:
            return AdmissibilityStatus.VERIFICAR, (
                f"Autuação em {request.protocol_date.isoformat()} após o prazo "
                f"({deadline.isoformat()}); data de concessão do benefício não "
                "localizada — verificar tempestividade manualmente (ADR-S3-03)."
            )
        if concession > deadline:
            return AdmissibilityStatus.OK, (
                f"Autuação após o prazo ({deadline.isoformat()}), porém benefício "
                f"concedido em {concession.isoformat()}, posterior ao prazo — "
                "tempestividade preservada (sub-regra da Etapa 2 do fluxo SRC)."
            )
        return AdmissibilityStatus.FALHA, (
            f"Autuação em {request.protocol_date.isoformat()} após o prazo "
            f"({deadline.isoformat()}) do exercício {request.requested_year}, com "
            f"benefício concedido em {concession.isoformat()}, anterior ao prazo — "
            "sugere-se o não conhecimento por intempestividade."
        )