# Copyright (c) Lineaje, Inc. All rights reserved.
# Lineaje UnifAI guardrail  version=2.0.0-alpha
def _lineaje_load_gr_client():
    """Lineaje-added: load gr_stub_client.py without a pip dependency (missing / broken: a pass-through client)."""
    import sys as _s, importlib.util as _ilu
    from pathlib import Path as _P
    n = "_lineaje_gr_stub_client"
    if n in _s.modules: return _s.modules[n]
    try:
        h = _P(__file__).resolve().parent
        _cand = next((d / "gr_stub_client.py" for d in [h, *h.parents][:8] if (d / "gr_stub_client.py").is_file()), h / "gr_stub_client.py")
        _spec = _ilu.spec_from_file_location(n, _cand)
        _s.modules[n] = _m = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_m); return _m
    except Exception:
        _s.modules.pop(n, None)
        return type('_lineaje_gr_unavailable', (), {'STUB_API': 999999, 'GuardrailUnavailableError': type('GuardrailUnavailableError', (PermissionError,), {}), 'SiteDescriptor': staticmethod(lambda *a, **k: None), 'new_interaction_id': staticmethod(lambda *a, **k: None), 'enforce': staticmethod(lambda _s, _p, *a, **k: _p), 'enforce_request': staticmethod(lambda _s, _p, *a, **k: _p), 'enforce_reply': staticmethod(lambda _s, _p, *a, **k: _p)})
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
import time
from typing import Union
from urllib.parse import parse_qs, urlparse

import tiktoken
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_mistralai import ChatMistralAI
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from pydantic import SecretStr

from quivr_core.brain.info import LLMInfo
from quivr_core.rag.entities.config import DefaultModelSuppliers, LLMEndpointConfig
from quivr_core.rag.utils import model_supports_function_calling

logger = logging.getLogger("quivr_core")


