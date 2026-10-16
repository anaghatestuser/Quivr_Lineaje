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

from typing import Any

import aiofiles
from langchain_core.documents import Document

from quivr_core.files.file import QuivrFile
from quivr_core.processor.processor_base import ProcessedDocument, ProcessorBase
from quivr_core.processor.registry import FileExtension
from quivr_core.processor.splitter import SplitterConfig


def recursive_character_splitter(
    doc: Document, chunk_size: int, chunk_overlap: int
) -> list[Document]:
    assert chunk_overlap < chunk_size, "chunk_overlap is greater than chunk_size"

    if len(doc.page_content) <= chunk_size:
        return [doc]

    chunk = Document(page_content=doc.page_content[:chunk_size], metadata=doc.metadata)
    remaining = Document(
        page_content=doc.page_content[chunk_size - chunk_overlap :],
        metadata=doc.metadata,
    )

    return [chunk] + recursive_character_splitter(remaining, chunk_size, chunk_overlap)


class SimpleTxtProcessor(ProcessorBase):
    """
    SimpleTxtProcessor is a class that implements the ProcessorBase interface.
    It is used to process the files with the Simple Txt parser.
    """

    supported_extensions = [FileExtension.txt]

    def __init__(
        self, splitter_config: SplitterConfig = SplitterConfig(), **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.splitter_config = splitter_config

    @property
    def processor_metadata(self) -> dict[str, Any]:
        return {
            "processor_cls": "SimpleTxtProcessor",
            "splitter": self.splitter_config.model_dump(),
        }

    async def process_file_inner(self, file: QuivrFile) -> ProcessedDocument[str]:
        async with aiofiles.open(file.path, mode="r") as f:
            content = await f.read()
            # LINEAJE: enforce() `content` at file_storage->agent file_upload — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:41a67d7998f9c2ab7ddb567bc39160f017747014dd462f1efa8ec452a7343af9'
            _gr_client = _lineaje_load_gr_client()
            _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:41a67d7998f9c2ab7ddb567bc39160f017747014dd462f1efa8ec452a7343af9', phase='file_upload', boundary={'source': 'file_upload', 'sink': 'agent_context'}, fail_mode='BLOCK', source_type='file_storage', destination_type='agent', project='tree', organization='', project_name='anaghatestuser', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'anaghatestuser', 'version': 'main', 'purl': 'pkg:github/github-second/anaghatestuser@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/processor/implementations/simple_txt_processor.py', 'line': 52, 'function': 'SimpleTxtProcessor.process_file_inner'}, 'file': 'core/quivr_core/processor/implementations/simple_txt_processor.py', 'line': 52, 'function': 'process_file_inner', 'agent_name': 'SimpleTxtProcessor', 'agent_name_source': 'inferred_from_class', 'not_on_graph': True})
            try:
                content = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, content, content_type='application/json'))
            except _gr_client.GuardrailUnavailableError:
                pass
            except PermissionError:
                raise

        doc = Document(page_content=content)

        docs = recursive_character_splitter(
            doc, self.splitter_config.chunk_size, self.splitter_config.chunk_overlap
        )

        return ProcessedDocument(
            chunks=docs, processor_cls="SimpleTxtProcessor", processor_response=content
        )
