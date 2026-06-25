"""Transporte de chat completion.

`ChatCompletionClient` é a abstração injetável que isola os adapters de LLM do SDK e da rede.
`AzureOpenAIChatClient` é a implementação de produção (import preguiçoso do pacote `openai`):
a classe pode ser importada sem `openai` instalado; o erro só ocorre se for de fato usada sem
o pacote. Em testes, injeta-se um cliente falso que devolve JSON canônico.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ...domain.errors import PocIptuError


class LlmTransportError(PocIptuError):
    """Falha de transporte/credencial ao chamar o provedor de LLM."""


class ChatCompletionClient(ABC):
    """Executa uma chamada de chat completion e devolve o conteúdo textual da resposta."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identificador do modelo/deployment, registrado nos metadados de auditoria."""
        raise NotImplementedError

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str, *, temperature: float) -> str:
        """Retorna o conteúdo (string) da resposta do modelo (esperado: JSON)."""
        raise NotImplementedError


@dataclass(frozen=True)
class AzureOpenAISettings:
    """Configuração de conexão com o Azure OpenAI (preenchida por variáveis de ambiente)."""

    endpoint: str
    api_key: str
    deployment: str
    api_version: str = "2024-08-01-preview"
    response_format_json: bool = True

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "AzureOpenAISettings | None":
        """Constrói a partir do ambiente; retorna None se a configuração estiver incompleta."""
        endpoint = env.get("AZURE_OPENAI_ENDPOINT")
        api_key = env.get("AZURE_OPENAI_API_KEY")
        deployment = env.get("AZURE_OPENAI_DEPLOYMENT")
        if not (endpoint and api_key and deployment):
            return None
        return cls(
            endpoint=endpoint,
            api_key=api_key,
            deployment=deployment,
            api_version=env.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
        )


class AzureOpenAIChatClient(ChatCompletionClient):
    """Cliente de chat completion sobre o Azure OpenAI."""

    def __init__(self, settings: AzureOpenAISettings) -> None:
        self._settings = settings
        self._client = None  # inicialização preguiçosa

    @property
    def model_name(self) -> str:
        return f"azure-openai:{self._settings.deployment}"

    def complete(self, system_prompt: str, user_prompt: str, *, temperature: float) -> str:
        client = self._get_client()
        kwargs = {
            "model": self._settings.deployment,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if self._settings.response_format_json:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as exc:  # erro de rede/credencial/limite
            raise LlmTransportError(f"Falha ao chamar Azure OpenAI: {exc}") from exc
        content = response.choices[0].message.content
        return content or ""

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AzureOpenAI  # import preguiçoso
            except ImportError as exc:
                raise LlmTransportError(
                    "Pacote 'openai' não instalado. Instale com 'pip install openai' para usar "
                    "o Azure OpenAI."
                ) from exc
            self._client = AzureOpenAI(
                azure_endpoint=self._settings.endpoint,
                api_key=self._settings.api_key,
                api_version=self._settings.api_version,
            )
        return self._client
