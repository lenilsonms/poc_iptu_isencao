"""Adapter de extração de campos sobre o LLM (Azure OpenAI).

Responsabilidade: montar o prompt de extração, chamar o LLM, fazer parse do JSON e mapear
para ExtractedFields (modelos de domínio, que validam os enums). Falhas de contrato viram
LlmResponseError.
"""

from __future__ import annotations

from pydantic import ValidationError

from ...domain.models import RequestIdentification, PropertyQualification
from ...domain.pipeline_models import (
    ApplicantQualification,
    ClassifiedDocument,
    ExtractedDocument,
    ExtractedFields,
)
from ...domain.models import IncomeAnalysis
from ...ports.field_extraction import FieldExtractionPort
from .chat_client import ChatCompletionClient
from .prompt_library import PromptLibrary
from .serialization import (
    LlmResponseError,
    parse_json_object,
    serialize_classified,
    serialize_pages,
)


class AzureFieldExtraction(FieldExtractionPort):
    """Extração de campos estruturados via LLM."""

    def __init__(self, chat_client: ChatCompletionClient, prompts: PromptLibrary) -> None:
        self._chat = chat_client
        self._prompts = prompts

    def extract(
        self,
        document: ExtractedDocument,
        classified_documents: list[ClassifiedDocument],
    ) -> ExtractedFields:
        template = self._prompts.extraction
        user_prompt = template.render_user(
            pages=serialize_pages(document, self._prompts.max_page_chars),
            classified_documents=serialize_classified(classified_documents),
        )
        content = self._chat.complete(
            template.system, user_prompt, temperature=self._prompts.temperature
        )
        return self._parse(content)

    def _parse(self, content: str) -> ExtractedFields:
        data = parse_json_object(content)
        try:
            return ExtractedFields(
                request=RequestIdentification.model_validate(self._section(data, "request")),
                applicant=ApplicantQualification.model_validate(
                    self._section(data, "applicant")
                ),
                property=PropertyQualification.model_validate(self._section(data, "property")),
                income=IncomeAnalysis.model_validate(self._section(data, "income")),
            )
        except ValidationError as exc:
            raise LlmResponseError(f"Extração fora do contrato esperado: {exc}") from exc

    @staticmethod
    def _section(data: dict, key: str) -> dict:
        section = data.get(key)
        if not isinstance(section, dict):
            raise LlmResponseError(f"Seção '{key}' ausente ou inválida na extração.")
        return section
