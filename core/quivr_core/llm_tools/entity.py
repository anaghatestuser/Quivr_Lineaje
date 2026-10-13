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

from quivr_core.base_config import QuivrBaseConfig
from typing import Callable
from langchain_core.tools import BaseTool
from typing import Dict, Any


class ToolsCategory(QuivrBaseConfig):
    name: str
    description: str
    tools: list
    default_tool: str | None = None
    create_tool: Callable

    def __init__(self, **data):
        super().__init__(**data)
        self.name = self.name.lower()


class ToolWrapper:
    def __init__(self, tool: BaseTool, format_input: Callable, format_output: Callable):
        self.tool = tool
        self.format_input = format_input
        self.format_output = format_output


class ToolRegistry:
    def __init__(self):
        self._registry = {}

    def register_tool(self, tool_name: str, create_func: Callable):
        self._registry[tool_name] = create_func

    def create_tool(self, tool_name: str, config: Dict[str, Any]) -> ToolWrapper:
        if tool_name not in self._registry:
            raise ValueError(f"Tool {tool_name} is not supported.")
        # LINEAJE: enforce() `config` at agent->system security_decision — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:f1d23665eec048b7fa208365156b6f43ac41ae3a5b68b839c462ca82be88873b'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:f1d23665eec048b7fa208365156b6f43ac41ae3a5b68b839c462ca82be88873b', phase='security_decision', boundary={'source': 'agent_message', 'sink': 'agent_message'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='system', project='lineaje-openclaw', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/llm_tools/entity.py', 'line': 36, 'function': 'ToolRegistry.create_tool'}})
        try:
            config = _gr_client.enforce(_gr_site, config, content_type='application/json', variable_name='config', source_file=__file__, before_line=36)
        except _gr_client.GuardrailUnavailableError:
            pass
        return self._registry[tool_name](config)