class LLMTokenizer:
    _cache: dict[
        int, tuple["LLMTokenizer", int, float]
    ] = {}  # {hash: (tokenizer, size_bytes, last_access_time)}
    _max_cache_size_mb: int = 50
    _max_cache_count: int = 5  # Default maximum number of cached tokenizers
    _current_cache_size: int = 0
    _default_size: int = 5 * 1024 * 1024

    def __init__(self, tokenizer_hub: str | None, fallback_tokenizer: str):
        self.tokenizer_hub = tokenizer_hub
        self.fallback_tokenizer = fallback_tokenizer

        if self.tokenizer_hub:
            # To prevent the warning
            # huggingface/tokenizers: The current process just got forked, after parallelism has already been used. Disabling parallelism to avoid deadlocks...
            os.environ["TOKENIZERS_PARALLELISM"] = (
                "false"
                if not os.environ.get("TOKENIZERS_PARALLELISM")
                else os.environ["TOKENIZERS_PARALLELISM"]
            )
            try:
                if "text-embedding-ada-002" in self.tokenizer_hub:
                    from transformers import GPT2TokenizerFast

                    self.tokenizer = GPT2TokenizerFast.from_pretrained(
                        self.tokenizer_hub
                    )
                else:
                    from transformers import AutoTokenizer

                    self.tokenizer = AutoTokenizer.from_pretrained(self.tokenizer_hub)
            except OSError:  # if we don't manage to connect to huggingface and/or no cached models are present
                _lineaje_payload = f"Cannot acces the configured tokenizer from {self.tokenizer_hub}, using the default tokenizer {self.fallback_tokenizer}"
                # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:5c6a6c5e82edb580ed4cab54a9cb7ba4af17657e237d98a84ab76e14ad6a4a90'
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:5c6a6c5e82edb580ed4cab54a9cb7ba4af17657e237d98a84ab76e14ad6a4a90', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, fail_mode='BLOCK', source_type='agent', destination_type='log', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 56, 'function': 'LLMTokenizer.__init__'}, 'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 56, 'function': '__init__', 'agent_name': 'LLMTokenizer', 'agent_name_source': 'inferred_from_class', 'not_on_graph': True})
                try:
                    _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    pass
                logger.warning(
                    _lineaje_payload
                )
                self.tokenizer = tiktoken.get_encoding(self.fallback_tokenizer)
        else:
            self.tokenizer = tiktoken.get_encoding(self.fallback_tokenizer)

        # More accurate size estimation
        self._size_bytes = self._calculate_tokenizer_size()

    def _calculate_tokenizer_size(self) -> int:
        """Calculate size of tokenizer by summing the sizes of its vocabulary and model files"""
        # By default, return a size of 5 MB
        if not hasattr(self.tokenizer, "vocab_files_names") or not hasattr(
            self.tokenizer, "init_kwargs"
        ):
            return self._default_size

        total_size = 0

        # Get the file keys from vocab_files_names
        file_keys = self.tokenizer.vocab_files_names.keys()
        # Look up these files in init_kwargs
        for key in file_keys:
            if file_path := self.tokenizer.init_kwargs.get(key):
                try:
                    total_size += os.path.getsize(file_path)
                except (OSError, FileNotFoundError):
                    _lineaje_payload = f"Could not access tokenizer file: {file_path}"
                    # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:596034588626a1bf5d0a2b7e1aa5cd77c7da97a36fd0c15ce3a4c2a65621b2b8'
                    _gr_client = _lineaje_load_gr_client()
                    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:596034588626a1bf5d0a2b7e1aa5cd77c7da97a36fd0c15ce3a4c2a65621b2b8', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, fail_mode='BLOCK', source_type='agent', destination_type='log', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 84, 'function': 'LLMTokenizer._calculate_tokenizer_size'}, 'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 84, 'function': '_calculate_tokenizer_size', 'agent_name': 'LLMTokenizer', 'agent_name_source': 'inferred_from_class', 'not_on_graph': True})
                    try:
                        _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
                    except _gr_client.GuardrailUnavailableError:
                        pass
                    except PermissionError:
                        pass
                    logger.debug(_lineaje_payload)

        return total_size if total_size > 0 else self._default_size

    @classmethod
    def load(cls, tokenizer_hub: str, fallback_tokenizer: str):
        cache_key = hash(str(tokenizer_hub))

        # If in cache, update last access time and return
        if cache_key in cls._cache:
            tokenizer, size, _ = cls._cache[cache_key]
            cls._cache[cache_key] = (tokenizer, size, time.time())
            return tokenizer

        # Create new instance
        instance = cls(tokenizer_hub, fallback_tokenizer)

        # Check if adding this would exceed either cache limit
        while (
            cls._current_cache_size + instance._size_bytes
            > cls._max_cache_size_mb * 1024 * 1024
            or len(cls._cache) >= cls._max_cache_count
        ):
            # Find least recently used item
            oldest_key = min(
                cls._cache.keys(),
                key=lambda k: cls._cache[k][2],  # last_access_time
            )
            # Remove it
            _, removed_size, _ = cls._cache.pop(oldest_key)
            cls._current_cache_size -= removed_size

        # Add new instance to cache with current timestamp
        cls._cache[cache_key] = (instance, instance._size_bytes, time.time())
        cls._current_cache_size += instance._size_bytes
        return instance

    @classmethod
    def set_max_cache_size_mb(cls, size_mb: int):
        """Set the maximum cache size in megabytes."""
        cls._max_cache_size_mb = size_mb
        cls._cleanup_cache()

    @classmethod
    def set_max_cache_count(cls, count: int):
        """Set the maximum number of tokenizers to cache."""
        cls._max_cache_count = count
        cls._cleanup_cache()

    @classmethod
    def _cleanup_cache(cls):
        """Clean up cache when limits are exceeded."""
        while (
            cls._current_cache_size > cls._max_cache_size_mb * 1024 * 1024
            or len(cls._cache) > cls._max_cache_count
        ):
            oldest_key = min(cls._cache.keys(), key=lambda k: cls._cache[k][2])
            _, removed_size, _ = cls._cache.pop(oldest_key)
            cls._current_cache_size -= removed_size

    @classmethod
    def preload_tokenizers(cls, models: list[str] | None = None):
        """Preload tokenizers into cache.

        Args:
            models: Optional list of model names (e.g. 'gpt-4o', 'claude-3-5-sonnet').
                   If None, preloads all available tokenizers.
        """
        from quivr_core.rag.entities.config import LLMModelConfig

        unique_tokenizer_hubs = set()

        # Collect tokenizer hubs based on provided models or all available
        if models:
            for model_name in models:
                # Find matching model configurations
                for supplier_models in LLMModelConfig._model_defaults.values():
                    for base_model_name, config in supplier_models.items():
                        # Check if the model name matches or starts with the base model name
                        if (
                            model_name.startswith(base_model_name)
                            and config.tokenizer_hub
                        ):
                            unique_tokenizer_hubs.add(config.tokenizer_hub)
                            break
        else:
            # Original behavior - collect all unique tokenizer hubs
            for supplier_models in LLMModelConfig._model_defaults.values():
                for config in supplier_models.values():
                    if config.tokenizer_hub:
                        unique_tokenizer_hubs.add(config.tokenizer_hub)

        # Load each unique tokenizer
        for hub in unique_tokenizer_hubs:
            try:
                cls.load(hub, LLMEndpointConfig._FALLBACK_TOKENIZER)
                _lineaje_payload = (f"Successfully preloaded tokenizer: {hub}. "
                    f"Total cache size: {cls._current_cache_size / (1024 * 1024):.2f} MB. "
                    f"Cache count: {len(cls._cache)}")
                # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:2800f44e8702e107f333e4dad839f6da19f2f6057729eae69d9f44f9df695d36'
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:2800f44e8702e107f333e4dad839f6da19f2f6057729eae69d9f44f9df695d36', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, fail_mode='BLOCK', source_type='agent', destination_type='log', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 180, 'function': 'LLMTokenizer.preload_tokenizers'}, 'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 180, 'function': 'preload_tokenizers', 'agent_name': 'LLMTokenizer', 'agent_name_source': 'inferred_from_class', 'not_on_graph': True})
                try:
                    _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    pass
                logger.info(
                    _lineaje_payload
                )
            except Exception as e:
                _lineaje_payload = f"Failed to preload tokenizer {hub}: {str(e)}"
                # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:a3126c7630767aa25bb1a591e6417fc30e963e3b7d1ac3d75f099679f9f55f41'
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:a3126c7630767aa25bb1a591e6417fc30e963e3b7d1ac3d75f099679f9f55f41', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, fail_mode='BLOCK', source_type='agent', destination_type='log', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 186, 'function': 'LLMTokenizer.preload_tokenizers'}, 'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 186, 'function': 'preload_tokenizers', 'agent_name': 'LLMTokenizer', 'agent_name_source': 'inferred_from_class', 'not_on_graph': True})
                try:
                    _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    pass
                logger.warning(_lineaje_payload)


