"""Exceções específicas do domínio.

Erros explícitos e tipados evitam que falhas de configuração ou de dados se propaguem
silenciosamente até a minuta — comportamento inadmissível num sistema que fundamenta
decisões administrativas.
"""

from __future__ import annotations


class PocIptuError(Exception):
    """Raiz da hierarquia de erros da POC. Permite capturar qualquer erro do domínio."""


class ConfigValidationError(PocIptuError):
    """Configuração ausente, malformada ou incoerente entre versões (depends_on)."""


class RegimeSelectionError(PocIptuError):
    """Falha irrecuperável ao selecionar o regime legal (distinta de 'não identificado').

    'Não identificado com segurança' é um resultado de negócio legítimo (VERIFICAR_MANUALMENTE),
    não um erro. Esta exceção é reservada a inconsistências estruturais — por exemplo, um id de
    decreto referenciado nas regras mas inexistente em legal_references.
    """
