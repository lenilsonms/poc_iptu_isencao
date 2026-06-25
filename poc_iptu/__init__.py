"""POC — Agente de IA para Triagem e Minuta de Isenção de IPTU de Guarulhos.

Núcleo determinístico (config-driven). A IA lê/classifica/extrai/redige; este núcleo,
puro e determinístico, SUGERE a conclusão. A decisão final é sempre humana.
"""
__version__ = "0.1.0"

from .rules import ProcessEvaluator, build_evaluator

__all__ = ["ProcessEvaluator", "build_evaluator", "__version__"]
