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

from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel
from quivr_core import Brain
from quivr_core.rag.entities.config import LLMEndpointConfig
from quivr_core.llm.llm_endpoint import LLMEndpoint
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

if __name__ == "__main__":
    brain = Brain.from_files(
        name="test_brain",
        file_paths=["tests/processor/data/dummy.pdf"],
        llm=LLMEndpoint(
            llm=FakeListChatModel(responses=["good"]),
            llm_config=LLMEndpointConfig(model="fake_model", llm_base_url="local"),
        ),
        embedder=DeterministicFakeEmbedding(size=20),
    )
    # Check brain info
    brain.print_info()

    console = Console()
    _lineaje_payload = Panel.fit("Ask your brain !", style="bold magenta")
    # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:a688ff436888322ffc60e2a431014e6f572e454c91c14900d1530bd0e4dfbc41'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:a688ff436888322ffc60e2a431014e6f572e454c91c14900d1530bd0e4dfbc41', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'examples/pdf_parsing_tika.py', 'line': 1, 'name': 'fake_model'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'fake_model', 'version': '1.0.0', 'purl': 'pkg:aiagent/fake_model@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/pdf_parsing_tika.py', 'line': 24, 'function': ''}})
    try:
        _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    console.print(_lineaje_payload)

    while True:
        # Get user input
        question = Prompt.ask("[bold cyan]Question[/bold cyan]")

        # Check if user wants to exit
        if question.lower() == "exit":
            _lineaje_payload = Panel("Goodbye!", style="bold yellow")
            # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:815a59272a5d6f688bb02d062685ac99c674c4093e4ddbac07e71257b7e19f9b'
            _gr_client = _lineaje_load_gr_client()
            _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:815a59272a5d6f688bb02d062685ac99c674c4093e4ddbac07e71257b7e19f9b', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'examples/pdf_parsing_tika.py', 'line': 1, 'name': 'fake_model'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'fake_model', 'version': '1.0.0', 'purl': 'pkg:aiagent/fake_model@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/pdf_parsing_tika.py', 'line': 32, 'function': ''}})
            try:
                _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
            except _gr_client.GuardrailUnavailableError:
                pass
            except PermissionError:
                pass
            console.print(_lineaje_payload)
            break

        answer = brain.ask(question)
        # Print the answer with typing effect
        _lineaje_payload = f"[bold green]Quivr Assistant[/bold green]: {answer.answer}"
        # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:f0aee67dc3d7ce2c1f9dcca686c8399c5e5a0980494e77df6aad2888f1ae8237'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:f0aee67dc3d7ce2c1f9dcca686c8399c5e5a0980494e77df6aad2888f1ae8237', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'examples/pdf_parsing_tika.py', 'line': 1, 'name': 'fake_model'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'fake_model', 'version': '1.0.0', 'purl': 'pkg:aiagent/fake_model@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/pdf_parsing_tika.py', 'line': 37, 'function': ''}})
        try:
            _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
        except _gr_client.GuardrailUnavailableError:
            pass
        except PermissionError:
            pass
        console.print(_lineaje_payload)

        _lineaje_payload = "-" * console.width
        # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:bdc33dffb183206e5285cd37849edd41cbd9aa4a6f272fb9511b02560a4a39d1'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:bdc33dffb183206e5285cd37849edd41cbd9aa4a6f272fb9511b02560a4a39d1', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'examples/pdf_parsing_tika.py', 'line': 1, 'name': 'fake_model'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'fake_model', 'version': '1.0.0', 'purl': 'pkg:aiagent/fake_model@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/pdf_parsing_tika.py', 'line': 39, 'function': ''}})
        try:
            _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
        except _gr_client.GuardrailUnavailableError:
            pass
        except PermissionError:
            pass
        console.print(_lineaje_payload)

    brain.print_info()
