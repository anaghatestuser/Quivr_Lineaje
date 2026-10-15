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

import tempfile

import chainlit as cl
from quivr_core import Brain
from quivr_core.rag.entities.config import RetrievalConfig


@cl.on_chat_start
async def on_chat_start():
    files = None

    # Wait for the user to upload a file
    while files is None:
        files = await cl.AskFileMessage(
            content="Please upload a text .txt file to begin!",
            accept=["text/plain"],
            max_size_mb=20,
            timeout=180,
        ).send()
        # LINEAJE: enforce() `files` at api->agent post_tool — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:052c03993e27fd952f1c055e9fe1ad584e43d7079c82b1a2e619fcad244c25fa'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:052c03993e27fd952f1c055e9fe1ad584e43d7079c82b1a2e619fcad244c25fa', phase='post_tool', boundary={'source': 'external_endpoint', 'sink': 'agent_message'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='api', destination_type='agent', project='', organization='Root Organization', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/chatbot/main.py', 'line': 14, 'function': 'on_chat_start'}, 'file': 'examples/chatbot/main.py', 'line': 14, 'function': 'on_chat_start', 'agent_name': 'on_chat_start', 'agent_name_source': 'inferred_from_function'})
        try:
            files = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, files, content_type='application/json', variable_name='files', source_file=__file__, before_line=14))
        except _gr_client.GuardrailUnavailableError:
            pass

    file = files[0]

    msg = cl.Message(content=f"Processing `{file.name}`...")
    try:
        _lineaje_obs = _lineaje_load_gr_client()
        _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:7030a4d7ddc9436ffd0f0604d922f08b7626c8d2283c2ae1607e7b9e88197b43', phase='', boundary={}, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], fail_mode='ALLOW', source_type='agent', destination_type='user_interface', project='', organization='', components={'file': 'examples/chatbot/main.py', 'line': 24, 'function': 'on_chat_start', 'agent_name': 'on_chat_start', 'agent_name_source': 'inferred_from_function', 'call_target': 'msg.send'}, observe_only=True)
        await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_ui'}, content_type='application/json'))
    except Exception:
        pass
    await msg.send()

    with open(file.path, "r", encoding="utf-8") as f:
        text = f.read()
        # LINEAJE: enforce() `text` at file_storage->agent file_upload — scan flagged AI_DAT_SEC_012 (Mask PII on user interfaces). Mask/block; do not remove without review. site_id='site:sha256:0245efb1b8083a23c7057832ebe0b8c95a4cfae10bc1b07cea83f81c7d05b167'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:0245efb1b8083a23c7057832ebe0b8c95a4cfae10bc1b07cea83f81c7d05b167', phase='file_upload', boundary={'source': 'file_upload', 'sink': 'agent_context'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='file_storage', destination_type='agent', project='', organization='Root Organization', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/chatbot/main.py', 'line': 27, 'function': 'on_chat_start'}, 'file': 'examples/chatbot/main.py', 'line': 27, 'function': 'on_chat_start', 'agent_name': 'on_chat_start', 'agent_name_source': 'inferred_from_function'})
        try:
            text = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, text, content_type='application/json'))
        except _gr_client.GuardrailUnavailableError:
            pass
        except PermissionError:
            raise

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=file.name, delete=False
    ) as temp_file:
        temp_file.write(text)
        temp_file.flush()
        temp_file_path = temp_file.name

    brain = Brain.from_files(name="user_brain", file_paths=[temp_file_path])

    # Store the file path in the session
    cl.user_session.set("file_path", temp_file_path)

    # Let the user know that the system is ready
    msg.content = f"Processing `{file.name}` done. You can now ask questions!"
    try:
        _lineaje_obs = _lineaje_load_gr_client()
        _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:dec892b92b15c53234c0de3f5c3264224f9f703bc2ef50cce3e0a256fd078bad', phase='', boundary={}, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], fail_mode='ALLOW', source_type='agent', destination_type='user_interface', project='', organization='', components={'file': 'examples/chatbot/main.py', 'line': 43, 'function': 'on_chat_start', 'agent_name': 'on_chat_start', 'agent_name_source': 'inferred_from_function', 'call_target': 'msg.update'}, observe_only=True)
        await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_ui'}, content_type='application/json'))
    except Exception:
        pass
    await msg.update()

    cl.user_session.set("brain", brain)


