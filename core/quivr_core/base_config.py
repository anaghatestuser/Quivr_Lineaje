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

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict
from typing import Self


class QuivrBaseConfig(BaseModel):
    """
    Base configuration class for Quivr.

    This class extends Pydantic's BaseModel and provides a foundation for
    configuration management in quivr-core.

    Attributes:
        model_config (ConfigDict): Configuration for the Pydantic model.
            It's set to forbid extra attributes, ensuring strict adherence
            to the defined schema.

    Class Methods:
        from_yaml: Create an instance of the class from a YAML file.
    """

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def from_yaml(cls, file_path: str | Path) -> Self:
        """
        Create an instance of the class from a YAML file.

        Args:
            file_path (str | Path): The path to the YAML file.

        Returns:
            QuivrBaseConfig: An instance of the class initialized with the data from the YAML file.
        """
        # Load the YAML file
        with open(file_path, "r") as stream:
            # LINEAJE: enforce() `stream` at file_storage->agent file_upload — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:80c7551551a072f8a13d828ff6f767641e97793bbc0a5ad59fcba82621de8975'
            _gr_client = _lineaje_load_gr_client()
            _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:80c7551551a072f8a13d828ff6f767641e97793bbc0a5ad59fcba82621de8975', phase='file_upload', boundary={'source': 'file_upload', 'sink': 'agent_context'}, fail_mode='BLOCK', source_type='file_storage', destination_type='agent', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/base_config.py', 'line': 39, 'function': 'QuivrBaseConfig.from_yaml'}, 'file': 'core/quivr_core/base_config.py', 'line': 39, 'function': 'from_yaml', 'agent_name': 'QuivrBaseConfig', 'agent_name_source': 'inferred_from_class', 'not_on_graph': True})
            try:
                stream = _gr_client.enforce(_gr_site, stream, content_type='application/json')
            except _gr_client.GuardrailUnavailableError:
                pass
            except PermissionError:
                raise
            config_data = yaml.safe_load(stream)

        # Instantiate the class using the YAML data
        return cls(**config_data)
