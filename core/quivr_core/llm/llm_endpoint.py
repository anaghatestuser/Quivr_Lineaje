# Copyright (c) Lineaje, Inc. All rights reserved.
# gr_check() POSTs to GR_SERVICE_URL+/enforce; fail-open unless GRBlockedError.
class GRBlockedError(Exception):
    def __init__(self, policy_id, reason):
        self.policy_id, self.reason = policy_id, reason
        super().__init__("Guardrail block for policy %r: %s" % (policy_id, reason))

def gr_check(data, source_type, destination_type, tenant_id="", timeout=5.0, **context):
    import json as _j, logging as _lg, os as _os, urllib.error as _ue, urllib.request as _ur
    _log = _lg.getLogger("lineaje.gr_client")
    hop_label = source_type + "->" + destination_type
    # A genuine policy block stops later checks in the same request context only
    # (a contextvar, not process-wide) so one blocked call never breaks the next request.
    _latch = getattr(gr_check, "_latch", None)
    if _latch is None:
        import contextvars as _cv
        _latch = gr_check._latch = _cv.ContextVar("lineaje_gr_blocked", default=None)
    _obs = bool(context.get("observe_only"))  # a log-only call never enforces, so a block neither skips nor sets it
    _prior = None if _obs else _latch.get()
    if _prior:
        _log.warning("gr_client[%s]: skipping POST /enforce — request already blocked (%s)", hop_label, _prior[1])
        try:  # still tell the Guardrail the activity happened (no data, no policy)
            import sys as _s
            _m = _s.modules.get("_lineaje_gr_stub_client")
            if _m is not None and hasattr(_m, "_report_skipped_after_block"):
                _f = getattr(_m.SiteDescriptor, "__dataclass_fields__", {})
                _m._report_skipped_after_block(_m.SiteDescriptor(site_id=context.get("site_id") or "", source_type=source_type, destination_type=destination_type, **{k: context[k] for k in ("components", "interaction_id") if context.get(k) and k in _f}), tenant_id or _os.environ.get("GR_TENANT_ID", ""))
        except Exception:
            pass
        raise GRBlockedError(_prior[0], _prior[1])
    def _blk(o):
        if isinstance(o, dict):
            return any(_blk(o.get(k)) for k in ("skill_path", "skill_file", "path", "file_path", "data", "skill_manifest_path"))
        s = str(o or "")
        b = s.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if b.endswith(".md.blocked"): return True
        try:
            if b in ("skill.md", "skills.md") and _os.path.isfile(str(o) + ".blocked"): return True
        except Exception:
            pass
        return False
    if _blk(data) or _blk(context):
        _log.warning("gr_client[%s]: quarantined skill (*.blocked) — not loaded, GR not called", hop_label)
        _latch.set(("blocked_manifest", "quarantined skill must not be read, downloaded, or loaded"))
        raise GRBlockedError("blocked_manifest", "quarantined skill must not be read, downloaded, or loaded")
    def _stub_client():
        # gr_stub_client.py (shipped next to instrumented files) loads .env, exchanges
        # the refresh token, and re-registers the site on unknown_site /
        # candidate_policies_mismatch — prefer it over the bare POST below.
        import sys as _s, importlib.util as _ilu
        from pathlib import Path as _P
        n = "_lineaje_gr_stub_client"
        if n in _s.modules: return _s.modules[n]
        if getattr(gr_check, "_no_stub_client", False): return None
        try:
            h = _P(__file__).resolve().parent
            c = next((d / "gr_stub_client.py" for d in [h, *h.parents][:8] if (d / "gr_stub_client.py").is_file()), None)
            if c is not None:
                spec = _ilu.spec_from_file_location(n, c)
                _s.modules[n] = m = _ilu.module_from_spec(spec)
                spec.loader.exec_module(m)
                if hasattr(m, "check") and hasattr(m, "SiteDescriptor"): return m
                _s.modules.pop(n, None)
        except Exception as exc:
            _s.modules.pop(n, None)
            _log.warning("gr_client[%s]: gr_stub_client.py not loadable (%s) — using inline client", hop_label, exc)
        gr_check._no_stub_client = True
        return None
    def _block(policy_id, reason):
        _log.warning("gr_client[%s]: BLOCKED by policy=%s — %s", hop_label, policy_id, reason)
        if _os.environ.get("GR_BLOCK_MODE", "enforce").lower() == "audit":
            return data
        if not _obs: _latch.set((policy_id, reason))
        raise GRBlockedError(policy_id, reason)
    tid = tenant_id or _os.environ.get("GR_TENANT_ID", "")
    _sc = _stub_client()
    if _sc is not None:
        try:
            _cp = [p if isinstance(p, dict) else {"policy_id": p} for p in (context.get("candidate_policies") or [])]
            _kw = {k: context[k] for k in ("components", "interaction_id", "observe_only") if context.get(k) and k in getattr(_sc.SiteDescriptor, "__dataclass_fields__", {})}
            _site = _sc.SiteDescriptor(site_id=context.get("site_id") or "", candidate_policies=_cp, fail_mode="BLOCK", source_type=source_type, destination_type=destination_type, **_kw)
            _d = _sc.check(_site, data, tenant_id=tid, timeout=timeout)
        except Exception as exc:
            _log.warning("gr_client[%s]: GR service call failed (%s) — failing open", hop_label, exc)
            return data
        if _d.blocked and not getattr(_d, "infra_failure", False):
            _acts = _d.actions_applied or []
            _pid = (_acts[0].get("policy_id") if _acts and isinstance(_acts[0], dict) else "") or "unknown"
            return _block(_pid, _d.warning or "Request denied by policy enforcement.")
        if _d.blocked:
            _log.warning("gr_client[%s]: GR service unavailable (%s) — failing open", hop_label, _d.warning)
            return data
        return data if _d.payload is None else _d.payload
    url = _os.environ.get("GR_SERVICE_URL", "")
    if not url:
        return data
    # Refresh token first: the GR service exchanges it for the access JWT it
    # calls the Data Service policy API with; a lineaje_pat_ PAT only
    # identifies the caller and cannot be exchanged.
    bearer = _os.environ.get("GR_BEARER_TOKEN") or _os.environ.get("LINEAJE_REFRESH_TOKEN") or _os.environ.get("LINEAJE_PAT_TOKEN") or _os.environ.get("LINEAJE_PAT", "")
    params_key = "out_params" if destination_type == "agent" else "in_params"
    def _gr_js(o):
        # JSON form of non-JSON payloads (LangChain Document, pydantic models, ...).
        if hasattr(o, "page_content"):
            return {"page_content": o.page_content, "metadata": getattr(o, "metadata", None) or {}}
        for _m in ("model_dump", "dict", "to_dict"):
            _f = getattr(o, _m, None)
            if callable(_f):
                try:
                    return _f()
                except Exception:
                    pass
        if isinstance(o, (set, tuple)):
            return list(o)
        return str(o)
    def _gr_back(orig, new):
        # Map the (possibly masked) JSON back onto the caller's own objects.
        if new == _j.loads(_j.dumps(orig, default=_gr_js)):
            return orig
        if isinstance(orig, (list, tuple)) and isinstance(new, list) and len(orig) == len(new):
            _out = [_gr_back(a, b) for a, b in zip(orig, new)]
            return tuple(_out) if isinstance(orig, tuple) else _out
        if hasattr(orig, "page_content") and isinstance(new, dict) and "page_content" in new:
            import copy as _cp
            _c = _cp.copy(orig)
            _c.page_content = new["page_content"]
            if isinstance(new.get("metadata"), dict) and hasattr(_c, "metadata"):
                _c.metadata = new["metadata"]
            return _c
        if orig is None or isinstance(orig, (str, int, float, bool, dict, list)):
            return new
        _log.warning("gr_client[%s]: masked result cannot be applied to %s — returning original", hop_label, type(orig).__name__)
        return orig
    _base = url.rstrip("/")
    if _base.lower().endswith("/enforce"): _base = _base[: -len("/enforce")].rstrip("/")
    def _post(body):
        headers = {"Content-Type": "application/json"}
        if bearer:
            headers["Authorization"] = "Bearer " + bearer
        req = _ur.Request(_base + "/enforce", data=_j.dumps(body, default=_gr_js).encode(), headers=headers, method="POST")
        with _ur.urlopen(req, timeout=timeout) as resp:
            return _j.loads(resp.read())
    try:
        _sent = _j.loads(_j.dumps(data, default=_gr_js))
        body = {"source_type": source_type, "destination_type": destination_type, params_key: {"data": _sent}}
        for _k, _v in context.items():
            if _v:
                body[_k] = _v
        if tid:
            body["tenant_id"] = tid
    except Exception as exc:
        _log.warning("gr_client[%s]: payload not serializable (%s) — failing open", hop_label, exc)
        return data
    result = None
    for _attempt in (0, 1):
        try:
            result = _post(body)
            break
        except Exception as exc:
            if isinstance(exc, _ue.HTTPError) and exc.code == 403:
                try: detail = _j.loads(exc.read()).get("detail", {})
                except Exception: detail = {}
                if not isinstance(detail, dict): detail = {"message": str(detail)}
                blocked_by = detail.get("blocked_by") or []
                if blocked_by or detail.get("error") == "request_blocked":
                    _pid = (blocked_by[0].get("policy_id") if isinstance(blocked_by[0], dict) else "") if blocked_by else ""
                    return _block(_pid or "unknown", detail.get("message", "Request denied by policy enforcement."))
                if _attempt == 0 and (body.get("site_id") or body.get("candidate_policies")):
                    # unknown_site / candidate_policies_mismatch: a site-manifest
                    # problem, not a policy verdict — re-evaluate without site scoping.
                    _log.warning("gr_client[%s]: %s — retrying without site_id", hop_label, detail.get("error") or detail.get("message") or "403")
                    body = {k: v for k, v in body.items() if k not in ("site_id", "candidate_policies")}
                    continue
            _log.warning("gr_client[%s]: GR service call failed (%s) — failing open", hop_label, exc)
            return data
    if not isinstance(result, dict):
        return data
    if result.get("status") == "escalate":
        _log.warning("gr_client[%s]: escalation flagged — passing through for human review", hop_label)
    if not isinstance(result.get("result"), dict) or "data" not in result["result"]:
        return data
    return _gr_back(data, result["result"]["data"])
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
                try:
                    _lineaje_payload = gr_check(_lineaje_payload, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:5c6a6c5e82edb580ed4cab54a9cb7ba4af17657e237d98a84ab76e14ad6a4a90', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_YRX2fVW06wDtvjKq', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/llm/llm_endpoint.py', 'line': 13, 'name': 'AzureChatOpenAI'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'AzureChatOpenAI', 'version': '1.0.0', 'purl': 'pkg:aiagent/AzureChatOpenAI@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 56, 'function': 'LLMTokenizer.__init__'}, 'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 56, 'function': '__init__', 'agent_name': 'LLMTokenizer', 'agent_name_source': 'inferred_from_class', 'call_target': 'logger.warning'})
                except Exception as _gr_exc:
                    if type(_gr_exc).__name__ == "GRBlockedError": raise
                    _lineaje_payload = _lineaje_payload
                    __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                logger.warning(
                    f"Cannot acces the configured tokenizer from {self.tokenizer_hub}, using the default tokenizer {self.fallback_tokenizer}"
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
                    try:
                        _lineaje_payload = gr_check(_lineaje_payload, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:596034588626a1bf5d0a2b7e1aa5cd77c7da97a36fd0c15ce3a4c2a65621b2b8', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_YRX2fVW06wDtvjKq', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/llm/llm_endpoint.py', 'line': 13, 'name': 'AzureChatOpenAI'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'AzureChatOpenAI', 'version': '1.0.0', 'purl': 'pkg:aiagent/AzureChatOpenAI@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 84, 'function': 'LLMTokenizer._calculate_tokenizer_size'}, 'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 84, 'function': '_calculate_tokenizer_size', 'agent_name': 'LLMTokenizer', 'agent_name_source': 'inferred_from_class', 'call_target': 'logger.debug'})
                    except Exception as _gr_exc:
                        if type(_gr_exc).__name__ == "GRBlockedError": raise
                        _lineaje_payload = _lineaje_payload
                        __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                    logger.debug(f"Could not access tokenizer file: {file_path}")

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
                try:
                    _lineaje_payload = gr_check(_lineaje_payload, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:2800f44e8702e107f333e4dad839f6da19f2f6057729eae69d9f44f9df695d36', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_YRX2fVW06wDtvjKq', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/llm/llm_endpoint.py', 'line': 13, 'name': 'AzureChatOpenAI'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'AzureChatOpenAI', 'version': '1.0.0', 'purl': 'pkg:aiagent/AzureChatOpenAI@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 180, 'function': 'LLMTokenizer.preload_tokenizers'}, 'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 180, 'function': 'preload_tokenizers', 'agent_name': 'LLMTokenizer', 'agent_name_source': 'inferred_from_class', 'call_target': 'logger.info'})
                except Exception as _gr_exc:
                    if type(_gr_exc).__name__ == "GRBlockedError": raise
                    _lineaje_payload = _lineaje_payload
                    __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                logger.info(
                    f"Successfully preloaded tokenizer: {hub}. "
                    f"Total cache size: {cls._current_cache_size / (1024 * 1024):.2f} MB. "
                    f"Cache count: {len(cls._cache)}"
                )
            except Exception as e:
                _lineaje_payload = f"Failed to preload tokenizer {hub}: {str(e)}"
                try:
                    _lineaje_payload = gr_check(_lineaje_payload, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:a3126c7630767aa25bb1a591e6417fc30e963e3b7d1ac3d75f099679f9f55f41', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_YRX2fVW06wDtvjKq', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/llm/llm_endpoint.py', 'line': 13, 'name': 'AzureChatOpenAI'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'AzureChatOpenAI', 'version': '1.0.0', 'purl': 'pkg:aiagent/AzureChatOpenAI@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 186, 'function': 'LLMTokenizer.preload_tokenizers'}, 'file': 'core/quivr_core/llm/llm_endpoint.py', 'line': 186, 'function': 'preload_tokenizers', 'agent_name': 'LLMTokenizer', 'agent_name_source': 'inferred_from_class', 'call_target': 'logger.warning'})
                except Exception as _gr_exc:
                    if type(_gr_exc).__name__ == "GRBlockedError": raise
                    _lineaje_payload = _lineaje_payload
                    __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                logger.warning(f"Failed to preload tokenizer {hub}: {str(e)}")


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
                _llm = ChatMistralAI(
                    model_name=config.model,
                    api_key=SecretStr(config.llm_api_key)
                    if config.llm_api_key
                    else None,
                    base_url=config.llm_base_url,
                    temperature=config.temperature,
                )
            elif config.supplier == DefaultModelSuppliers.GEMINI:
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
