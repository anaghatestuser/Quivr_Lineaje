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

import importlib
import logging
import types
from dataclasses import dataclass, field
from heapq import heappop, heappush
from typing import List, Type, TypeAlias

from quivr_core.files.file import FileExtension

from .processor_base import ProcessorBase

logger = logging.getLogger("quivr_core")

_LOWEST_PRIORITY = 100

_registry: dict[str, Type[ProcessorBase]] = {}

# external, read only. Contains the actual processors that we are imported and ready to use
registry = types.MappingProxyType(_registry)


@dataclass(order=True)
class ProcEntry:
    priority: int
    cls_mod: str = field(compare=False)
    err: str | None = field(compare=False)


ProcMapping: TypeAlias = dict[FileExtension | str, list[ProcEntry]]

# Register based on mimetypes
base_processors: ProcMapping = {
    FileExtension.txt: [
        ProcEntry(
            cls_mod="quivr_core.processor.implementations.simple_txt_processor.SimpleTxtProcessor",
            err=None,
            priority=_LOWEST_PRIORITY,
        )
    ],
    FileExtension.pdf: [
        ProcEntry(
            cls_mod="quivr_core.processor.implementations.tika_processor.TikaProcessor",
            err=None,
            priority=_LOWEST_PRIORITY,
        )
    ],
}


def _append_proc_mapping(
    mapping: ProcMapping,
    file_exts: List[FileExtension] | List[str],
    cls_mod: str,
    errtxt: str,
    priority: int | None,
):
    for file_ext in file_exts:
        if file_ext in mapping:
            try:
                prev_proc = heappop(mapping[file_ext])
                proc_entry = ProcEntry(
                    priority=priority
                    if priority is not None
                    else prev_proc.priority - 1,
                    cls_mod=cls_mod,
                    err=errtxt,
                )
                # Push the previous processor back
                heappush(mapping[file_ext], prev_proc)
                heappush(mapping[file_ext], proc_entry)
            except IndexError:
                proc_entry = ProcEntry(
                    priority=priority if priority is not None else _LOWEST_PRIORITY,
                    cls_mod=cls_mod,
                    err=errtxt,
                )
                heappush(mapping[file_ext], proc_entry)

        else:
            proc_entry = ProcEntry(
                priority=priority if priority is not None else _LOWEST_PRIORITY,
                cls_mod=cls_mod,
                err=errtxt,
            )

            mapping[file_ext] = [proc_entry]


def defaults_to_proc_entries(
    base_processors: ProcMapping,
) -> ProcMapping:
    # TODO(@aminediro) : how can a user change the order of the processor ?
    # NOTE: order of this list is important as resolution of `get_processor_class` depends on it
    # We should have a way to automatically add these at 'import' time
    for supported_extensions, processor_name in [
        ([FileExtension.csv], "CSVProcessor"),
        ([FileExtension.txt], "TikTokenTxtProcessor"),
        ([FileExtension.docx, FileExtension.doc], "DOCXProcessor"),
        ([FileExtension.xls, FileExtension.xlsx], "XLSXProcessor"),
        ([FileExtension.pptx], "PPTProcessor"),
        (
            [FileExtension.markdown, FileExtension.md, FileExtension.mdx],
            "MarkdownProcessor",
        ),
        ([FileExtension.epub], "EpubProcessor"),
        ([FileExtension.bib], "BibTexProcessor"),
        ([FileExtension.odt], "ODTProcessor"),
        ([FileExtension.html], "HTMLProcessor"),
        ([FileExtension.py], "PythonProcessor"),
        ([FileExtension.ipynb], "NotebookProcessor"),
    ]:
        for ext in supported_extensions:
            ext_str = ext.value if isinstance(ext, FileExtension) else ext
            _append_proc_mapping(
                mapping=base_processors,
                file_exts=[ext],
                cls_mod=f"quivr_core.processor.implementations.default.{processor_name}",
                errtxt=f"can't import {processor_name}. Please install quivr-core[{ext_str}] to access {processor_name}",
                priority=None,
            )

    # TODO(@aminediro): Megaparse should register itself
    # Append Megaparse
    _append_proc_mapping(
        mapping=base_processors,
        file_exts=[
            FileExtension.txt,
            FileExtension.pdf,
            FileExtension.docx,
            FileExtension.doc,
            FileExtension.pptx,
            FileExtension.xls,
            FileExtension.xlsx,
            FileExtension.csv,
            FileExtension.epub,
            FileExtension.bib,
            FileExtension.odt,
            FileExtension.html,
            FileExtension.markdown,
            FileExtension.md,
            FileExtension.mdx,
        ],
        cls_mod="quivr_core.processor.implementations.megaparse_processor.MegaparseProcessor",
        errtxt=f"can't import MegaparseProcessor. Please install quivr-core[{ext_str}] to access MegaparseProcessor",
        priority=None,
    )
    return base_processors


known_processors = defaults_to_proc_entries(base_processors)