class LLMEndpoint:
    _cache = {}

    def __init__(self, llm_config: LLMEndpointConfig, llm: BaseChatModel):
        self._config = llm_config
        self._llm = llm
        self._supports_func_calling = model_supports_function_calling(
            self._config.model
        )

        self.llm_tokenizer = LLMTokenizer.load(
            llm_config.tokenizer_hub, llm_config.fallback_tokenizer
        )

    def count_tokens(self, text: str) -> int:
        # Tokenize the input text and return the token count
        encoding = self.llm_tokenizer.tokenizer.encode(text)
        return len(encoding)

    def get_config(self):
        return self._config

    @classmethod
    def from_config(cls, config: LLMEndpointConfig = LLMEndpointConfig()):
        hashed_config = hash(config)
        if hashed_config in cls._cache:
            return cls._cache[hashed_config]

        _llm: Union[
            AzureChatOpenAI,
            ChatOpenAI,
            ChatAnthropic,
            ChatMistralAI,
            ChatGoogleGenerativeAI,
            ChatGroq,
        ]
        try:
            if config.supplier == DefaultModelSuppliers.AZURE:
                # Parse the URL
                parsed_url = urlparse(config.llm_base_url)
                deployment = parsed_url.path.split("/")[3]  # type: ignore
                api_version = parse_qs(parsed_url.query).get("api-version", [None])[0]  # type: ignore
                azure_endpoint = f"https://{parsed_url.netloc}"  # type: ignore
                # LINEAJE: approved-model gate `_lineaje_model_evidence` at agent->llm pre_model — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:d27b38d0a00c2b0151c6bc6acb0cdb3baa3d73432c4aa9da4cfc6a826739bb4c'
                _lineaje_model_evidence = {'model': deployment, 'client': 'AzureChatOpenAI', 'provider': 'langchain_openai', 'model_source': 'call_kwarg', 'project': 'tree'}
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:d27b38d0a00c2b0151c6bc6acb0cdb3baa3d73432c4aa9da4cfc6a826739bb4c', phase='pre_model', boundary={'source': 'agent_config', 'sink': 'model'}, fail_mode='BLOCK', source_type='agent', destination_type='llm', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'destination': {'entity_type': 'llm', 'name': 'gpt-4o', 'provider': 'openai', 'version': ''}, 'identity': {'app': {'name': 'quivr_lineaje', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo', 'version': 'main'}, 'destination': {'entity_type': 'aimodel', 'name': 'GPT', 'purl': 'pkg:aimodel/GPT@4o', 'version': '4o'}}, 'invocation': {'file': 'core/quivr_core/llm/llm_endpoint.py', 'function': 'LLMEndpoint.from_config', 'line': 232}, 'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 232, 'function': 'from_config', 'agent_name': 'LLMEndpoint', 'agent_name_source': 'inferred_from_class', 'boundary_id': 'bnd:88c4ebfdf36b4b84'})
                try:
                    _lineaje_model_evidence = _gr_client.enforce(_gr_site, _lineaje_model_evidence, content_type='application/json')
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    raise
                _llm = AzureChatOpenAI(
                    azure_deployment=deployment,  # type: ignore
                    api_version=api_version,
                    api_key=SecretStr(config.llm_api_key)
                    if config.llm_api_key
                    else None,
                    azure_endpoint=azure_endpoint,
                    max_tokens=config.max_output_tokens,
                    temperature=config.temperature,
                )
            elif config.supplier == DefaultModelSuppliers.ANTHROPIC:
                assert config.llm_api_key, "Can't load model config"
                # LINEAJE: approved-model gate `_lineaje_model_evidence` at agent->llm pre_model — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:36aa6da871f70b75470e80141a5b5fba0a765501163cdce8d65dd176ef8090ad'
                _lineaje_model_evidence = {'model': config.model, 'client': 'ChatAnthropic', 'provider': 'langchain_anthropic', 'model_source': 'call_kwarg', 'project': 'tree'}
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:36aa6da871f70b75470e80141a5b5fba0a765501163cdce8d65dd176ef8090ad', phase='pre_model', boundary={'source': 'agent_config', 'sink': 'model'}, fail_mode='BLOCK', source_type='agent', destination_type='llm', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'destination': {'entity_type': 'llm', 'name': 'ChatAnthropic', 'provider': '', 'version': ''}, 'identity': {'app': {'name': 'quivr_lineaje', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo', 'version': 'main'}, 'destination': {'entity_type': 'aimodel', 'name': 'ChatAnthropic', 'purl': 'pkg:aimodel/ChatAnthropic@1.0.0', 'version': '1.0.0'}}, 'invocation': {'file': 'core/quivr_core/llm/llm_endpoint.py', 'function': 'LLMEndpoint.from_config', 'line': 244}, 'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 244, 'function': 'from_config', 'agent_name': 'LLMEndpoint', 'agent_name_source': 'inferred_from_class', 'boundary_id': 'bnd:b1c59ea421e21d4c'})
                try:
                    _lineaje_model_evidence = _gr_client.enforce(_gr_site, _lineaje_model_evidence, content_type='application/json')
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    raise
                _llm = ChatAnthropic(
                    model_name=config.model,
                    api_key=SecretStr(config.llm_api_key),
                    base_url=config.llm_base_url,
                    max_tokens_to_sample=config.max_output_tokens,
                    temperature=config.temperature,
                    timeout=None,
                    stop=None,
                )
            elif config.supplier == DefaultModelSuppliers.OPENAI:
                # LINEAJE: approved-model gate `_lineaje_model_evidence` at agent->llm pre_model — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:2be5eda52e70ca204b20759f6264901960440947e8a3c12aae0f318747db0c74'
                _lineaje_model_evidence = {'model': config.model, 'client': 'ChatOpenAI', 'provider': 'langchain_openai', 'model_source': 'call_kwarg', 'project': 'tree'}
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:2be5eda52e70ca204b20759f6264901960440947e8a3c12aae0f318747db0c74', phase='pre_model', boundary={'source': 'agent_config', 'sink': 'model'}, fail_mode='BLOCK', source_type='agent', destination_type='llm', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'destination': {'entity_type': 'llm', 'name': 'gpt-4o', 'provider': 'openai', 'version': ''}, 'identity': {'app': {'name': 'quivr_lineaje', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo', 'version': 'main'}, 'destination': {'entity_type': 'aimodel', 'name': 'GPT', 'purl': 'pkg:aimodel/GPT@4o', 'version': '4o'}}, 'invocation': {'file': 'core/quivr_core/llm/llm_endpoint.py', 'function': 'LLMEndpoint.from_config', 'line': 254}, 'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 254, 'function': 'from_config', 'agent_name': 'LLMEndpoint', 'agent_name_source': 'inferred_from_class', 'boundary_id': 'bnd:b2baa63fee7590a0'})
                try:
                    _lineaje_model_evidence = _gr_client.enforce(_gr_site, _lineaje_model_evidence, content_type='application/json')
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    raise
                _llm = ChatOpenAI(
                    model=config.model,
                    api_key=SecretStr(config.llm_api_key)
                    if config.llm_api_key
                    else None,
                    base_url=config.llm_base_url,
                    max_completion_tokens=config.max_output_tokens,
                    temperature=config.temperature
                    if not config.model.startswith("o")
                    else None,
                )
            elif config.supplier == DefaultModelSuppliers.MISTRAL:
                # LINEAJE: approved-model gate `_lineaje_model_evidence` at agent->llm pre_model — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:a31b3190e9c1cd424cc2bb5d5e5742a4a95335d9f589832a9cb1774eb195c6af'
                _lineaje_model_evidence = {'model': config.model, 'client': 'ChatMistralAI', 'provider': 'langchain_mistralai', 'model_source': 'call_kwarg', 'project': 'tree'}
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:a31b3190e9c1cd424cc2bb5d5e5742a4a95335d9f589832a9cb1774eb195c6af', phase='pre_model', boundary={'source': 'agent_config', 'sink': 'model'}, fail_mode='BLOCK', source_type='agent', destination_type='llm', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'destination': {'entity_type': 'llm', 'name': 'ChatMistralAI', 'provider': '', 'version': ''}, 'identity': {'app': {'name': 'quivr_lineaje', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo', 'version': 'main'}, 'destination': {'entity_type': 'aimodel', 'name': 'ChatMistralAI', 'purl': 'pkg:aimodel/ChatMistralAI@1.0.0', 'version': '1.0.0'}}, 'invocation': {'file': 'core/quivr_core/llm/llm_endpoint.py', 'function': 'LLMEndpoint.from_config', 'line': 266}, 'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 266, 'function': 'from_config', 'agent_name': 'LLMEndpoint', 'agent_name_source': 'inferred_from_class', 'boundary_id': 'bnd:d6a1c035957c2ba3'})
                try:
                    _lineaje_model_evidence = _gr_client.enforce(_gr_site, _lineaje_model_evidence, content_type='application/json')
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    raise
                _llm = ChatMistralAI(
                    model_name=config.model,
                    api_key=SecretStr(config.llm_api_key)
                    if config.llm_api_key
                    else None,
                    base_url=config.llm_base_url,
                    temperature=config.temperature,
                )
            elif config.supplier == DefaultModelSuppliers.GEMINI:
                # LINEAJE: approved-model gate `_lineaje_model_evidence` at agent->llm pre_model — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:a79b7ec560c42888afe99379c598c5e198166102d1d71ba7fda4441ca7f6c356'
                _lineaje_model_evidence = {'model': config.model, 'client': 'ChatGoogleGenerativeAI', 'provider': 'langchain_google_genai', 'model_source': 'call_kwarg', 'project': 'tree'}
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:a79b7ec560c42888afe99379c598c5e198166102d1d71ba7fda4441ca7f6c356', phase='pre_model', boundary={'source': 'agent_config', 'sink': 'model'}, fail_mode='BLOCK', source_type='agent', destination_type='llm', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'destination': {'entity_type': 'llm', 'name': 'ChatGoogleGenerativeAI', 'provider': '', 'version': ''}, 'identity': {'app': {'name': 'quivr_lineaje', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo', 'version': 'main'}, 'destination': {'entity_type': 'aimodel', 'name': 'ChatGoogleGenerativeAI', 'purl': 'pkg:aimodel/ChatGoogleGenerativeAI@1.0.0', 'version': '1.0.0'}}, 'invocation': {'file': 'core/quivr_core/llm/llm_endpoint.py', 'function': 'LLMEndpoint.from_config', 'line': 275}, 'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 275, 'function': 'from_config', 'agent_name': 'LLMEndpoint', 'agent_name_source': 'inferred_from_class', 'boundary_id': 'bnd:788806e1e92f3d66'})
                try:
                    _lineaje_model_evidence = _gr_client.enforce(_gr_site, _lineaje_model_evidence, content_type='application/json')
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    raise
                _llm = ChatGoogleGenerativeAI(
                    model=config.model,
                    api_key=SecretStr(config.llm_api_key)
                    if config.llm_api_key
                    else None,
                    base_url=config.llm_base_url,
                    max_tokens=config.max_output_tokens,
                    temperature=config.temperature,
                )
            elif config.supplier == DefaultModelSuppliers.GROQ:
                # LINEAJE: approved-model gate `_lineaje_model_evidence` at agent->llm pre_model — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:a666f00adb954e0ec3339ede3a6ef0e832e446eebdf2aaba361925dbb5f3cdfb'
                _lineaje_model_evidence = {'model': config.model, 'client': 'ChatGroq', 'provider': 'langchain_groq', 'model_source': 'call_kwarg', 'project': 'tree'}
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:a666f00adb954e0ec3339ede3a6ef0e832e446eebdf2aaba361925dbb5f3cdfb', phase='pre_model', boundary={'source': 'agent_config', 'sink': 'model'}, fail_mode='BLOCK', source_type='agent', destination_type='llm', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'destination': {'entity_type': 'llm', 'name': 'ChatGroq', 'provider': '', 'version': ''}, 'identity': {'app': {'name': 'quivr_lineaje', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo', 'version': 'main'}, 'destination': {'entity_type': 'aimodel', 'name': 'ChatGroq', 'purl': 'pkg:aimodel/ChatGroq@1.0.0', 'version': '1.0.0'}}, 'invocation': {'file': 'core/quivr_core/llm/llm_endpoint.py', 'function': 'LLMEndpoint.from_config', 'line': 285}, 'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 285, 'function': 'from_config', 'agent_name': 'LLMEndpoint', 'agent_name_source': 'inferred_from_class', 'boundary_id': 'bnd:b2ac64cb1c84ee93'})
                try:
                    _lineaje_model_evidence = _gr_client.enforce(_gr_site, _lineaje_model_evidence, content_type='application/json')
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    raise
                _llm = ChatGroq(
                    model=config.model,
                    api_key=SecretStr(config.llm_api_key)
                    if config.llm_api_key
                    else None,
                    base_url=config.llm_base_url,
                    max_tokens=config.max_output_tokens,
                    temperature=config.temperature,
                )

            else:
                # LINEAJE: approved-model gate `_lineaje_model_evidence` at agent->llm pre_model — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:614af9bd41e02d822793fed23e7f2194575cbb1f6957e2ab5cb9608f3fc49e90'
                _lineaje_model_evidence = {'model': config.model, 'client': 'ChatOpenAI', 'provider': 'langchain_openai', 'model_source': 'call_kwarg', 'project': 'tree'}
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:614af9bd41e02d822793fed23e7f2194575cbb1f6957e2ab5cb9608f3fc49e90', phase='pre_model', boundary={'source': 'agent_config', 'sink': 'model'}, fail_mode='BLOCK', source_type='agent', destination_type='llm', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'destination': {'entity_type': 'llm', 'name': 'gpt-4o', 'provider': 'openai', 'version': ''}, 'identity': {'app': {'name': 'quivr_lineaje', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo', 'version': 'main'}, 'destination': {'entity_type': 'aimodel', 'name': 'GPT', 'purl': 'pkg:aimodel/GPT@4o', 'version': '4o'}}, 'invocation': {'file': 'core/quivr_core/llm/llm_endpoint.py', 'function': 'LLMEndpoint.from_config', 'line': 296}, 'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 296, 'function': 'from_config', 'agent_name': 'LLMEndpoint', 'agent_name_source': 'inferred_from_class', 'boundary_id': 'bnd:7da93de17bbfa0ec'})
                try:
                    _lineaje_model_evidence = _gr_client.enforce(_gr_site, _lineaje_model_evidence, content_type='application/json')
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    raise
                _llm = ChatOpenAI(
                    model=config.model,
                    api_key=SecretStr(config.llm_api_key)
                    if config.llm_api_key
                    else None,
                    base_url=config.llm_base_url,
                    max_completion_tokens=config.max_output_tokens,
                    temperature=config.temperature,
                )
            instance = cls(llm=_llm, llm_config=config)
            cls._cache[hashed_config] = instance

            return instance

        except ImportError as e:
            raise ImportError(
                "Please provide a valid BaseLLM or install quivr-core['base'] package"
            ) from e

    def supports_func_calling(self) -> bool:
        return self._supports_func_calling

    def info(self) -> LLMInfo:
        return LLMInfo(
            model=self._config.model,
            llm_base_url=(
                self._config.llm_base_url if self._config.llm_base_url else "openai"
            ),
            temperature=self._config.temperature,
            max_tokens=self._config.max_output_tokens,
            supports_function_calling=self.supports_func_calling(),
        )

    def clone_llm(self):
        """Create a new instance of the LLM with the same configuration."""
        return self._llm.__class__(**self._llm.__dict__)
