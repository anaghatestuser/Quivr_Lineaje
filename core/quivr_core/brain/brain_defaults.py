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

import logging

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

from quivr_core.rag.entities.config import DefaultModelSuppliers, LLMEndpointConfig
from quivr_core.llm import LLMEndpoint

logger = logging.getLogger("quivr_core")


async def build_default_vectordb(
    docs: list[Document], embedder: Embeddings
) -> VectorStore:
    try:
        from langchain_community.vectorstores import FAISS

        _lineaje_payload = "Using Faiss-CPU as vector store."
        # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:ba792bd0925958e73e6ea89d5585d9fc6bf2715b0ee284741ee705e0f40d950d'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:ba792bd0925958e73e6ea89d5585d9fc6bf2715b0ee284741ee705e0f40d950d', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'core/quivr_core/brain/brain_defaults.py', 'line': 35, 'name': 'OpenAIEmbeddings'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'OpenAIEmbeddings', 'version': '1.0.0', 'purl': 'pkg:aiagent/OpenAIEmbeddings@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/brain/brain_defaults.py', 'line': 19, 'function': 'build_default_vectordb'}})
        try:
            _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json'))
        except _gr_client.GuardrailUnavailableError:
            pass
        except PermissionError:
            pass
        logger.debug(_lineaje_payload)
        # TODO(@aminediro) : embedding call is usually not concurrent for all documents but waits
        if len(docs) > 0:
            vector_db = await FAISS.afrom_documents(documents=docs, embedding=embedder)
            return vector_db
        else:
            raise ValueError("can't initialize brain without documents")

    except ImportError as e:
        raise ImportError(
            "Please provide a valid vector store or install quivr-core['base'] package for using the default one."
        ) from e


def default_embedder() -> Embeddings:
    try:
        from langchain_openai import OpenAIEmbeddings

        _lineaje_payload = "Loaded OpenAIEmbeddings as default LLM for brain"
        # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:7bd8e5bc4c69956c57ff51b20344d0c95ca79656a45699a275bcd335b7723f93'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:7bd8e5bc4c69956c57ff51b20344d0c95ca79656a45699a275bcd335b7723f93', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'core/quivr_core/brain/brain_defaults.py', 'line': 35, 'name': 'OpenAIEmbeddings'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'OpenAIEmbeddings', 'version': '1.0.0', 'purl': 'pkg:aiagent/OpenAIEmbeddings@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/brain/brain_defaults.py', 'line': 37, 'function': 'default_embedder'}})
        try:
            _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
        except _gr_client.GuardrailUnavailableError:
            pass
        except PermissionError:
            pass
        logger.debug(_lineaje_payload)
        embedder = OpenAIEmbeddings()
        return embedder
    except ImportError as e:
        raise ImportError(
            "Please provide a valid Embedder or install quivr-core['base'] package for using the defaultone."
        ) from e


def default_llm() -> LLMEndpoint:
    try:
        _lineaje_payload = "Loaded ChatOpenAI as default LLM for brain"
        # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:fc1ca1cbca32e603d83f0e29d694b1a00b4e75224afb48363546d7a2ab13791d'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:fc1ca1cbca32e603d83f0e29d694b1a00b4e75224afb48363546d7a2ab13791d', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'core/quivr_core/brain/brain_defaults.py', 'line': 35, 'name': 'OpenAIEmbeddings'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'OpenAIEmbeddings', 'version': '1.0.0', 'purl': 'pkg:aiagent/OpenAIEmbeddings@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/brain/brain_defaults.py', 'line': 48, 'function': 'default_llm'}})
        try:
            _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
        except _gr_client.GuardrailUnavailableError:
            pass
        except PermissionError:
            pass
        logger.debug(_lineaje_payload)
        llm = LLMEndpoint.from_config(
            LLMEndpointConfig(supplier=DefaultModelSuppliers.OPENAI, model="gpt-4o")
        )
        return llm

    except ImportError as e:
        raise ImportError(
            "Please provide a valid BaseLLM or install quivr-core['base'] package"
        ) from e
