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

from dataclasses import dataclass
from uuid import UUID

from rich.tree import Tree


@dataclass
class ChatHistoryInfo:
    nb_chats: int
    current_default_chat: UUID
    current_chat_history_length: int

    def add_to_tree(self, chats_tree: Tree):
        chats_tree.add(f"Number of Chats: [bold]{self.nb_chats}[/bold]")
        chats_tree.add(
            f"Current Default Chat: [bold magenta]{self.current_default_chat}[/bold magenta]"
        )
        chats_tree.add(
            f"Current Chat History Length: [bold]{self.current_chat_history_length}[/bold]"
        )


@dataclass
class LLMInfo:
    model: str
    llm_base_url: str
    temperature: float
    max_tokens: int
    supports_function_calling: int

    def add_to_tree(self, llm_tree: Tree):
        llm_tree.add(f"Model: [italic]{self.model}[/italic]")
        llm_tree.add(f"Base URL: [underline]{self.llm_base_url}[/underline]")
        llm_tree.add(f"Temperature: [bold]{self.temperature}[/bold]")
        llm_tree.add(f"Max Tokens: [bold]{self.max_tokens}[/bold]")
        func_call_color = "green" if self.supports_function_calling else "red"
        llm_tree.add(
            f"Supports Function Calling: [bold {func_call_color}]{self.supports_function_calling}[/bold {func_call_color}]"
        )


@dataclass
class StorageInfo:
    storage_type: str
    n_files: int

    def add_to_tree(self, files_tree: Tree):
        files_tree.add(f"Storage Type: [italic]{self.storage_type}[/italic]")
        files_tree.add(f"Number of Files: [bold]{self.n_files}[/bold]")


@dataclass
class BrainInfo:
    brain_id: UUID
    brain_name: str
    chats_info: ChatHistoryInfo
    llm_info: LLMInfo
    files_info: StorageInfo | None = None

    def to_tree(self):
        tree = Tree("📊 Brain Information")
        tree.add(f"🆔 ID: [bold cyan]{self.brain_id}[/bold cyan]")
        tree.add(f"🧠 Brain Name: [bold green]{self.brain_name}[/bold green]")

        if self.files_info:
            files_tree = tree.add("📁 Files")
            self.files_info.add_to_tree(files_tree)

        chats_tree = tree.add("💬 Chats")
        self.chats_info.add_to_tree(chats_tree)

        llm_tree = tree.add("🤖 LLM")
        self.llm_info.add_to_tree(llm_tree)
        # LINEAJE: enforce() `tree` at agent->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:a62e2789723c9834440bac4997fbedb45cd9274e87129b445cc07cb5bbe0193e'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:a62e2789723c9834440bac4997fbedb45cd9274e87129b445cc07cb5bbe0193e', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='user_interface', project='lineaje-openclaw', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/brain/info.py', 'line': 74, 'function': 'BrainInfo.to_tree'}})
        try:
            tree = _gr_client.enforce(_gr_site, tree, content_type='text/plain')
        except _gr_client.GuardrailUnavailableError:
            pass
        except PermissionError:
            pass
        return tree
