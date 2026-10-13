# Copyright (c) Lineaje, Inc. All rights reserved.
# Lineaje UnifAI guardrail  version=2.0.0-alpha
def _lineaje_load_gr_client():
    """Lineaje-added: load gr_stub_client.py without a pip dependency."""
    import sys as _s, importlib.util as _ilu
    from pathlib import Path as _P
    n = "_lineaje_gr_stub_client"
    if n in _s.modules: return _s.modules[n]
    h = _P(__file__).resolve().parent
    _cand = next((d / "gr_stub_client.py" for d in [h, *h.parents][:8] if (d / "gr_stub_client.py").is_file()), h / "gr_stub_client.py")
    _spec = _ilu.spec_from_file_location(n, _cand)
    _s.modules[n] = _m = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_m); return _m
def _lineaje_current_model():
    """Lineaje-added: reread the app's model setting for every request."""
    import os as _o
    from pathlib import Path as _P
    _keys = ("OPENROUTER_MODEL", "LLM_MODEL", "MODEL_NAME", "MODEL_ID", "OPENAI_MODEL", "ANTHROPIC_MODEL", "BEDROCK_MODEL_ID")
    _here = _P(__file__).resolve().parent
    for _path in (_here / ".env", *(_p / ".env" for _p in list(_here.parents)[:8])):
        if not _path.is_file(): continue
        try: _lines = _path.read_text(encoding="utf-8").splitlines()
        except OSError: continue
        _values = {}
        for _line in _lines:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line: continue
            _key, _, _value = _line.partition("=")
            if _key.strip() in _keys: _values[_key.strip()] = _value.strip().strip(chr(34)).strip(chr(39))
        for _key in _keys:
            if _values.get(_key): return _values[_key]
    return next((_o.environ[_key].strip() for _key in _keys if _o.environ.get(_key, "").strip()), "")

import logging
import os
import re
from enum import Enum
from typing import Any, Dict, Hashable, List, Optional, Type, Union
from uuid import UUID

from langchain_core.prompts.base import BasePromptTemplate
from langchain_core.tools import BaseTool
from langgraph.graph import END, START
from pydantic import BaseModel
from rapidfuzz import fuzz, process

from quivr_core.base_config import QuivrBaseConfig
from quivr_core.config import MegaparseConfig
from quivr_core.llm_tools.llm_tools import TOOLS_CATEGORIES, TOOLS_LISTS, LLMToolFactory
from quivr_core.processor.splitter import SplitterConfig

logger = logging.getLogger("quivr_core")
MIN_CONTEXT_TOKENS = 4096
MIN_OUTPUT_TOKENS = 4096


def normalize_to_env_variable_name(name: str) -> str:
    # Replace any character that is not a letter, digit, or underscore with an underscore
    env_variable_name = re.sub(r"[^A-Za-z0-9_]", "_", name).upper()

    # Check if the normalized name starts with a digit
    if env_variable_name[0].isdigit():
        raise ValueError(
            f"Invalid environment variable name '{env_variable_name}': Cannot start with a digit."
        )

    # LINEAJE: enforce() `env_variable_name` at agent->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:7cca50e88e4212ee7155cedb4f72038e396106f56efe60768505a125a3475e60'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:7cca50e88e4212ee7155cedb4f72038e396106f56efe60768505a125a3475e60', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='user_interface', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/entities/config.py', 'line': 34, 'function': 'normalize_to_env_variable_name'}})
    try:
        env_variable_name = _gr_client.enforce(_gr_site, env_variable_name, content_type='text/plain')
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    return env_variable_name


class SpecialEdges(str, Enum):
    start = "START"
    end = "END"


class BrainConfig(QuivrBaseConfig):
    brain_id: UUID | None = None
    name: str

    @property
    def id(self) -> UUID | None:
        return self.brain_id


class DefaultWebSearchTool(str, Enum):
    TAVILY = "tavily"


