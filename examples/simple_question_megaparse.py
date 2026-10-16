import os

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from quivr_core import Brain
from quivr_core.llm.llm_endpoint import LLMEndpoint
from quivr_core.rag.entities.config import LLMEndpointConfig
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

if __name__ == "__main__":
    try:
        _gr_client_m27a5a199 = (lambda _s, _n: _s.modules.get(_n) or (lambda _u, _h: (lambda _sp: (lambda _m: [_s.modules.__setitem__(_n, _m), _sp.loader.exec_module(_m), _m][2])(_u.module_from_spec(_sp)))(_u.spec_from_file_location(_n, next((_d / 'gr_stub_client.py' for _d in [_h, *_h.parents][:8] if (_d / 'gr_stub_client.py').is_file()), _h / 'gr_stub_client.py'))))(__import__('importlib.util').util, __import__('pathlib').Path(globals().get('__file__') or '.').resolve().parent))(__import__('sys'), '_lineaje_gr_stub_client')
    except Exception:
        __import__('sys').modules.pop('_lineaje_gr_stub_client', None)
        _gr_client_m27a5a199 = type('_lineaje_gr_unavailable', (), {'STUB_API': 999999, 'GuardrailUnavailableError': type('GuardrailUnavailableError', (PermissionError,), {}), 'SiteDescriptor': staticmethod(lambda *a, **k: None), 'new_interaction_id': staticmethod(lambda *a, **k: None), 'enforce': staticmethod(lambda _s, _p, *a, **k: _p), 'enforce_request': staticmethod(lambda _s, _p, *a, **k: _p), 'enforce_reply': staticmethod(lambda _s, _p, *a, **k: _p)})
    try:
        _lineaje_obs_m27a5a199 = _gr_client_m27a5a199
        _lineaje_obs_site_m27a5a199 = _lineaje_obs_m27a5a199.SiteDescriptor(site_id='site:sha256:fbcabb39e8d465e109e441766b91116f7ecd188eea4df907ffe196ab4e60d3fc', phase='', boundary={}, fail_mode='ALLOW', source_type='agent', destination_type='llm', project='tree', organization='', components={'file': 'examples/simple_question_megaparse.py', 'line': 17, 'call_target': 'os.getenv', 'source': {'entity_type': 'agent', 'file_path': 'examples/simple_question_megaparse.py', 'line': 3, 'name': 'ChatOpenAI', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB'}, 'destination': {'entity_type': 'llm', 'name': 'gpt-4o', 'provider': 'openai', 'version': ''}, 'identity': {'app': {'name': 'quivr_lineaje', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo', 'version': 'main'}, 'destination': {'entity_type': 'aimodel', 'name': 'GPT', 'purl': 'pkg:aimodel/GPT@4o', 'version': '4o'}, 'source': {'entity_type': 'aiagent', 'name': 'ChatOpenAI', 'purl': 'pkg:aiagent/ChatOpenAI@1.0.0', 'version': '1.0.0'}}, 'invocation': {'file': 'examples/simple_question_megaparse.py', 'function': '', 'line': 17}, 'boundary_id': 'bnd:77c3ff7a9cf91a92'}, observe_only=True)
        _lineaje_obs_m27a5a199.enforce(_lineaje_obs_site_m27a5a199, {'activity': 'agent_to_llm'}, content_type='application/json')
    except Exception:
        pass
    __import__('builtins').list(map(globals().pop, ('_gr_client_m27a5a199', '_lineaje_obs_m27a5a199', '_lineaje_obs_site_m27a5a199'), (None,) * 3))
    brain = Brain.from_files(
        name="test_brain",
        file_paths=["./tests/processor/pdf/sample.pdf"],
        llm=LLMEndpoint(
            llm_config=LLMEndpointConfig(model="gpt-4o"),
            llm=ChatOpenAI(model="gpt-4o", api_key=str(os.getenv("OPENAI_API_KEY"))),
        ),
    )
    embedder = embeddings = OpenAIEmbeddings(
        model="text-embedding-3-large",
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
            _gr_client_m27a5a199 = (lambda _s, _n: _s.modules.get(_n) or (lambda _u, _h: (lambda _sp: (lambda _m: [_s.modules.__setitem__(_n, _m), _sp.loader.exec_module(_m), _m][2])(_u.module_from_spec(_sp)))(_u.spec_from_file_location(_n, next((_d / 'gr_stub_client.py' for _d in [_h, *_h.parents][:8] if (_d / 'gr_stub_client.py').is_file()), _h / 'gr_stub_client.py'))))(__import__('importlib.util').util, __import__('pathlib').Path(globals().get('__file__') or '.').resolve().parent))(__import__('sys'), '_lineaje_gr_stub_client')
        except Exception:
            __import__('sys').modules.pop('_lineaje_gr_stub_client', None)
            _gr_client_m27a5a199 = type('_lineaje_gr_unavailable', (), {'STUB_API': 999999, 'GuardrailUnavailableError': type('GuardrailUnavailableError', (PermissionError,), {}), 'SiteDescriptor': staticmethod(lambda *a, **k: None), 'new_interaction_id': staticmethod(lambda *a, **k: None), 'enforce': staticmethod(lambda _s, _p, *a, **k: _p), 'enforce_request': staticmethod(lambda _s, _p, *a, **k: _p), 'enforce_reply': staticmethod(lambda _s, _p, *a, **k: _p)})
        # LINEAJE: enforce() `answer` at llm->agent post_model — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:08b3e4d955d5cb3a09a6a15af04107c7ed37a3cead5b6bc99a6f6a08f60db151'
        _gr_site_m27a5a199 = _gr_client_m27a5a199.SiteDescriptor(site_id='site:sha256:08b3e4d955d5cb3a09a6a15af04107c7ed37a3cead5b6bc99a6f6a08f60db151', phase='post_model', boundary={'source': 'model', 'sink': 'agent_message'}, fail_mode='BLOCK', source_type='llm', destination_type='agent', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'file_path': 'examples/simple_question_megaparse.py', 'line': 3, 'name': 'ChatOpenAI', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB'}, 'destination': {'entity_type': 'llm', 'name': 'gpt-4o', 'provider': 'openai', 'version': ''}, 'identity': {'app': {'name': 'quivr_lineaje', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo', 'version': 'main'}, 'destination': {'entity_type': 'aimodel', 'name': 'GPT', 'purl': 'pkg:aimodel/GPT@4o', 'version': '4o'}, 'source': {'entity_type': 'aiagent', 'name': 'ChatOpenAI', 'purl': 'pkg:aiagent/ChatOpenAI@1.0.0', 'version': '1.0.0'}}, 'invocation': {'file': 'examples/simple_question_megaparse.py', 'function': '', 'line': 38}, 'file': 'examples/simple_question_megaparse.py', 'line': 38, 'boundary_id': 'bnd:77c3ff7a9cf91a92'}, interaction_id=locals().get('_lineaje_interaction_id_m27a5a199'))
        try:
            answer = _gr_client_m27a5a199.enforce(_gr_site_m27a5a199, answer, content_type='application/json', variable_name='answer', source_file=globals().get('__file__', ''), before_line=38)
        except _gr_client_m27a5a199.GuardrailUnavailableError:
            pass
        __import__('builtins').list(map(globals().pop, ('_gr_client_m27a5a199', '_gr_site_m27a5a199', '_lineaje_interaction_id_m27a5a199'), (None,) * 3))
        # Print the answer with typing effect
        console.print(f"[bold green]Quivr Assistant[/bold green]: {answer.answer}")

        console.print("-" * console.width)

    brain.print_info()