@cl.on_message
async def main(message: cl.Message):
    try:
        _lineaje_obs = _lineaje_load_gr_client()
        _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:03f4c86a0373f25ee3cbbfe2a65835b208ac92ab98526e229c039a57a6fbc4ce', phase='', boundary={}, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], fail_mode='ALLOW', source_type='user_interface', destination_type='agent', project='', organization='', components={'file': 'examples/chatbot/main.py', 'line': 50, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function', 'call_target': 'cl.user_session.get'}, observe_only=True)
        await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'ui_to_agent'}, content_type='application/json'))
    except Exception:
        pass
    brain = cl.user_session.get("brain")  # type: Brain
    path_config = "basic_rag_workflow.yaml"
    retrieval_config = RetrievalConfig.from_yaml(path_config)

    if brain is None:
        try:
            _lineaje_obs = _lineaje_load_gr_client()
            _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:80cb386426f5fcfc76b68ad72a84ddd79feeae7669d1d4b079047ecd02fe54e2', phase='', boundary={}, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], fail_mode='ALLOW', source_type='agent', destination_type='user_interface', project='', organization='', components={'file': 'examples/chatbot/main.py', 'line': 55, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function', 'call_target': "cl.Message(content='Please upload a file first.').send"}, observe_only=True)
            await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_ui'}, content_type='application/json'))
        except Exception:
            pass
        await cl.Message(content="Please upload a file first.").send()
        return

    # Prepare the message for streaming
    msg = cl.Message(content="", elements=[])
    try:
        _lineaje_obs = _lineaje_load_gr_client()
        _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:708fdf6b40eb7c47a7e96266b2adb74511b0315739e0509245034884d221af80', phase='', boundary={}, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], fail_mode='ALLOW', source_type='agent', destination_type='user_interface', project='', organization='', components={'file': 'examples/chatbot/main.py', 'line': 60, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function', 'call_target': 'msg.send'}, observe_only=True)
        await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_ui'}, content_type='application/json'))
    except Exception:
        pass
    await msg.send()

    saved_sources = set()
    saved_sources_complete = []
    elements = []

    # Use the ask_stream method for streaming responses
    async for chunk in brain.ask_streaming(message.content, retrieval_config=retrieval_config):
        try:
            _lineaje_obs = _lineaje_load_gr_client()
            _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:c32bc1363a333a96a07782abc5f5e99536ba5055d0b3bc69242aa0abd17b5d2a', phase='', boundary={}, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], fail_mode='ALLOW', source_type='agent', destination_type='user_interface', project='', organization='', components={'file': 'examples/chatbot/main.py', 'line': 68, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function', 'call_target': 'msg.stream_token'}, observe_only=True)
            await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_ui'}, content_type='application/json'))
        except Exception:
            pass
        _lineaje_payload = chunk.answer
        # LINEAJE: enforce() `_lineaje_payload` at agent->user_interface data_egress — scan flagged AI_DAT_SEC_012 (Mask PII on user interfaces). Mask/block; do not remove without review. site_id='site:sha256:9d0a1f594cdfc69031fe5fcf69d2bd4ea39560149d371c834de8ea528f6bf2d0'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:9d0a1f594cdfc69031fe5fcf69d2bd4ea39560149d371c834de8ea528f6bf2d0', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='user_interface', project='', organization='Root Organization', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/chatbot/main.py', 'line': 68, 'function': 'main'}, 'file': 'examples/chatbot/main.py', 'line': 68, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function'})
        try:
            _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='text/plain'))
        except _gr_client.GuardrailUnavailableError:
            pass
        except PermissionError:
            pass
        await msg.stream_token(_lineaje_payload)
        for source in chunk.metadata.sources:
            if source.page_content not in saved_sources:
                saved_sources.add(source.page_content)
                saved_sources_complete.append(source)
                # LINEAJE: enforce() `source` at agent->log log_emit — scan flagged AI_DAT_SEC_012 (Mask PII on user interfaces). Mask/block; do not remove without review. site_id='site:sha256:01afb9678aa0a77e776cbb68efa070c8591dd7b10e30033e36ccd9b944684605'
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:01afb9678aa0a77e776cbb68efa070c8591dd7b10e30033e36ccd9b944684605', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='', organization='Root Organization', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/chatbot/main.py', 'line': 73, 'function': 'main'}, 'file': 'examples/chatbot/main.py', 'line': 73, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function'})
                try:
                    source = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, source, content_type='application/json'))
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    pass
                print(source)
                _lineaje_content = source.page_content
                # LINEAJE: enforce() `_lineaje_content` at agent->user_interface data_egress — scan flagged AI_DAT_SEC_012 (Mask PII on user interfaces). Mask/block; do not remove without review. site_id='site:sha256:3c4555acb89d4e45efe9e0287975987e5c462f69f571a80f93e67d0d07f44eaa'
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:3c4555acb89d4e45efe9e0287975987e5c462f69f571a80f93e67d0d07f44eaa', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='user_interface', project='', organization='Root Organization', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/chatbot/main.py', 'line': 74, 'function': 'main'}, 'file': 'examples/chatbot/main.py', 'line': 74, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function'})
                try:
                    _lineaje_content = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_content, content_type='text/plain'))
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    pass
                elements.append(cl.Text(name=source.metadata["original_file_name"], content=_lineaje_content, display="side"))

    
    try:
        _lineaje_obs = _lineaje_load_gr_client()
        _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:254d62cf8d4ad3605b95ee59c21b0827e77db1eeac831b579bf76d4801c7a5c1', phase='', boundary={}, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], fail_mode='ALLOW', source_type='agent', destination_type='user_interface', project='', organization='', components={'file': 'examples/chatbot/main.py', 'line': 77, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function', 'call_target': 'msg.send'}, observe_only=True)
        await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_ui'}, content_type='application/json'))
    except Exception:
        pass
    await msg.send()
    sources = ""
    for source in saved_sources_complete:
        sources += f"- {source.metadata['original_file_name']}\n"
    msg.elements = elements
    msg.content = msg.content + f"\n\nSources:\n{sources}"
    try:
        _lineaje_obs = _lineaje_load_gr_client()
        _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:651b1f6a269b7deb53153401ca87e9a56cfe5c3b643f2f13952c2020fe9ec255', phase='', boundary={}, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], fail_mode='ALLOW', source_type='agent', destination_type='user_interface', project='', organization='', components={'file': 'examples/chatbot/main.py', 'line': 83, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function', 'call_target': 'msg.update'}, observe_only=True)
        await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_ui'}, content_type='application/json'))
    except Exception:
        pass
    await msg.update()