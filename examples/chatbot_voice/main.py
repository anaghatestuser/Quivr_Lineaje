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
import os
import chainlit as cl
from quivr_core import Brain
from quivr_core.rag.entities.config import RetrievalConfig
from openai import AsyncOpenAI
from chainlit.element import Element

from io import BytesIO


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
        # LINEAJE: enforce() `files` at api->agent post_tool — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:c7a56fd40d406abdd5b61c6c2c04d05e91174b49fa8129f3d6eecdf36163b972'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:c7a56fd40d406abdd5b61c6c2c04d05e91174b49fa8129f3d6eecdf36163b972', phase='post_tool', boundary={'source': 'external_endpoint', 'sink': 'agent_message'}, fail_mode='ALLOW_WITH_AUDIT', source_type='api', destination_type='agent', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/chatbot_voice/main.py', 'line': 18, 'function': 'on_chat_start'}, 'file': 'examples/chatbot_voice/main.py', 'line': 18, 'function': 'on_chat_start', 'agent_name': 'on_chat_start', 'agent_name_source': 'inferred_from_function', 'not_on_graph': True})
        try:
            files = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, files, content_type='application/json', variable_name='files', source_file=__file__, before_line=18))
        except _gr_client.GuardrailUnavailableError:
            pass

    file = files[0]

    msg = cl.Message(content=f"Processing `{file.name}`...")
    try:
        _lineaje_obs = _lineaje_load_gr_client()
        _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:52280b0f611dee50ca42179bd727f7e3b7632e9b1f34afc50f9c5a28f5872559', phase='', boundary={}, fail_mode='ALLOW', source_type='agent', destination_type='user_interface', project='tree', organization='', components={'file': 'examples/chatbot_voice/main.py', 'line': 28, 'function': 'on_chat_start', 'agent_name': 'on_chat_start', 'agent_name_source': 'inferred_from_function', 'call_target': 'msg.send', 'not_on_graph': True}, observe_only=True)
        await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_ui'}, content_type='application/json'))
    except Exception:
        pass
    await msg.send()

    with open(file.path, "r", encoding="utf-8") as f:
        text = f.read()
        # LINEAJE: enforce() `text` at file_storage->agent file_upload — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:5dcb48adf715bd1cb5edf530b217e9d36dc184b1c16c01cf47b3ad3cf826b551'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:5dcb48adf715bd1cb5edf530b217e9d36dc184b1c16c01cf47b3ad3cf826b551', phase='file_upload', boundary={'source': 'file_upload', 'sink': 'agent_context'}, fail_mode='BLOCK', source_type='file_storage', destination_type='agent', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/chatbot_voice/main.py', 'line': 31, 'function': 'on_chat_start'}, 'file': 'examples/chatbot_voice/main.py', 'line': 31, 'function': 'on_chat_start', 'agent_name': 'on_chat_start', 'agent_name_source': 'inferred_from_function', 'not_on_graph': True})
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
        _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:8496b2d5bed0d5874cc85f6fd51abdf11e632ad38fec9ff46c0130d229fee747', phase='', boundary={}, fail_mode='ALLOW', source_type='agent', destination_type='user_interface', project='tree', organization='', components={'file': 'examples/chatbot_voice/main.py', 'line': 47, 'function': 'on_chat_start', 'agent_name': 'on_chat_start', 'agent_name_source': 'inferred_from_function', 'call_target': 'msg.update', 'not_on_graph': True}, observe_only=True)
        await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_ui'}, content_type='application/json'))
    except Exception:
        pass
    await msg.update()

    cl.user_session.set("brain", brain)


