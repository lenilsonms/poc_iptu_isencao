"""Adapters de LLM (Azure OpenAI) e demonstração offline."""
from .azure_classification import AzureDocumentClassification
from .azure_extraction import AzureFieldExtraction
from .chat_client import (
    AzureOpenAIChatClient,
    AzureOpenAISettings,
    ChatCompletionClient,
    LlmTransportError,
)
from .offline_demo import (
    OfflineDemoClassification,
    OfflineDemoExtraction,
    golden_case_classified_documents,
    golden_case_extracted_fields,
)
from .prompt_library import PromptLibrary, PromptTemplate
from .serialization import LlmResponseError
from .taxonomy import load_allowed_document_types

__all__ = [
    "AzureDocumentClassification",
    "AzureFieldExtraction",
    "ChatCompletionClient",
    "AzureOpenAIChatClient",
    "AzureOpenAISettings",
    "LlmTransportError",
    "LlmResponseError",
    "OfflineDemoClassification",
    "OfflineDemoExtraction",
    "golden_case_classified_documents",
    "golden_case_extracted_fields",
    "PromptLibrary",
    "PromptTemplate",
    "load_allowed_document_types",
]