def get_processor_class(file_extension: FileExtension | str) -> Type[ProcessorBase]:
    """Fetch processor class from registry

    The dict ``known_processors`` maps file extensions to the locations
    of processors that could process them.
    Loading of these classes is *Lazy*. Appropriate import will happen
    the first time we try to process some file type.

    Some processors need additional dependencies. If the import fails
    we return the "err" field of the ProcEntry in  ``known_processors``.
    """

    if file_extension not in registry:
        # Either you registered it from module or it's in the known processors
        if file_extension not in known_processors:
            raise ValueError(f"Extension not known: {file_extension}")
        entries = known_processors[file_extension]
        while entries:
            proc_entry = heappop(entries)
            try:
                register_processor(file_extension, _import_class(proc_entry.cls_mod))
                break
            except ImportError:
                _lineaje_payload = f"{proc_entry.err}. Falling to the next available processor for {file_extension}"
                # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:18387faa1d5edf31015a6b098ee8b1f3d9eb81a16eddee539bf1ade4e6c0b4a6'
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:18387faa1d5edf31015a6b098ee8b1f3d9eb81a16eddee539bf1ade4e6c0b4a6', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, fail_mode='BLOCK', source_type='agent', destination_type='log', project='tree', organization='', project_name='anaghatestuser', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'anaghatestuser', 'version': 'main', 'purl': 'pkg:github/github-second/anaghatestuser@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/processor/registry.py', 'line': 176, 'function': 'get_processor_class'}, 'file': 'core/quivr_core/processor/registry.py', 'line': 176, 'function': 'get_processor_class', 'agent_name': 'get_processor_class', 'agent_name_source': 'inferred_from_function', 'not_on_graph': True})
                try:
                    _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    pass
                logger.warn(
                    _lineaje_payload
                )
        if len(entries) == 0 and file_extension not in registry:
            raise ImportError(f"can't find any processor for {file_extension}")

    cls = registry[file_extension]
    return cls


def register_processor(
    file_ext: FileExtension | str,
    proc_cls: str | Type[ProcessorBase],
    append: bool = True,
    override: bool = False,
    errtxt: str | None = None,
    priority: int | None = None,
):
    if isinstance(proc_cls, str):
        if file_ext in known_processors and append is False:
            if all(proc_cls != proc.cls_mod for proc in known_processors[file_ext]):
                raise ValueError(
                    f"Processor for ({file_ext}) already in the registry and append is False"
                )
        else:
            if all(proc_cls != proc.cls_mod for proc in known_processors[file_ext]):
                _append_proc_mapping(
                    known_processors,
                    file_exts=[file_ext],
                    cls_mod=proc_cls,
                    errtxt=errtxt
                    or f"{proc_cls} import failed for processor of {file_ext}",
                    priority=priority,
                )
            else:
                _lineaje_payload = f"{proc_cls} already in registry..."
                # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:8286a55eeed6dfc0530746341a07cf7e240dcb8bc06f6777be50a1a58cec5394'
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:8286a55eeed6dfc0530746341a07cf7e240dcb8bc06f6777be50a1a58cec5394', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, fail_mode='BLOCK', source_type='agent', destination_type='log', project='tree', organization='', project_name='anaghatestuser', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'anaghatestuser', 'version': 'main', 'purl': 'pkg:github/github-second/anaghatestuser@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/processor/registry.py', 'line': 211, 'function': 'register_processor'}, 'file': 'core/quivr_core/processor/registry.py', 'line': 211, 'function': 'register_processor', 'agent_name': 'register_processor', 'agent_name_source': 'inferred_from_function', 'not_on_graph': True})
                try:
                    _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json')
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    pass
                logger.info(_lineaje_payload)

    else:
        assert issubclass(
            proc_cls, ProcessorBase
        ), f"{proc_cls} should be a subclass of quivr_core.processor.ProcessorBase"
        if file_ext in registry and override is False:
            if _registry[file_ext] is not proc_cls:
                raise ValueError(
                    f"Processor for ({file_ext}) already in the registry and append is False"
                )
        else:
            _registry[file_ext] = proc_cls


def _import_class(full_mod_path: str):
    if ":" in full_mod_path:
        mod_name, name = full_mod_path.rsplit(":", 1)
    else:
        mod_name, name = full_mod_path.rsplit(".", 1)

    mod = importlib.import_module(mod_name)

    for cls in name.split("."):
        mod = getattr(mod, cls)

    if not isinstance(mod, type):
        raise TypeError(f"{full_mod_path} is not a class")

    if not issubclass(mod, ProcessorBase):
        raise TypeError(f"{full_mod_path} is not a subclass of ProcessorBase ")

    # LINEAJE: enforce() `mod` at agent->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:04c2caec6c85eb23ffb11e4eb47f522cbcea1ad50d46747ce20878ac85103ff4'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:04c2caec6c85eb23ffb11e4eb47f522cbcea1ad50d46747ce20878ac85103ff4', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, fail_mode='BLOCK', source_type='agent', destination_type='user_interface', project='tree', organization='', project_name='anaghatestuser', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'anaghatestuser', 'version': 'main', 'purl': 'pkg:github/github-second/anaghatestuser@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/processor/registry.py', 'line': 243, 'function': '_import_class'}, 'file': 'core/quivr_core/processor/registry.py', 'line': 243, 'function': '_import_class', 'agent_name': '_import_class', 'agent_name_source': 'inferred_from_function', 'not_on_graph': True})
    try:
        mod = _gr_client.enforce(_gr_site, mod, content_type='text/plain')
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    return mod


def available_processors():
    """Return a list of the known processors."""
    return list(known_processors)