class DefaultRerankers(str, Enum):
    COHERE = "cohere"
    JINA = "jina"
    # MIXEDBREAD = "mixedbread-ai"

    @property
    def default_model(self) -> str:
        # Mapping of suppliers to their default models
        return {
            self.COHERE: "rerank-v3.5",
            self.JINA: "jina-reranker-v2-base-multilingual",
            # self.MIXEDBREAD: "rmxbai-rerank-large-v1",
        }[self]


class DefaultModelSuppliers(str, Enum):
    OPENAI = "openai"
    AZURE = "azure"
    ANTHROPIC = "anthropic"
    META = "meta"
    MISTRAL = "mistral"
    GROQ = "groq"
    GEMINI = "gemini"


class LLMConfig(QuivrBaseConfig):
    max_context_tokens: int | None = None
    max_output_tokens: int | None = None
    tokenizer_hub: str | None = None


class LLMModelConfig:
    _model_defaults: Dict[DefaultModelSuppliers, Dict[str, LLMConfig]] = {
        DefaultModelSuppliers.OPENAI: {
            "gpt-4.1": LLMConfig(
                max_context_tokens=1047576,
                max_output_tokens=32768,
                tokenizer_hub="Quivr/gpt-4o",
            ),
            "gpt-4o": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=16384,
                tokenizer_hub="Quivr/gpt-4o",
            ),
            "gpt-4o-mini": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=16384,
                tokenizer_hub="Quivr/gpt-4o",
            ),
            "o3-mini": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=100000,
                tokenizer_hub="Quivr/gpt-4o",
            ),
            "o4-mini": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=100000,
                tokenizer_hub="Quivr/gpt-4o",
            ),
            "o1-mini": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=65536,
                tokenizer_hub="Quivr/gpt-4o",
            ),
            "o1-preview": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=32768,
                tokenizer_hub="Quivr/gpt-4o",
            ),
            "o1": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=100000,
                tokenizer_hub="Quivr/gpt-4o",
            ),
            "gpt-4-turbo": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/gpt-4",
            ),
            "gpt-4": LLMConfig(
                max_context_tokens=8192,
                max_output_tokens=8192,
                tokenizer_hub="Quivr/gpt-4",
            ),
            "gpt-3.5-turbo": LLMConfig(
                max_context_tokens=16385,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/gpt-3.5-turbo",
            ),
            "text-embedding-3-large": LLMConfig(
                max_context_tokens=8191, tokenizer_hub="Quivr/text-embedding-ada-002"
            ),
            "text-embedding-3-small": LLMConfig(
                max_context_tokens=8191, tokenizer_hub="Quivr/text-embedding-ada-002"
            ),
            "text-embedding-ada-002": LLMConfig(
                max_context_tokens=8191, tokenizer_hub="Quivr/text-embedding-ada-002"
            ),
        },
        DefaultModelSuppliers.ANTHROPIC: {
            "claude-opus-4": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=8192,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-sonnet-4": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=8192,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-3-7-sonnet": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=8192,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-3-5-sonnet": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=8192,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-3-opus": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-3-sonnet": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-3-haiku": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-2-1": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-2-0": LLMConfig(
                max_context_tokens=100000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-instant-1-2": LLMConfig(
                max_context_tokens=100000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
        },
        # Unclear for LLAMA models...
        # see https://huggingface.co/meta-llama/Llama-3.1-405B-Instruct/discussions/6
        DefaultModelSuppliers.META: {
            "llama-3.1": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/Meta-Llama-3.1-Tokenizer",
            ),
            "llama-3": LLMConfig(
                max_context_tokens=8192,
                max_output_tokens=2048,
                tokenizer_hub="Quivr/llama3-tokenizer-new",
            ),
            "code-llama": LLMConfig(
                max_context_tokens=16384, tokenizer_hub="Quivr/llama-code-tokenizer"
            ),
        },
        DefaultModelSuppliers.GROQ: {
            "llama-3.3-70b": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=32768,
                tokenizer_hub="Quivr/Meta-Llama-3.1-Tokenizer",
            ),
            "llama-3.1-70b": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=32768,
                tokenizer_hub="Quivr/Meta-Llama-3.1-Tokenizer",
            ),
            "llama-3": LLMConfig(
                max_context_tokens=8192, tokenizer_hub="Quivr/llama3-tokenizer-new"
            ),
            "code-llama": LLMConfig(
                max_context_tokens=16384, tokenizer_hub="Quivr/llama-code-tokenizer"
            ),
            "deepseek-r1-distill-llama-70b": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=32768,
                tokenizer_hub="Quivr/Meta-Llama-3.1-Tokenizer",
            ),
            "meta-llama/llama-4-maverick-17b-128e-instruct": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=32768,
                tokenizer_hub="Quivr/Meta-Llama-3.1-Tokenizer",
            ),
        },
        DefaultModelSuppliers.MISTRAL: {
            "mistral-large": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/mistral-tokenizer-v3",
            ),
            "mistral-small": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/mistral-tokenizer-v3",
            ),
            "mistral-nemo": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/Mistral-Nemo-Instruct-Tokenizer",
            ),
            "codestral": LLMConfig(
                max_context_tokens=32000, tokenizer_hub="Quivr/mistral-tokenizer-v3"
            ),
        },
        DefaultModelSuppliers.GEMINI: {
            "gemini-2.5": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/gemini-tokenizer",
            ),
        },
    }

    @classmethod
    def get_supplier_by_model_name(cls, model: str) -> DefaultModelSuppliers | None:
        # Iterate over the suppliers and their models
        for supplier, models in cls._model_defaults.items():
            # Check if the model name or a base part of the model name is in the supplier's models
            for base_model_name in models:
                if model.startswith(base_model_name):
                    return supplier
        # Return None if no supplier matches the model name
        return None

    @classmethod
    def get_llm_model_config(
        cls, supplier: DefaultModelSuppliers, model_name: str
    ) -> Optional[LLMConfig]:
        """Retrieve the LLMConfig (context and tokenizer_hub) for a given supplier and model."""
        supplier_defaults = cls._model_defaults.get(supplier)
        if not supplier_defaults:
            return None

        # Use startswith logic for matching model names
        for key, config in supplier_defaults.items():
            if model_name.startswith(key):
                return config

        return None