@cl.on_message
async def main(message: cl.Message):

    # LINEAJE: enforce() `message` at user_interface->agent post_agent_receive — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:2ee5f0eea1010041ec0225031139dc2b951acfd734a4e6a1f42756155e3d76d8'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:2ee5f0eea1010041ec0225031139dc2b951acfd734a4e6a1f42756155e3d76d8', phase='post_agent_receive', boundary={'source': 'user_interface', 'sink': 'agent_message'}, fail_mode='BLOCK', source_type='user_interface', destination_type='agent', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo', 'version': 'main'}, 'destination': {'entity_type': 'aimodel', 'name': 'Whisper', 'purl': 'pkg:aimodel/Whisper@1', 'version': '1'}}, 'invocation': {'file': 'examples/chatbot_voice/main.py', 'function': 'main', 'line': 53}, 'destination': {'entity_type': 'llm', 'name': 'whisper-1', 'provider': 'openai', 'version': ''}, 'file': 'examples/chatbot_voice/main.py', 'line': 55, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function', 'boundary_id': 'bnd:77da2f797c1b826c'})
    try:
        message = _gr_client.enforce(_gr_site, message, content_type='application/json', variable_name='message', source_file=__file__, before_line=55)
    except _gr_client.GuardrailUnavailableError:
        pass
    try:
        _lineaje_obs = _lineaje_load_gr_client()
        _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:cddc7efd43b077742283fb6dcc6f3777630bb8866394ddb459ddd1d6bf5f2be3', phase='', boundary={}, fail_mode='ALLOW', source_type='user_interface', destination_type='agent', project='tree', organization='', components={'file': 'examples/chatbot_voice/main.py', 'line': 55, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function', 'call_target': 'cl.TaskList', 'not_on_graph': True}, observe_only=True)
        await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'ui_to_agent'}, content_type='application/json'))
    except Exception:
        pass
    task_list = cl.TaskList(name="State")
    task_list.status = "Running..."

    think = cl.Task(title="Thinking", status=cl.TaskStatus.RUNNING)
    await task_list.add_task(think)

    tts = cl.Task(title="Text to speech")
    await task_list.add_task(tts)

    await task_list.send()

    brain = cl.user_session.get("brain")  # type: Brain
    path_config = "basic_rag_workflow.yaml"
    retrieval_config = RetrievalConfig.from_yaml(path_config)

    if brain is None:
        try:
            _lineaje_obs = _lineaje_load_gr_client()
            _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:b4f505a126ee0cf2f2c2f5f56312299141d6a2edb5b92aa51b8733866bfbb20b', phase='', boundary={}, fail_mode='ALLOW', source_type='agent', destination_type='user_interface', project='tree', organization='', components={'file': 'examples/chatbot_voice/main.py', 'line': 71, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function', 'call_target': "cl.Message(content='Please upload a file first.').send", 'not_on_graph': True}, observe_only=True)
            await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_ui'}, content_type='application/json'))
        except Exception:
            pass
        await cl.Message(content="Please upload a file first.").send()
        return

    # Prepare the message for streaming
    msg = cl.Message(content="", elements=[], author="Quivr", type="assistant_message")
    try:
        _lineaje_obs = _lineaje_load_gr_client()
        _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:6481b68de00ecf8bae2d1047a16b0c0ca4714f82398ae101bedbe8412c5f5d59', phase='', boundary={}, fail_mode='ALLOW', source_type='agent', destination_type='user_interface', project='tree', organization='', components={'file': 'examples/chatbot_voice/main.py', 'line': 76, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function', 'call_target': 'msg.send', 'not_on_graph': True}, observe_only=True)
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
            _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:8af1c52358e052248969cd7ee2a06d6b62dca542e6b92d31825aca3930c1eae6', phase='', boundary={}, fail_mode='ALLOW', source_type='agent', destination_type='user_interface', project='tree', organization='', components={'file': 'examples/chatbot_voice/main.py', 'line': 84, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function', 'call_target': 'msg.stream_token', 'not_on_graph': True}, observe_only=True)
            await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_ui'}, content_type='application/json'))
        except Exception:
            pass
        _lineaje_payload = chunk.answer
        # LINEAJE: enforce() `_lineaje_payload` at agent->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:4e8a8dba98ed9ecc8d6793fce785e9ec0adca53737e579e949a35fe20f0c4f4f'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:4e8a8dba98ed9ecc8d6793fce785e9ec0adca53737e579e949a35fe20f0c4f4f', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, fail_mode='BLOCK', source_type='agent', destination_type='user_interface', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/chatbot_voice/main.py', 'line': 84, 'function': 'main'}, 'file': 'examples/chatbot_voice/main.py', 'line': 84, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function', 'not_on_graph': True})
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
                # LINEAJE: enforce() `source` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:22f161ed56d256f46ba6b12c58f23d6595554b68757ad08ea3edb162e5c592eb'
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:22f161ed56d256f46ba6b12c58f23d6595554b68757ad08ea3edb162e5c592eb', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, fail_mode='BLOCK', source_type='agent', destination_type='log', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/chatbot_voice/main.py', 'line': 89, 'function': 'main'}, 'file': 'examples/chatbot_voice/main.py', 'line': 89, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function', 'not_on_graph': True})
                try:
                    source = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, source, content_type='application/json'))
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    pass
                print(source)
                _lineaje_content = source.page_content
                # LINEAJE: enforce() `_lineaje_content` at agent->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:48d5f4d6f0d4ae4562d2349c86b66daec93f1a9320211091d26e25d699941cf0'
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:48d5f4d6f0d4ae4562d2349c86b66daec93f1a9320211091d26e25d699941cf0', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, fail_mode='BLOCK', source_type='agent', destination_type='user_interface', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/chatbot_voice/main.py', 'line': 90, 'function': 'main'}, 'file': 'examples/chatbot_voice/main.py', 'line': 90, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function', 'not_on_graph': True})
                try:
                    _lineaje_content = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_content, content_type='text/plain'))
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    pass
                elements.append(cl.Text(name=source.metadata["original_file_name"], content=_lineaje_content, display="side"))
    
    think.status = cl.TaskStatus.DONE
    tts.status = cl.TaskStatus.RUNNING
    await task_list.update()
    
    audio_file = await text_to_speech(msg.content)
    # LINEAJE: enforce() `audio_file` at agent->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:cee5da66cbc65c1fe8cf556ca4ee1333e5838cc0b90efb93b3f3cd571c828f75'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:cee5da66cbc65c1fe8cf556ca4ee1333e5838cc0b90efb93b3f3cd571c828f75', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, fail_mode='BLOCK', source_type='agent', destination_type='user_interface', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/chatbot_voice/main.py', 'line': 97, 'function': 'main'}, 'file': 'examples/chatbot_voice/main.py', 'line': 97, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function', 'not_on_graph': True})
    try:
        audio_file = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, audio_file, content_type='text/plain'))
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    elements.append(cl.Audio(content=audio_file, auto_play=True, mime="audio/mpeg"))

    sources = ""
    for source in saved_sources_complete:
        sources += f"- {source.metadata['original_file_name']}\n"
    msg.elements = elements
    msg.content = msg.content + f"\n\nSources:\n{sources}"
    try:
        _lineaje_obs = _lineaje_load_gr_client()
        _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:833c5289f9126dbe7dc55fac0d4845d44ad5d549dd0327fcd16eba4963f57e6e', phase='', boundary={}, fail_mode='ALLOW', source_type='agent', destination_type='user_interface', project='tree', organization='', components={'file': 'examples/chatbot_voice/main.py', 'line': 104, 'function': 'main', 'agent_name': 'main', 'agent_name_source': 'inferred_from_function', 'call_target': 'msg.update', 'not_on_graph': True}, observe_only=True)
        await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_ui'}, content_type='application/json'))
    except Exception:
        pass
    await msg.update()

    tts.status = cl.TaskStatus.DONE
    task_list.status = "Done"
    await task_list.update()
    await cl.sleep(1)
    await task_list.remove()

