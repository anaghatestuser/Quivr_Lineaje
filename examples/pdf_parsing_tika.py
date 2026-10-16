from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel
from quivr_core import Brain
from quivr_core.rag.entities.config import LLMEndpointConfig
from quivr_core.llm.llm_endpoint import LLMEndpoint
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

if __name__ == "__main__":
    try:
        _gr_client_m9e07b581 = (lambda _s, _n: _s.modules.get(_n) or (lambda _u, _h: (lambda _sp: (lambda _m: [_s.modules.__setitem__(_n, _m), _sp.loader.exec_module(_m), _m][2])(_u.module_from_spec(_sp)))(_u.spec_from_file_location(_n, next((_d / 'gr_stub_client.py' for _d in [_h, *_h.parents][:8] if (_d / 'gr_stub_client.py').is_file()), _h / 'gr_stub_client.py'))))(__import__('importlib.util').util, __import__('pathlib').Path(globals().get('__file__') or '.').resolve().parent))(__import__('sys'), '_lineaje_gr_stub_client')
    except Exception:
        __import__('sys').modules.pop('_lineaje_gr_stub_client', None)
        _gr_client_m9e07b581 = type('_lineaje_gr_unavailable', (), {'STUB_API': 999999, 'GuardrailUnavailableError': type('GuardrailUnavailableError', (PermissionError,), {}), 'SiteDescriptor': staticmethod(lambda *a, **k: None), 'new_interaction_id': staticmethod(lambda *a, **k: None), 'enforce': staticmethod(lambda _s, _p, *a, **k: _p), 'enforce_request': staticmethod(lambda _s, _p, *a, **k: _p), 'enforce_reply': staticmethod(lambda _s, _p, *a, **k: _p)})
    try:
        _lineaje_obs_m9e07b581 = _gr_client_m9e07b581
        _lineaje_obs_site_m9e07b581 = _lineaje_obs_m9e07b581.SiteDescriptor(site_id='site:sha256:6483e7ef0c2e4ba936e5b7b84955a092aec92f1619e80262b09ad40a44e0e560', phase='', boundary={}, fail_mode='ALLOW', source_type='agent', destination_type='llm', project='tree', organization='', components={'file': 'examples/pdf_parsing_tika.py', 'line': 16, 'call_target': 'LLMEndpointConfig', 'model': 'fake_model', 'source': {'entity_type': 'agent', 'file_path': 'examples/pdf_parsing_tika.py', 'line': 1, 'name': 'fake_model', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB'}, 'identity': {'app': {'name': 'quivr_lineaje', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo', 'version': 'main'}, 'destination': {'entity_type': 'aimodel', 'name': 'fake_model', 'purl': 'pkg:aimodel/fake_model@1.0.0', 'version': ''}, 'source': {'entity_type': 'aiagent', 'name': 'fake_model', 'purl': 'pkg:aiagent/fake_model@1.0.0', 'version': '1.0.0'}}, 'invocation': {'file': 'examples/pdf_parsing_tika.py', 'function': '', 'line': 16}, 'destination': {'entity_type': 'llm', 'name': 'fake_model', 'provider': '', 'version': ''}, 'boundary_id': 'bnd:3d2857ed7fc2761a'}, observe_only=True)
        _lineaje_obs_m9e07b581.enforce(_lineaje_obs_site_m9e07b581, {'activity': 'agent_to_llm'}, content_type='application/json')
    except Exception:
        pass
    __import__('builtins').list(map(globals().pop, ('_gr_client_m9e07b581', '_lineaje_obs_m9e07b581', '_lineaje_obs_site_m9e07b581'), (None,) * 3))
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
    console.print(Panel.fit("Ask your brain !", style="bold magenta"))

    while True:
        # Get user input
        question = Prompt.ask("[bold cyan]Question[/bold cyan]")

        # Check if user wants to exit
        if question.lower() == "exit":
            console.print(Panel("Goodbye!", style="bold yellow"))
            break

        answer = brain.ask(question)
        try:
            _gr_client_m9e07b581 = (lambda _s, _n: _s.modules.get(_n) or (lambda _u, _h: (lambda _sp: (lambda _m: [_s.modules.__setitem__(_n, _m), _sp.loader.exec_module(_m), _m][2])(_u.module_from_spec(_sp)))(_u.spec_from_file_location(_n, next((_d / 'gr_stub_client.py' for _d in [_h, *_h.parents][:8] if (_d / 'gr_stub_client.py').is_file()), _h / 'gr_stub_client.py'))))(__import__('importlib.util').util, __import__('pathlib').Path(globals().get('__file__') or '.').resolve().parent))(__import__('sys'), '_lineaje_gr_stub_client')
        except Exception:
            __import__('sys').modules.pop('_lineaje_gr_stub_client', None)
            _gr_client_m9e07b581 = type('_lineaje_gr_unavailable', (), {'STUB_API': 999999, 'GuardrailUnavailableError': type('GuardrailUnavailableError', (PermissionError,), {}), 'SiteDescriptor': staticmethod(lambda *a, **k: None), 'new_interaction_id': staticmethod(lambda *a, **k: None), 'enforce': staticmethod(lambda _s, _p, *a, **k: _p), 'enforce_request': staticmethod(lambda _s, _p, *a, **k: _p), 'enforce_reply': staticmethod(lambda _s, _p, *a, **k: _p)})
        # LINEAJE: enforce() `answer` at llm->agent post_model — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:a85ad656ef1d29b5e3dac617bf5ff81b479145c531a1f09b044d7d34b0c3a4c4'
        _gr_site_m9e07b581 = _gr_client_m9e07b581.SiteDescriptor(site_id='site:sha256:a85ad656ef1d29b5e3dac617bf5ff81b479145c531a1f09b044d7d34b0c3a4c4', phase='post_model', boundary={'source': 'model', 'sink': 'agent_message'}, fail_mode='BLOCK', source_type='llm', destination_type='agent', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'file_path': 'examples/pdf_parsing_tika.py', 'line': 1, 'name': 'fake_model', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB'}, 'identity': {'app': {'name': 'quivr_lineaje', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo', 'version': 'main'}, 'destination': {'entity_type': 'aimodel', 'name': 'fake_model', 'purl': 'pkg:aimodel/fake_model@1.0.0', 'version': ''}, 'source': {'entity_type': 'aiagent', 'name': 'fake_model', 'purl': 'pkg:aiagent/fake_model@1.0.0', 'version': '1.0.0'}}, 'invocation': {'file': 'examples/pdf_parsing_tika.py', 'function': '', 'line': 35}, 'destination': {'entity_type': 'llm', 'name': 'fake_model', 'provider': '', 'version': ''}, 'file': 'examples/pdf_parsing_tika.py', 'line': 35, 'boundary_id': 'bnd:3d2857ed7fc2761a'}, interaction_id=locals().get('_lineaje_interaction_id_m9e07b581'))
        try:
            answer = _gr_client_m9e07b581.enforce(_gr_site_m9e07b581, answer, content_type='application/json', variable_name='answer', source_file=globals().get('__file__', ''), before_line=35)
        except _gr_client_m9e07b581.GuardrailUnavailableError:
            pass
        __import__('builtins').list(map(globals().pop, ('_gr_client_m9e07b581', '_gr_site_m9e07b581', '_lineaje_interaction_id_m9e07b581'), (None,) * 3))
        # Print the answer with typing effect
        console.print(f"[bold green]Quivr Assistant[/bold green]: {answer.answer}")

        console.print("-" * console.width)

    brain.print_info()