class LLMEndpointConfig(QuivrBaseConfig):
    supplier: DefaultModelSuppliers = DefaultModelSuppliers.OPENAI
    model: str = "gpt-4o"
    tokenizer_hub: str | None = None
    llm_base_url: str | None = None
    env_variable_name: str | None = None
    llm_api_key: str | None = None
    max_context_tokens: int = 20000
    max_output_tokens: int = 4096
    temperature: float = 0.3
    streaming: bool = True
    prompt: BasePromptTemplate | None = None

    _FALLBACK_TOKENIZER = "cl100k_base"

    def __hash__(self):
        return hash(
            (
                self.supplier,
                self.model,
                self.tokenizer_hub,
                self.llm_base_url,
                self.env_variable_name,
                self.llm_api_key,
                self.max_context_tokens,
                self.max_output_tokens,
                self.temperature,
                self.streaming,
                repr(self.prompt) if self.prompt is not None else None,
            )
        )

    @property
    def fallback_tokenizer(self) -> str:
        return self._FALLBACK_TOKENIZER

    def __init__(self, **data):
        super().__init__(**data)
        self.set_llm_model_config()
        self.set_api_key()

    def set_api_key(self, force_reset: bool = False):
        if not self.supplier:
            return

        # Check if the corresponding API key environment variable is set
        if force_reset or not self.env_variable_name:
            self.env_variable_name = (
                f"{normalize_to_env_variable_name(self.supplier)}_API_KEY"
            )

        if not self.llm_api_key or force_reset:
            self.llm_api_key = os.getenv(self.env_variable_name)

        if not self.llm_api_key:
            _lineaje_payload = f"The API key for supplier '{self.supplier}' is not set. "
            # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:6b93fde637d531cb05b24ec1a399edcda9d00da44d82d2e8278fff44e82bb838'
            _gr_client = _lineaje_load_gr_client()
            _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:6b93fde637d531cb05b24ec1a399edcda9d00da44d82d2e8278fff44e82bb838', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/entities/config.py', 'line': 363, 'function': 'LLMEndpointConfig.set_api_key'}})
            try:
                _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
            except _gr_client.GuardrailUnavailableError:
                pass
            except PermissionError:
                pass
            logger.warning(_lineaje_payload)
            _lineaje_payload = f"Please set the environment variable: '{self.env_variable_name}'. "
            # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:dac4821596c6b7283cfd8ceeab22034a2a46098f541d50c951e59063a0eed288'
            _gr_client = _lineaje_load_gr_client()
            _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:dac4821596c6b7283cfd8ceeab22034a2a46098f541d50c951e59063a0eed288', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/entities/config.py', 'line': 364, 'function': 'LLMEndpointConfig.set_api_key'}})
            try:
                _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
            except _gr_client.GuardrailUnavailableError:
                pass
            except PermissionError:
                pass
            logger.warning(
                _lineaje_payload
            )

    def set_llm_model_config(self):
        # Automatically set context_length and tokenizer_hub based on the supplier and model
        llm_model_config = LLMModelConfig.get_llm_model_config(
            self.supplier, self.model
        )
        if llm_model_config:
            if llm_model_config.max_context_tokens:
                _max_context_tokens = (
                    llm_model_config.max_context_tokens
                    - llm_model_config.max_output_tokens
                    if llm_model_config.max_output_tokens
                    else llm_model_config.max_context_tokens
                )
                if self.max_context_tokens > _max_context_tokens:
                    _lineaje_payload = f"Lowering max_context_tokens from {self.max_context_tokens} to {_max_context_tokens}"
                    # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:60f55a7e1f438fe199ed50235183cc9366d3f2595a2d173dc0fa19fab116978b'
                    _gr_client = _lineaje_load_gr_client()
                    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:60f55a7e1f438fe199ed50235183cc9366d3f2595a2d173dc0fa19fab116978b', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/entities/config.py', 'line': 382, 'function': 'LLMEndpointConfig.set_llm_model_config'}})
                    try:
                        _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
                    except _gr_client.GuardrailUnavailableError:
                        pass
                    except PermissionError:
                        pass
                    logger.warning(
                        _lineaje_payload
                    )
                    self.max_context_tokens = _max_context_tokens

                if self.max_context_tokens < MIN_CONTEXT_TOKENS:
                    _lineaje_payload = f"max_context_tokens is too low: {self.max_context_tokens}. "
                    # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:45309ce207cc7cec013d1c7064228481631edb121378b647b8ed43bfc0f6c29d'
                    _gr_client = _lineaje_load_gr_client()
                    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:45309ce207cc7cec013d1c7064228481631edb121378b647b8ed43bfc0f6c29d', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/entities/config.py', 'line': 388, 'function': 'LLMEndpointConfig.set_llm_model_config'}})
                    try:
                        _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
                    except _gr_client.GuardrailUnavailableError:
                        pass
                    except PermissionError:
                        pass
                    logger.error(
                        _lineaje_payload
                    )
                    raise ValueError(
                        f"max_context_tokens is too low: {self.max_context_tokens}. "
                    )
            if llm_model_config.max_output_tokens:
                if self.max_output_tokens > llm_model_config.max_output_tokens:
                    _lineaje_payload = f"Lowering max_output_tokens from {self.max_output_tokens} to {llm_model_config.max_output_tokens}"
                    # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:6b7a773539e95ec25376a5d1df985f6cc9d2c1765512cdf7225bc5cf8aa5a8dd'
                    _gr_client = _lineaje_load_gr_client()
                    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:6b7a773539e95ec25376a5d1df985f6cc9d2c1765512cdf7225bc5cf8aa5a8dd', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/entities/config.py', 'line': 396, 'function': 'LLMEndpointConfig.set_llm_model_config'}})
                    try:
                        _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
                    except _gr_client.GuardrailUnavailableError:
                        pass
                    except PermissionError:
                        pass
                    logger.warning(
                        _lineaje_payload
                    )
                    self.max_output_tokens = llm_model_config.max_output_tokens

                if self.max_output_tokens < MIN_OUTPUT_TOKENS:
                    _lineaje_payload = f"max_output_tokens is too low: {self.max_output_tokens}. "
                    # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:2985880eb6edf92bf1e4f6b511becbaf9d8c3ff208925fa13b8fe27e0c78b0bc'
                    _gr_client = _lineaje_load_gr_client()
                    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:2985880eb6edf92bf1e4f6b511becbaf9d8c3ff208925fa13b8fe27e0c78b0bc', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/entities/config.py', 'line': 402, 'function': 'LLMEndpointConfig.set_llm_model_config'}})
                    try:
                        _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
                    except _gr_client.GuardrailUnavailableError:
                        pass
                    except PermissionError:
                        pass
                    logger.error(
                        _lineaje_payload
                    )
                    raise ValueError(
                        f"max_output_tokens is too low: {self.max_output_tokens}. "
                    )

            self.tokenizer_hub = llm_model_config.tokenizer_hub

    def set_llm_model(self, model: str):
        supplier = LLMModelConfig.get_supplier_by_model_name(model)
        if supplier is None:
            raise ValueError(
                f"Cannot find the corresponding supplier for model {model}"
            )
        self.supplier = supplier
        self.model = model

        self.set_llm_model_config()
        self.set_api_key(force_reset=True)

    def set_from_sqlmodel(self, sqlmodel: BaseModel, mapping: Dict[str, str]):
        """
        Set attributes in LLMEndpointConfig from Model attributes using a field mapping.

        :param model_instance: An instance of the Model class.
        :param mapping: A dictionary that maps Model fields to LLMEndpointConfig fields.
                        Example: {"max_input": "max_input_tokens", "env_variable_name": "env_variable_name"}
        """
        for model_field, llm_field in mapping.items():
            if hasattr(sqlmodel, model_field) and hasattr(self, llm_field):
                setattr(self, llm_field, getattr(sqlmodel, model_field))
            else:
                raise AttributeError(
                    f"Invalid mapping: {model_field} or {llm_field} does not exist."
                )


