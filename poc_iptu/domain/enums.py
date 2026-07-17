"""Enumerações canônicas do domínio da POC de isenção de IPTU.

Estes são os vocabulários oficiais. Qualquer valor produzido pelo LLM ou lido de
configuração é coagido para um destes enums na fronteira (via Pydantic), garantindo
que o núcleo determinístico jamais opere sobre strings livres.
"""

from __future__ import annotations

from enum import Enum


class ConclusionStatus(str, Enum):
    """Vocabulário canônico de conclusão. O LLM nunca decide; o código sugere.

    Mapeamento para o vocabulário operacional da SRC (ADR-S2-01):
      PROCEDENTE     -> APTO_PARA_ANALISE_DE_DEFERIMENTO (a POC não declara procedência)
      IMPROCEDENTE   -> INDEFERIMENTO_SUGERIDO (motivo em ConclusionResult.denial_ground)
      NAO CONHECIMENTO / PREJUDICADO -> estados próprios, abaixo.
    """

    INDEFERIMENTO_SUGERIDO = "INDEFERIMENTO_SUGERIDO"
    APTO_PARA_ANALISE_DE_DEFERIMENTO = "APTO_PARA_ANALISE_DE_DEFERIMENTO"
    VERIFICAR_MANUALMENTE = "VERIFICAR_MANUALMENTE"
    FORA_DO_ESCOPO_POC = "FORA_DO_ESCOPO_POC"
    NAO_CONHECIMENTO_SUGERIDO = "NAO_CONHECIMENTO_SUGERIDO"          # NOVO: intempestividade
    JULGAMENTO_PREJUDICADO_SUGERIDO = "JULGAMENTO_PREJUDICADO_SUGERIDO"  # NOVO: perda de objeto


class AdmissibilityStatus(str, Enum):
    """Resultado de uma verificação de admissibilidade (Etapas 2 e 3 do fluxo SRC).

    NAO_AVALIADO é o default até o Sprint 3 ligar os detectores — a precedência
    ignora verificações não avaliadas (ADR-S2-03).
    """

    OK = "OK"
    FALHA = "FALHA"
    NAO_AVALIADO = "NAO_AVALIADO"


class DenialGround(str, Enum):
    """Motivo tipado do indeferimento sugerido (ADR-S2-02)."""

    INEPCIA_DA_INICIAL = "INEPCIA_DA_INICIAL"            # ilegitimidade (Etapa 3 SRC)
    FALTA_DE_DOCUMENTACAO = "FALTA_DE_DOCUMENTACAO"      # checklist (Etapa 4 SRC)
    RENDA_ACIMA_DO_LIMITE = "RENDA_ACIMA_DO_LIMITE"      # 5.2.2.d SRC


class ChecklistStatus(str, Enum):
    """Status de cada item do checklist documental."""

    OK = "OK"
    NAO_APRESENTADO = "NAO_APRESENTADO"
    VERIFICAR = "VERIFICAR"
    NAO_APLICAVEL = "NAO_APLICAVEL"


class BenefitType(str, Enum):
    """Tipo de benefício pleiteado. Apenas os três primeiros estão no escopo da POC."""

    APOSENTADO = "APOSENTADO"
    PENSIONISTA = "PENSIONISTA"
    LOAS = "LOAS"
    PRODUTOR_RURAL = "PRODUTOR_RURAL"
    OUTRO = "OUTRO"


class IncomeStatus(str, Enum):
    """Resultado da análise de renda agregada (todas as fontes)."""

    OK = "OK"
    VERIFICAR = "VERIFICAR"
    ACIMA_DO_LIMITE = "ACIMA_DO_LIMITE"
    NAO_APLICAVEL = "NAO_APLICAVEL"


class PropertyRelationshipType(str, Enum):
    """Vínculo do requerente com o imóvel (art. 7º da Lei nº 6.793/2010, redação da Lei nº 8.443/2025).

    O valor sentinela VERIFICAR é usado quando o vínculo não pôde ser determinado com segurança.
    """

    PROPRIETARIO = "PROPRIETARIO"
    COPROPRIETARIO = "COPROPRIETARIO"
    COMPROMISSARIO = "COMPROMISSARIO"
    TITULAR_DOMINIO_UTIL = "TITULAR_DOMINIO_UTIL"
    POSSUIDOR = "POSSUIDOR"
    CESSIONARIO = "CESSIONARIO"
    USUFRUTUARIO = "USUFRUTUARIO"
    VERIFICAR = "VERIFICAR"


class LegalRegimeId(str, Enum):
    """Identificadores dos decretos regulamentadores versionados por vigência."""
    DEC_22429_2003 = "DEC_22429_2003"
    DEC_34767_2018 = "DEC_34767_2018"
    DEC_42621_2025 = "DEC_42621_2025"