async_openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

@cl.step(type="tool", name="Speech to text")
async def speech_to_text(audio_file):
    try:
        _lineaje_obs = _lineaje_load_gr_client()
        _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:bb03ffc6e114833c0026d46159936c3c2e0cce678472a394bb9c8ee1e2b9baa5', phase='', boundary={}, fail_mode='ALLOW', source_type='agent', destination_type='llm', project='tree', organization='', components={'file': 'examples/chatbot_voice/main.py', 'line': 116, 'function': 'speech_to_text', 'agent_name': 'speech_to_text', 'agent_name_source': 'inferred_from_function', 'call_target': 'async_openai_client.audio.transcriptions.create', 'model': 'whisper-1', 'not_on_graph': True}, observe_only=True)
        await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_llm'}, content_type='application/json'))
    except Exception:
        pass
    response = await async_openai_client.audio.transcriptions.create(
        model="whisper-1", file=audio_file
    )

    return response.text

@cl.step(type="tool", name="Text to speech")
async def text_to_speech(text):
    try:
        _lineaje_obs = _lineaje_load_gr_client()
        _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:92f4f29e24a538efb1e05a3f857de83e44b9f27d5bc2d2d8b3a5398f29fea446', phase='', boundary={}, fail_mode='ALLOW', source_type='agent', destination_type='llm', project='tree', organization='', components={'file': 'examples/chatbot_voice/main.py', 'line': 124, 'function': 'text_to_speech', 'agent_name': 'text_to_speech', 'agent_name_source': 'inferred_from_function', 'call_target': 'async_openai_client.audio.speech.create', 'model': 'tts-1', 'not_on_graph': True}, observe_only=True)
        await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_llm'}, content_type='application/json'))
    except Exception:
        pass
    response = await async_openai_client.audio.speech.create(
        model="tts-1", voice="alloy", input=text
    )

    return response.content