# Cannot use Pydantic v2 field_validator because of conflicts with pydantic v1 still in use in LangChain
class RerankerConfig(QuivrBaseConfig):
    supplier: DefaultRerankers | None = None
    model: str | None = None
    top_n: int = 5  # Number of chunks returned by the re-ranker
    api_key: str | None = None
    relevance_score_threshold: float | None = None
    relevance_score_key: str = "relevance_score"

    def __init__(self, **data):
        super().__init__(**data)  # Call Pydantic's BaseModel init
        self.validate_model()  # Automatically call external validation

    def validate_model(self):
        # If model is not provided, get default model based on supplier
        if self.model is None and self.supplier is not None:
            self.model = self.supplier.default_model

        # Check if the corresponding API key environment variable is set
        if self.supplier:
            api_key_var = f"{normalize_to_env_variable_name(self.supplier)}_API_KEY"
            self.api_key = os.getenv(api_key_var)

            if self.api_key is None:
                raise ValueError(
                    f"The API key for supplier '{self.supplier}' is not set. "
                    f"Please set the environment variable: {api_key_var}"
                )


class ConditionalEdgeConfig(QuivrBaseConfig):
    routing_function: str
    conditions: Union[list, Dict[Hashable, str]]

    def __init__(self, **data):
        super().__init__(**data)
        self.resolve_special_edges()

    def resolve_special_edges(self):
        """Replace SpecialEdges enum values with their corresponding langgraph values."""

        if isinstance(self.conditions, dict):
            # If conditions is a dictionary, iterate through the key-value pairs
            for key, value in self.conditions.items():
                if value == SpecialEdges.end:
                    self.conditions[key] = END
                elif value == SpecialEdges.start:
                    self.conditions[key] = START
        elif isinstance(self.conditions, list):
            # If conditions is a list, iterate through the values
            for index, value in enumerate(self.conditions):
                if value == SpecialEdges.end:
                    self.conditions[index] = END
                elif value == SpecialEdges.start:
                    self.conditions[index] = START


