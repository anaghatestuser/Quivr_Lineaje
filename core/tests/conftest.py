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

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.runnables.utils import AddableDict
from langchain_core.vectorstores import InMemoryVectorStore
from quivr_core.rag.entities.config import LLMEndpointConfig
from quivr_core.files.file import FileExtension, QuivrFile
from quivr_core.llm import LLMEndpoint


@pytest.fixture(scope="function")
def temp_data_file(tmp_path):
    data = "This is some test data."
    temp_file = tmp_path / "data.txt"
    # LINEAJE: enforce() `data` at agent->file file_write — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:654fd716f929a3e72312ec9006e8d88d2309e129e253160f0799e738d2300de9'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:654fd716f929a3e72312ec9006e8d88d2309e129e253160f0799e738d2300de9', phase='file_write', boundary={'source': 'agent_message', 'sink': 'file_content'}, fail_mode='BLOCK', source_type='agent', destination_type='file', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/tests/conftest.py', 'line': 21, 'function': 'temp_data_file'}, 'file': 'core/tests/conftest.py', 'line': 21, 'function': 'temp_data_file', 'agent_name': 'temp_data_file', 'agent_name_source': 'inferred_from_function', 'not_on_graph': True})
    try:
        data = _gr_client.enforce(_gr_site, data, content_type='application/json', variable_name='data', source_file=__file__, before_line=21)
    except _gr_client.GuardrailUnavailableError:
        pass
    temp_file.write_text(data)
    # LINEAJE: enforce() `temp_file` at agent->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:9ccd438e42c5a91e16bcf1465b82d2a1deb52f36231a37f23e72b4c92ac43edb'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:9ccd438e42c5a91e16bcf1465b82d2a1deb52f36231a37f23e72b4c92ac43edb', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, fail_mode='BLOCK', source_type='agent', destination_type='user_interface', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/tests/conftest.py', 'line': 22, 'function': 'temp_data_file'}, 'file': 'core/tests/conftest.py', 'line': 22, 'function': 'temp_data_file', 'agent_name': 'temp_data_file', 'agent_name_source': 'inferred_from_function', 'not_on_graph': True})
    try:
        temp_file = _gr_client.enforce(_gr_site, temp_file, content_type='text/plain')
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    return temp_file


@pytest.fixture(scope="function")
def quivr_txt(temp_data_file):
    return QuivrFile(
        id=uuid4(),
        brain_id=uuid4(),
        original_filename=temp_data_file.name,
        path=temp_data_file,
        file_extension=FileExtension.txt,
        file_sha1="123",
    )


@pytest.fixture
def quivr_pdf():
    return QuivrFile(
        id=uuid4(),
        brain_id=uuid4(),
        original_filename="dummy.pdf",
        path=Path("./tests/processor/data/dummy.pdf"),
        file_extension=FileExtension.pdf,
        file_sha1="13bh234jh234",
    )


@pytest.fixture
def full_response():
    return "Natural Language Processing (NLP) is a field of artificial intelligence that focuses on the interaction between computers and humans through natural language. The ultimate objective of NLP is to enable computers to understand, interpret, and respond to human language in a way that is both valuable and meaningful. NLP combines computational linguistics—rule-based modeling of human language—with statistical, machine learning, and deep learning models. This combination allows computers to process human language in the form of text or voice data and to understand its full meaning, complete with the speaker or writer’s intent and sentiment. Key tasks in NLP include text and speech recognition, translation, sentiment analysis, and topic segmentation."


@pytest.fixture
def chunks_stream_answer():
    with open("./tests/chunk_stream_fixture.jsonl", "r") as f:
        # LINEAJE: enforce() `f` at file_storage->agent file_upload — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:8da6f955c9948828e7bd9e8a52757c69cbcdaab5103ac2c07372e6533f7223c6'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:8da6f955c9948828e7bd9e8a52757c69cbcdaab5103ac2c07372e6533f7223c6', phase='file_upload', boundary={'source': 'file_upload', 'sink': 'agent_context'}, fail_mode='BLOCK', source_type='file_storage', destination_type='agent', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/tests/conftest.py', 'line': 57, 'function': 'chunks_stream_answer'}, 'file': 'core/tests/conftest.py', 'line': 57, 'function': 'chunks_stream_answer', 'agent_name': 'chunks_stream_answer', 'agent_name_source': 'inferred_from_function', 'not_on_graph': True})
        try:
            f = _gr_client.enforce(_gr_site, f, content_type='application/json')
        except _gr_client.GuardrailUnavailableError:
            pass
        except PermissionError:
            raise
        raw_chunks = list(f)

    chunks = []
    for rc in raw_chunks:
        chunk = AddableDict(**json.loads(rc))
        if "answer" in chunk:
            chunk["answer"] = AIMessageChunk(**chunk["answer"])
            chunks.append(chunk)
    # LINEAJE: enforce() `chunks` at agent->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:0776a338adffbb4b26fe3dc32dc41889a4479ae931dfa03b55e761568f5ab674'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:0776a338adffbb4b26fe3dc32dc41889a4479ae931dfa03b55e761568f5ab674', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, fail_mode='BLOCK', source_type='agent', destination_type='user_interface', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/tests/conftest.py', 'line': 65, 'function': 'chunks_stream_answer'}, 'file': 'core/tests/conftest.py', 'line': 65, 'function': 'chunks_stream_answer', 'agent_name': 'chunks_stream_answer', 'agent_name_source': 'inferred_from_function', 'not_on_graph': True})
    try:
        chunks = _gr_client.enforce(_gr_site, chunks, content_type='text/plain')
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    return chunks


@pytest.fixture(autouse=True)
def openai_api_key():
    os.environ["OPENAI_API_KEY"] = "this-is-a-test-key"


@pytest.fixture
def answers():
    return [f"answer_{i}" for i in range(10)]


@pytest.fixture(scope="function")
def fake_llm(answers: list[str]):
    llm = FakeListChatModel(responses=answers)
    return LLMEndpoint(llm=llm, llm_config=LLMEndpointConfig(model="fake_model"))


@pytest.fixture(scope="function")
def embedder():
    return DeterministicFakeEmbedding(size=20)


@pytest.fixture(scope="function")
def mem_vector_store(embedder):
    return InMemoryVectorStore(embedder)