@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.AudioChunk):
    if chunk.isStart:
        buffer = BytesIO()
        # This is required for whisper to recognize the file type
        buffer.name = f"input_audio.{chunk.mimeType.split('/')[1]}"
        # Initialize the session for a new audio stream
        cl.user_session.set("audio_buffer", buffer)
        cl.user_session.set("audio_mime_type", chunk.mimeType)

    # Write the chunks to a buffer and transcribe the whole audio at the end
    cl.user_session.get("audio_buffer").write(chunk.data)


@cl.on_audio_end
async def on_audio_end(elements: list[Element]):
    # Get the audio buffer from the session
    task_list = cl.TaskList(name="State")
    task_list.status = "Running..."

    stt = cl.Task(title="Speech to text", status=cl.TaskStatus.RUNNING)
    await task_list.add_task(stt)

    await task_list.send()

    audio_buffer: BytesIO = cl.user_session.get("audio_buffer")
    audio_buffer.seek(0)  # Move the file pointer to the beginning
    audio_file = audio_buffer.read()
    audio_mime_type: str = cl.user_session.get("audio_mime_type")

    # LINEAJE: enforce() `audio_file` at agent->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:2805003565327a138a7c08f472b57293d7f69f58a5ad50827a44127dd508043d'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:2805003565327a138a7c08f472b57293d7f69f58a5ad50827a44127dd508043d', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, fail_mode='BLOCK', source_type='agent', destination_type='user_interface', project='tree', organization='', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/chatbot_voice/main.py', 'line': 161, 'function': 'on_audio_end'}, 'file': 'examples/chatbot_voice/main.py', 'line': 161, 'function': 'on_audio_end', 'agent_name': 'on_audio_end', 'agent_name_source': 'inferred_from_function', 'not_on_graph': True})
    try:
        audio_file = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, audio_file, content_type='text/plain'))
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    input_audio_el = cl.Audio(
        mime=audio_mime_type, content=audio_file, name=audio_buffer.name
    )
    try:
        _lineaje_obs = _lineaje_load_gr_client()
        _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:9c4e4ee3002e065f7d70fb3350c2f21ef30906185696fb711bbf3674284a2e42', phase='', boundary={}, fail_mode='ALLOW', source_type='agent', destination_type='user_interface', project='tree', organization='', components={'file': 'examples/chatbot_voice/main.py', 'line': 164, 'function': 'on_audio_end', 'agent_name': 'on_audio_end', 'agent_name_source': 'inferred_from_function', 'call_target': "cl.Message(author='You', type='user_message', content='', elements=[input_audio_", 'not_on_graph': True}, observe_only=True)
        await __import__('asyncio').to_thread(lambda: _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_ui'}, content_type='application/json'))
    except Exception:
        pass
    await cl.Message(
        author="You",
        type="user_message",
        content="",
        elements=[input_audio_el, *elements],
    ).send()

    whisper_input = (audio_buffer.name, audio_file, audio_mime_type)
    transcription = await speech_to_text(whisper_input)

    msg = cl.Message(author="You", content=transcription, elements=elements)

    stt.status = cl.TaskStatus.DONE
    task_list.status = "Done"
    await task_list.update()
    await cl.sleep(1)
    await task_list.remove()

    await main(message=msg)