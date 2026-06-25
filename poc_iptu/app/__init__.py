"""Camada de aplicação da UI: runner testável + app Streamlit."""
from .analysis_runner import (
    AnalysisMode,
    RunnerContext,
    build_runner,
    default_config_dir,
    run_analysis,
)

__all__ = [
    "AnalysisMode",
    "RunnerContext",
    "build_runner",
    "run_analysis",
    "default_config_dir",
]