class NodeConfig(QuivrBaseConfig):
    name: str
    description: str | None = None
    edges: List[str] | None = None
    conditional_edge: ConditionalEdgeConfig | None = None
    tools: List[Dict[str, Any]] | None = None
    instantiated_tools: List[BaseTool | Type] | None = None

    def __init__(self, **data):
        super().__init__(**data)
        self._instantiate_tools()
        self.resolve_special_edges_in_name_and_edges()

    def resolve_special_edges_in_name_and_edges(self):
        """Replace SpecialEdges enum values in name and edges with corresponding langgraph values."""
        if self.name == SpecialEdges.start:
            self.name = START
        elif self.name == SpecialEdges.end:
            self.name = END

        if self.edges:
            for i, edge in enumerate(self.edges):
                if edge == SpecialEdges.start:
                    self.edges[i] = START
                elif edge == SpecialEdges.end:
                    self.edges[i] = END

    def _instantiate_tools(self):
        """Instantiate tools based on the configuration."""
        if self.tools:
            self.instantiated_tools = [
                LLMToolFactory.create_tool(tool_config.pop("name"), tool_config)
                for tool_config in self.tools
            ]


class DefaultWorkflow(str, Enum):
    RAG = "rag"

    @property
    def nodes(self) -> List[NodeConfig]:
        # Mapping of workflow types to their default node configurations
        workflows = {
            self.RAG: [
                NodeConfig(name=START, edges=["filter_history"]),
                NodeConfig(name="filter_history", edges=["rewrite"]),
                NodeConfig(name="rewrite", edges=["retrieve"]),
                NodeConfig(name="retrieve", edges=["generate_rag"]),
                NodeConfig(name="generate_rag", edges=[END]),
            ]
        }
        return workflows[self]


