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

    try:
        env_variable_name = gr_check(env_variable_name, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:7cca50e88e4212ee7155cedb4f72038e396106f56efe60768505a125a3475e60', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/entities/config.py', 'line': 34, 'function': 'normalize_to_env_variable_name'}, 'file': 'core/quivr_core/rag/entities/config.py', 'line': 34, 'function': 'normalize_to_env_variable_name', 'agent_name': 'normalize_to_env_variable_name', 'agent_name_source': 'inferred_from_function', 'site_kind': 'return'})
    except Exception as _gr_exc:
        if type(_gr_exc).__name__ == "GRBlockedError": raise
        env_variable_name = env_variable_name
        __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
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
            logger.warning(f"The API key for supplier '{self.supplier}' is not set. ")
            _lineaje_payload = f"Please set the environment variable: '{self.env_variable_name}'. "
            try:
                _lineaje_payload = gr_check(_lineaje_payload, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:6b93fde637d531cb05b24ec1a399edcda9d00da44d82d2e8278fff44e82bb838', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/entities/config.py', 'line': 364, 'function': 'LLMEndpointConfig.set_api_key'}, 'file': 'core/quivr_core/rag/entities/config.py', 'line': 364, 'function': 'set_api_key', 'agent_name': 'LLMEndpointConfig', 'agent_name_source': 'inferred_from_class', 'call_target': 'logger.warning'})
            except Exception as _gr_exc:
                if type(_gr_exc).__name__ == "GRBlockedError": raise
                _lineaje_payload = _lineaje_payload
                __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
            logger.warning(
                f"Please set the environment variable: '{self.env_variable_name}'. "
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
                    try:
                        _lineaje_payload = gr_check(_lineaje_payload, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:60f55a7e1f438fe199ed50235183cc9366d3f2595a2d173dc0fa19fab116978b', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/entities/config.py', 'line': 382, 'function': 'LLMEndpointConfig.set_llm_model_config'}, 'file': 'core/quivr_core/rag/entities/config.py', 'line': 382, 'function': 'set_llm_model_config', 'agent_name': 'LLMEndpointConfig', 'agent_name_source': 'inferred_from_class', 'call_target': 'logger.warning'})
                    except Exception as _gr_exc:
                        if type(_gr_exc).__name__ == "GRBlockedError": raise
                        _lineaje_payload = _lineaje_payload
                        __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                    logger.warning(
                        f"Lowering max_context_tokens from {self.max_context_tokens} to {_max_context_tokens}"
                    )
                    self.max_context_tokens = _max_context_tokens

                if self.max_context_tokens < MIN_CONTEXT_TOKENS:
                    _lineaje_payload = f"max_context_tokens is too low: {self.max_context_tokens}. "
                    try:
                        _lineaje_payload = gr_check(_lineaje_payload, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:45309ce207cc7cec013d1c7064228481631edb121378b647b8ed43bfc0f6c29d', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/entities/config.py', 'line': 388, 'function': 'LLMEndpointConfig.set_llm_model_config'}, 'file': 'core/quivr_core/rag/entities/config.py', 'line': 388, 'function': 'set_llm_model_config', 'agent_name': 'LLMEndpointConfig', 'agent_name_source': 'inferred_from_class', 'call_target': 'logger.error'})
                    except Exception as _gr_exc:
                        if type(_gr_exc).__name__ == "GRBlockedError": raise
                        _lineaje_payload = _lineaje_payload
                        __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                    logger.error(
                        f"max_context_tokens is too low: {self.max_context_tokens}. "
                    )
                    raise ValueError(
                        f"max_context_tokens is too low: {self.max_context_tokens}. "
                    )
            if llm_model_config.max_output_tokens:
                if self.max_output_tokens > llm_model_config.max_output_tokens:
                    _lineaje_payload = f"Lowering max_output_tokens from {self.max_output_tokens} to {llm_model_config.max_output_tokens}"
                    try:
                        _lineaje_payload = gr_check(_lineaje_payload, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:6b7a773539e95ec25376a5d1df985f6cc9d2c1765512cdf7225bc5cf8aa5a8dd', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/entities/config.py', 'line': 396, 'function': 'LLMEndpointConfig.set_llm_model_config'}, 'file': 'core/quivr_core/rag/entities/config.py', 'line': 396, 'function': 'set_llm_model_config', 'agent_name': 'LLMEndpointConfig', 'agent_name_source': 'inferred_from_class', 'call_target': 'logger.warning'})
                    except Exception as _gr_exc:
                        if type(_gr_exc).__name__ == "GRBlockedError": raise
                        _lineaje_payload = _lineaje_payload
                        __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                    logger.warning(
                        f"Lowering max_output_tokens from {self.max_output_tokens} to {llm_model_config.max_output_tokens}"
                    )
                    self.max_output_tokens = llm_model_config.max_output_tokens

                if self.max_output_tokens < MIN_OUTPUT_TOKENS:
                    _lineaje_payload = f"max_output_tokens is too low: {self.max_output_tokens}. "
                    try:
                        _lineaje_payload = gr_check(_lineaje_payload, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:2985880eb6edf92bf1e4f6b511becbaf9d8c3ff208925fa13b8fe27e0c78b0bc', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/entities/config.py', 'line': 402, 'function': 'LLMEndpointConfig.set_llm_model_config'}, 'file': 'core/quivr_core/rag/entities/config.py', 'line': 402, 'function': 'set_llm_model_config', 'agent_name': 'LLMEndpointConfig', 'agent_name_source': 'inferred_from_class', 'call_target': 'logger.error'})
                    except Exception as _gr_exc:
                        if type(_gr_exc).__name__ == "GRBlockedError": raise
                        _lineaje_payload = _lineaje_payload
                        __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                    logger.error(
                        f"max_output_tokens is too low: {self.max_output_tokens}. "
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
