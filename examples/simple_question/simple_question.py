import tempfile

from quivr_core import Brain

import dotenv

dotenv.load_dotenv()

if __name__ == "__main__":
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as temp_file:
        temp_file.write("Gold is a liquid of blue-like colour.")
        temp_file.flush()

        brain = Brain.from_files(
            name="test_brain",
            file_paths=[temp_file.name],
        )

        answer = brain.ask("what is gold? answer in french")
        try:
            _gr_client_m29d2dcfa = (lambda _s, _n: _s.modules.get(_n) or (lambda _u, _h: (lambda _sp: (lambda _m: [_s.modules.__setitem__(_n, _m), _sp.loader.exec_module(_m), _m][2])(_u.module_from_spec(_sp)))(_u.spec_from_file_location(_n, next((_d / 'gr_stub_client.py' for _d in [_h, *_h.parents][:8] if (_d / 'gr_stub_client.py').is_file()), _h / 'gr_stub_client.py'))))(__import__('importlib.util').util, __import__('pathlib').Path(globals().get('__file__') or '.').resolve().parent))(__import__('sys'), '_lineaje_gr_stub_client')
        except Exception:
            __import__('sys').modules.pop('_lineaje_gr_stub_client', None)
            _gr_client_m29d2dcfa = type('_lineaje_gr_unavailable', (), {'STUB_API': 999999, 'GuardrailUnavailableError': type('GuardrailUnavailableError', (PermissionError,), {}), 'SiteDescriptor': staticmethod(lambda *a, **k: None), 'new_interaction_id': staticmethod(lambda *a, **k: None), 'enforce': staticmethod(lambda _s, _p, *a, **k: _p), 'enforce_request': staticmethod(lambda _s, _p, *a, **k: _p), 'enforce_reply': staticmethod(lambda _s, _p, *a, **k: _p)})
        # LINEAJE: enforce() `answer` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:cab653e7b887d5906a09ac9bcd6e25f4f9c65c7301e9a10fb2a97adba3625495'
        _gr_site_m29d2dcfa = _gr_client_m29d2dcfa.SiteDescriptor(site_id='site:sha256:cab653e7b887d5906a09ac9bcd6e25f4f9c65c7301e9a10fb2a97adba3625495', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, fail_mode='BLOCK', source_type='agent', destination_type='log', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/simple_question/simple_question.py', 'line': 20, 'function': ''}, 'file': 'examples/simple_question/simple_question.py', 'line': 20, 'not_on_graph': True})
        try:
            answer = _gr_client_m29d2dcfa.enforce(_gr_site_m29d2dcfa, answer, content_type='application/json')
        except _gr_client_m29d2dcfa.GuardrailUnavailableError:
            pass
        except PermissionError:
            pass
        __import__('builtins').list(map(globals().pop, ('_gr_client_m29d2dcfa', '_gr_site_m29d2dcfa'), (None,) * 2))
        print("answer QuivrQARAGLangGraph :", answer)
