"""Caso de uso de análise de processo — orquestração da aplicação.

`AnalyzeProcessUseCase` é o topo do fluxo de entrada. Ele compõe as portas e o núcleo
determinístico, nesta ordem:

    ler PDF (+OCR)  ->  classificar  ->  extrair campos  ->  montar checklist (determinístico)
                    ->  avaliar (núcleo determinístico)  ->  consolidar ProcessAnalysisResult

Princípios respeitados:
  - depende apenas de PORTAS (DocumentReaderPort, DocumentClassificationPort, FieldExtractionPort);
    os adapters concretos são injetados, jamais instanciados aqui;
  - a parte estocástica (LLM/OCR) e a determinística (montagem do checklist + avaliação) ficam
    separadas e isoladas;
  - a minuta NÃO é gerada aqui (etapa do DecisionDraftService); draft_text permanece None.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..config.loader import ConfigLoader
from ..config.schemas import AppConfig
from ..domain.pipeline_models import (
    AnalysisMetadata,
    ExtractedDocument,
    ProcessAnalysisResult,
)
from ..domain.models import ProcessAnalysisInput
from ..drafting.decision_draft_service import DecisionDraftService
from ..ports.document_classification import DocumentClassificationPort
from ..ports.document_reader import DocumentReaderPort
from ..ports.field_extraction import FieldExtractionPort
from ..ports.ocr import OcrPort
from ..rules.checklist_assembler import ChecklistAssembler
from ..rules.process_evaluator import ProcessEvaluator, build_evaluator
from .. import __version__
from ..ports.decision_drafting import DecisionDraftingPort

# Política de PII registrada na auditoria. CPF circula mascarado na UI/minuta/logs.
_PII_POLICY = "CPF mascarado em UI/minuta/logs; CPF bruto restrito a uso interno controlado."


class AnalyzeProcessRequest:
    """Entrada do caso de uso: a fonte do PDF e um nome lógico opcional."""

    def __init__(
        self,
        source: bytes | str | Path,
        file_name: str | None = None,
        process_id: str | None = None,
    ) -> None:
        self.source = source
        self.file_name = file_name
        self.process_id = process_id


class AnalyzeProcessUseCase:
    """Orquestra a análise de um processo, do PDF à conclusão sugerida."""

    def __init__(
        self,
        document_reader: DocumentReaderPort,
        classifier: DocumentClassificationPort,
        field_extractor: FieldExtractionPort,
        checklist_assembler: ChecklistAssembler,
        process_evaluator: ProcessEvaluator,
        config_versions: "ConfigVersions",
        llm_provider: str,
        llm_model: str,
        ocr_engine: str,
        prompt_version: str = "n/a",
        decision_draft_service: DecisionDraftingPort | None = None,  # <- tipo da porta

    ) -> None:
        self._document_reader = document_reader
        self._classifier = classifier
        self._field_extractor = field_extractor
        self._checklist_assembler = checklist_assembler
        self._process_evaluator = process_evaluator
        self._config_versions = config_versions
        self._llm_provider = llm_provider
        self._llm_model = llm_model
        self._ocr_engine = ocr_engine
        self._prompt_version = prompt_version
        self._decision_draft_service = decision_draft_service

    def execute(self, request: AnalyzeProcessRequest) -> ProcessAnalysisResult:
        document = self._document_reader.read(request.source, request.file_name)

        classified = self._classifier.classify(document)
        fields = self._field_extractor.extract(document, classified)
        checklist = self._checklist_assembler.assemble(
            classified, fields.applicant, fields.income
        )

        analysis_input = ProcessAnalysisInput(
            request=fields.request,
            applicant=fields.applicant,
            property=fields.property,
            income=fields.income,
            checklist=checklist,
        )
        conclusion = self._process_evaluator.evaluate(analysis_input)

        result = ProcessAnalysisResult(
            process_id=request.process_id or str(uuid.uuid4()),
            file_name=document.file_name,
            request=fields.request,
            applicant=fields.applicant,
            property=fields.property,
            income=fields.income,
            documents=classified,
            checklist=checklist,
            conclusion=conclusion,
            metadata=self._build_metadata(),
            draft_text=None,
            ocr_page_count=document.ocr_page_count,
            total_page_count=len(document.pages),
        )
        return self._with_draft(result)

    def _with_draft(self, result: ProcessAnalysisResult) -> ProcessAnalysisResult:
        """Gera a minuta e a anexa ao resultado, quando o serviço de minuta está disponível."""
        if self._decision_draft_service is None:
            return result
        draft = self._decision_draft_service.generate(result)
        return result.model_copy(update={"draft_text": draft.text})

    def _build_metadata(self) -> AnalysisMetadata:
        return AnalysisMetadata(
            analysis_id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            app_version=__version__,
            legal_references_version=self._config_versions.legal_references,
            business_rules_version=self._config_versions.business_rules,
            checklist_version=self._config_versions.checklist,
            llm_provider=self._llm_provider,
            llm_model=self._llm_model,
            ocr_engine=self._ocr_engine,
            prompt_version=self._prompt_version,
            pii_policy=_PII_POLICY,
        )


class ConfigVersions:
    """Versões das configurações, para rastreabilidade nos metadados."""

    def __init__(self, legal_references: str, business_rules: str, checklist: str) -> None:
        self.legal_references = legal_references
        self.business_rules = business_rules
        self.checklist = checklist

    @classmethod
    def from_app_config(cls, config: AppConfig) -> "ConfigVersions":
        return cls(
            legal_references=config.legal_references.version,
            business_rules=config.business_rules.version,
            checklist=config.checklist.version,
        )


def build_analyze_process_use_case(
    config_dir: Path | str,
    document_reader: DocumentReaderPort,
    classifier: DocumentClassificationPort,
    field_extractor: FieldExtractionPort,
    ocr: OcrPort,
    llm_provider: str,
    llm_model: str,
    prompt_version: str = "n/a",
    decision_draft_service: DecisionDraftingPort | None = None,
) -> AnalyzeProcessUseCase:
    """Composition root do caso de uso: carrega config e injeta todas as dependências."""
    app_config: AppConfig = ConfigLoader(config_dir).load()
    checklist_assembler = ChecklistAssembler(app_config.checklist)
    process_evaluator: ProcessEvaluator = build_evaluator(config_dir)
    if decision_draft_service is None:
        decision_draft_service = DecisionDraftService(app_config.conclusion_mapping)
    return AnalyzeProcessUseCase(
        document_reader=document_reader,
        classifier=classifier,
        field_extractor=field_extractor,
        checklist_assembler=checklist_assembler,
        process_evaluator=process_evaluator,
        config_versions=ConfigVersions.from_app_config(app_config),
        llm_provider=llm_provider,
        llm_model=llm_model,
        ocr_engine=ocr.engine_name,
        prompt_version=prompt_version,
        decision_draft_service=decision_draft_service,
    )
