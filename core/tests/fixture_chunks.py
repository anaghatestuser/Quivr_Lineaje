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

import asyncio
import json
from uuid import uuid4

from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.vectorstores import InMemoryVectorStore
from quivr_core.rag.entities.chat import ChatHistory
from quivr_core.rag.entities.config import LLMEndpointConfig, RetrievalConfig
from quivr_core.llm import LLMEndpoint
from quivr_core.rag.quivr_rag_langgraph import QuivrQARAGLangGraph


async def main():
    retrieval_config = RetrievalConfig(llm_config=LLMEndpointConfig(model="gpt-4o"))
    embedder = DeterministicFakeEmbedding(size=20)
    vec = InMemoryVectorStore(embedder)

    llm = LLMEndpoint.from_config(retrieval_config.llm_config)
    chat_history = ChatHistory(uuid4(), uuid4())
    rag_pipeline = QuivrQARAGLangGraph(
        retrieval_config=retrieval_config, llm=llm, vector_store=vec
    )

    conversational_qa_chain = rag_pipeline.build_chain()

    with open("response.jsonl", "w") as f:
        async for event in conversational_qa_chain.astream_events(
            {
                "messages": [
                    ("user", "What is NLP, give a very long detailed answer"),
                ],
                "chat_history": chat_history,
                "custom_personality": None,
            },
            version="v1",
            config={"metadata": {}},
        ):
            kind = event["event"]
            if (
                kind == "on_chat_model_stream"
                and event["metadata"]["langgraph_node"] == "generate"
            ):
                chunk = event["data"]["chunk"]
                dict_chunk = {
                    k: v.dict() if isinstance(v, AIMessageChunk) else v
                    for k, v in chunk.items()
                }
                _lineaje_payload = json.dumps(dict_chunk) + "\n"
                # LINEAJE: enforce() `_lineaje_payload` at agent->file file_write — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:de997cd092d4d3543335e98229a95ffaf0441595010daf94afc117afb619de27'
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:de997cd092d4d3543335e98229a95ffaf0441595010daf94afc117afb619de27', phase='file_write', boundary={'source': 'agent_message', 'sink': 'file_content'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='file', project='lineaje-openclaw', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/tests/fixture_chunks.py', 'line': 49, 'function': 'main'}})
                try:
                    _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json', variable_name='_lineaje_payload', source_file=__file__, before_line=49))
                except _gr_client.GuardrailUnavailableError:
                    pass
                # LINEAJ_lineaje_payloadagent->external data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:74c615d8f50f11db02e552e8cdb4fdf7541b2e714e96522f89fa962feaf9e5bb'
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:74c615d8f50f11db02e552e8cdb4fdf7541b2e714e96522f89fa962feaf9e5bb', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'external_endpoint'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='external', project='lineaje-openclaw', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/tests/fixture_chunks.py', 'line': 49, 'function': 'main'}})
                try:
                    dict_chunk = _gr_client.enforce(_gr_site, dict_chunk, content_type='application/json', variable_name='dict_chunk', source_file=__file__, before_line=49)
                except _gr_client.GuardrailUnavailableError:
                    pass
                f.write(json.dumps(dict_chunk) + "\n")


asyncio.run(main())
