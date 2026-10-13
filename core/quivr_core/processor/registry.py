# Copyright (c) Lineaje, Inc. All rights reserved.
# gr_check() POSTs to GR_SERVICE_URL+/enforce; fail-open unless GRBlockedError.
class GRBlockedError(Exception):
    def __init__(self, policy_id, reason):
        self.policy_id, self.reason = policy_id, reason
        super().__init__("Guardrail block for policy %r: %s" % (policy_id, reason))

def gr_check(data, source_type, destination_type, tenant_id="", timeout=5.0, **context):
    import json as _j, logging as _lg, os as _os, urllib.error as _ue, urllib.request as _ur
    _log = _lg.getLogger("lineaje.gr_client")
    hop_label = source_type + "->" + destination_type
    # A genuine policy block stops later checks in the same request context only
    # (a contextvar, not process-wide) so one blocked call never breaks the next request.
    _latch = getattr(gr_check, "_latch", None)
    if _latch is None:
        import contextvars as _cv
        _latch = gr_check._latch = _cv.ContextVar("lineaje_gr_blocked", default=None)
    _prior = _latch.get()
    if _prior:
        _log.warning("gr_client[%s]: skipping POST /enforce — request already blocked (%s)", hop_label, _prior[1])
        raise GRBlockedError(_prior[0], _prior[1])
    def _blk(o):
        if isinstance(o, dict):
            return any(_blk(o.get(k)) for k in ("skill_path", "skill_file", "path", "file_path", "data", "skill_manifest_path"))
        s = str(o or "")
        b = s.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if b.endswith(".md.blocked"): return True
        try:
            if b in ("skill.md", "skills.md") and _os.path.isfile(str(o) + ".blocked"): return True
        except Exception:
            pass
        return False
    if _blk(data) or _blk(context):
        _log.warning("gr_client[%s]: quarantined skill (*.blocked) — not loaded, GR not called", hop_label)
        _latch.set(("blocked_manifest", "quarantined skill must not be read, downloaded, or loaded"))
        raise GRBlockedError("blocked_manifest", "quarantined skill must not be read, downloaded, or loaded")
    def _stub_client():
        # gr_stub_client.py (shipped next to instrumented files) loads .env, exchanges
        # the refresh token, and re-registers the site on unknown_site /
        # candidate_policies_mismatch — prefer it over the bare POST below.
        import sys as _s, importlib.util as _ilu
        from pathlib import Path as _P
        n = "_lineaje_gr_stub_client"
        if n in _s.modules: return _s.modules[n]
        if getattr(gr_check, "_no_stub_client", False): return None
        try:
            h = _P(__file__).resolve().parent
            c = next((d / "gr_stub_client.py" for d in [h, *h.parents][:8] if (d / "gr_stub_client.py").is_file()), None)
            if c is not None:
                spec = _ilu.spec_from_file_location(n, c)
                _s.modules[n] = m = _ilu.module_from_spec(spec)
                spec.loader.exec_module(m)
                if hasattr(m, "check") and hasattr(m, "SiteDescriptor"): return m
                _s.modules.pop(n, None)
        except Exception as exc:
            _s.modules.pop(n, None)
            _log.warning("gr_client[%s]: gr_stub_client.py not loadable (%s) — using inline client", hop_label, exc)
        gr_check._no_stub_client = True
        return None
    def _block(policy_id, reason):
        _log.warning("gr_client[%s]: BLOCKED by policy=%s — %s", hop_label, policy_id, reason)
        if _os.environ.get("GR_BLOCK_MODE", "enforce").lower() == "audit":
            return data
        _latch.set((policy_id, reason))
        raise GRBlockedError(policy_id, reason)
    tid = tenant_id or _os.environ.get("GR_TENANT_ID", "")
    _sc = _stub_client()
    if _sc is not None:
        try:
            _cp = [p if isinstance(p, dict) else {"policy_id": p} for p in (context.get("candidate_policies") or [])]
            _site = _sc.SiteDescriptor(site_id=context.get("site_id") or "", candidate_policies=_cp, fail_mode="BLOCK", source_type=source_type, destination_type=destination_type)
            _d = _sc.check(_site, data, tenant_id=tid, timeout=timeout)
        except Exception as exc:
            _log.warning("gr_client[%s]: GR service call failed (%s) — failing open", hop_label, exc)
            return data
        if _d.blocked and not getattr(_d, "infra_failure", False):
            _acts = _d.actions_applied or []
            _pid = (_acts[0].get("policy_id") if _acts and isinstance(_acts[0], dict) else "") or "unknown"
            return _block(_pid, _d.warning or "Request denied by policy enforcement.")
        if _d.blocked:
            _log.warning("gr_client[%s]: GR service unavailable (%s) — failing open", hop_label, _d.warning)
            return data
        return data if _d.payload is None else _d.payload
    url = _os.environ.get("GR_SERVICE_URL", "")
    if not url:
        return data
    # Refresh token first: the GR service exchanges it for the access JWT it
    # calls the Data Service policy API with; a lineaje_pat_ PAT only
    # identifies the caller and cannot be exchanged.
    bearer = _os.environ.get("GR_BEARER_TOKEN") or _os.environ.get("LINEAJE_REFRESH_TOKEN") or _os.environ.get("LINEAJE_PAT_TOKEN") or _os.environ.get("LINEAJE_PAT", "")
    params_key = "out_params" if destination_type == "agent" else "in_params"
    def _gr_js(o):
        # JSON form of non-JSON payloads (LangChain Document, pydantic models, ...).
        if hasattr(o, "page_content"):
            return {"page_content": o.page_content, "metadata": getattr(o, "metadata", None) or {}}
        for _m in ("model_dump", "dict", "to_dict"):
            _f = getattr(o, _m, None)
            if callable(_f):
                try:
                    return _f()
                except Exception:
                    pass
        if isinstance(o, (set, tuple)):
            return list(o)
        return str(o)
    def _gr_back(orig, new):
        # Map the (possibly masked) JSON back onto the caller's own objects.
        if new == _j.loads(_j.dumps(orig, default=_gr_js)):
            return orig
        if isinstance(orig, (list, tuple)) and isinstance(new, list) and len(orig) == len(new):
            _out = [_gr_back(a, b) for a, b in zip(orig, new)]
            return tuple(_out) if isinstance(orig, tuple) else _out
        if hasattr(orig, "page_content") and isinstance(new, dict) and "page_content" in new:
            import copy as _cp
            _c = _cp.copy(orig)
            _c.page_content = new["page_content"]
            if isinstance(new.get("metadata"), dict) and hasattr(_c, "metadata"):
                _c.metadata = new["metadata"]
            return _c
        if orig is None or isinstance(orig, (str, int, float, bool, dict, list)):
            return new
        _log.warning("gr_client[%s]: masked result cannot be applied to %s — returning original", hop_label, type(orig).__name__)
        return orig
    _base = url.rstrip("/")
    if _base.lower().endswith("/enforce"): _base = _base[: -len("/enforce")].rstrip("/")
    def _post(body):
        headers = {"Content-Type": "application/json"}
        if bearer:
            headers["Authorization"] = "Bearer " + bearer
        req = _ur.Request(_base + "/enforce", data=_j.dumps(body, default=_gr_js).encode(), headers=headers, method="POST")
        with _ur.urlopen(req, timeout=timeout) as resp:
            return _j.loads(resp.read())
    try:
        _sent = _j.loads(_j.dumps(data, default=_gr_js))
        body = {"source_type": source_type, "destination_type": destination_type, params_key: {"data": _sent}}
        for _k, _v in context.items():
            if _v:
                body[_k] = _v
        if tid:
            body["tenant_id"] = tid
    except Exception as exc:
        _log.warning("gr_client[%s]: payload not serializable (%s) — failing open", hop_label, exc)
        return data
    result = None
    for _attempt in (0, 1):
        try:
            result = _post(body)
            break
        except Exception as exc:
            if isinstance(exc, _ue.HTTPError) and exc.code == 403:
                try: detail = _j.loads(exc.read()).get("detail", {})
                except Exception: detail = {}
                if not isinstance(detail, dict): detail = {"message": str(detail)}
                blocked_by = detail.get("blocked_by") or []
                if blocked_by or detail.get("error") == "request_blocked":
                    _pid = (blocked_by[0].get("policy_id") if isinstance(blocked_by[0], dict) else "") if blocked_by else ""
                    return _block(_pid or "unknown", detail.get("message", "Request denied by policy enforcement."))
                if _attempt == 0 and (body.get("site_id") or body.get("candidate_policies")):
                    # unknown_site / candidate_policies_mismatch: a site-manifest
                    # problem, not a policy verdict — re-evaluate without site scoping.
                    _log.warning("gr_client[%s]: %s — retrying without site_id", hop_label, detail.get("error") or detail.get("message") or "403")
                    body = {k: v for k, v in body.items() if k not in ("site_id", "candidate_policies")}
                    continue
            _log.warning("gr_client[%s]: GR service call failed (%s) — failing open", hop_label, exc)
            return data
    if not isinstance(result, dict):
        return data
    if result.get("status") == "escalate":
        _log.warning("gr_client[%s]: escalation flagged — passing through for human review", hop_label)
    if not isinstance(result.get("result"), dict) or "data" not in result["result"]:
        return data
    return _gr_back(data, result["result"]["data"])
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
    try:
        base_processors = gr_check(base_processors, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005'], site_id='site:sha256:c13799a012e1102fe816a2c07496125e1e793ead2486793a1f4524dfe2d06f46')
    except Exception as _gr_exc:
        if type(_gr_exc).__name__ == "GRBlockedError": raise
        base_processors = base_processors
        __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
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
                try:
                    _lineaje_payload = gr_check(_lineaje_payload, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005'], site_id='site:sha256:18387faa1d5edf31015a6b098ee8b1f3d9eb81a16eddee539bf1ade4e6c0b4a6')
                except Exception as _gr_exc:
                    if type(_gr_exc).__name__ == "GRBlockedError": raise
                    _lineaje_payload = _lineaje_payload
                    __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                logger.warn(
                    f"{proc_entry.err}. Falling to the next available processor for {file_extension}"
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
                try:
                    _lineaje_payload = gr_check(_lineaje_payload, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005'], site_id='site:sha256:8286a55eeed6dfc0530746341a07cf7e240dcb8bc06f6777be50a1a58cec5394')
                except Exception as _gr_exc:
                    if type(_gr_exc).__name__ == "GRBlockedError": raise
                    _lineaje_payload = _lineaje_payload
                    __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                logger.info(f"{proc_cls} already in registry...")

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

    try:
        mod = gr_check(mod, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005'], site_id='site:sha256:04c2caec6c85eb23ffb11e4eb47f522cbcea1ad50d46747ce20878ac85103ff4')
    except Exception as _gr_exc:
        if type(_gr_exc).__name__ == "GRBlockedError": raise
        mod = mod
        __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
    return mod


def available_processors():
    """Return a list of the known processors."""
    return list(known_processors)