class WorkflowConfig(QuivrBaseConfig):
    name: str | None = None
    nodes: List[NodeConfig] = []
    available_tools: List[str] | None = None
    validated_tools: List[BaseTool | Type] = []
    activated_tools: List[BaseTool | Type] = []

    def __init__(self, **data):
        super().__init__(**data)
        self.check_first_node_is_start()
        self.validate_available_tools()

    def check_first_node_is_start(self):
        if self.nodes and self.nodes[0].name != START:
            raise ValueError(f"The first node should be a {SpecialEdges.start} node")

    def get_node_tools(self, node_name: str) -> List[Any]:
        """Get tools for a specific node."""
        for node in self.nodes:
            if node.name == node_name and node.instantiated_tools:
                return node.instantiated_tools
        return []

    def validate_available_tools(self):
        if self.available_tools:
            valid_tools = list(TOOLS_CATEGORIES.keys()) + list(TOOLS_LISTS.keys())
            for tool in self.available_tools:
                if tool.lower() in valid_tools:
                    self.validated_tools.append(
                        LLMToolFactory.create_tool(tool, {}).tool
                    )
                else:
                    matches = process.extractOne(
                        tool.lower(), valid_tools, scorer=fuzz.WRatio
                    )
                    if matches:
                        raise ValueError(
                            f"Tool {tool} is not a valid ToolsCategory or ToolsList. Did you mean {matches[0]}?"
                        )
                    else:
                        raise ValueError(
                            f"Tool {tool} is not a valid ToolsCategory or ToolsList"
                        )


class RetrievalConfig(QuivrBaseConfig):
    reranker_config: RerankerConfig = RerankerConfig()
    llm_config: LLMEndpointConfig = LLMEndpointConfig()
    max_history: int = 10
    max_files: int = 20
    k: int = 40  # Number of chunks returned by the retriever
    prompt: str | None = None
    workflow_config: WorkflowConfig = WorkflowConfig(nodes=DefaultWorkflow.RAG.nodes)

    def __init__(self, **data):
        super().__init__(**data)
        self.llm_config.set_api_key(force_reset=True)


class ParserConfig(QuivrBaseConfig):
    splitter_config: SplitterConfig = SplitterConfig()
    megaparse_config: MegaparseConfig = MegaparseConfig()


class IngestionConfig(QuivrBaseConfig):
    parser_config: ParserConfig = ParserConfig()


class AssistantConfig(QuivrBaseConfig):
    retrieval_config: RetrievalConfig = RetrievalConfig()
    ingestion_config: IngestionConfig = IngestionConfig()
