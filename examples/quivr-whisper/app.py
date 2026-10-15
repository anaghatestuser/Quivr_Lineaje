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

from flask import Flask, render_template, request, jsonify, session
import openai
import base64
import os
import requests
from dotenv import load_dotenv
from quivr_core import Brain
from quivr_core.rag.entities.config import RetrievalConfig
from tempfile import NamedTemporaryFile
from werkzeug.utils import secure_filename
from asyncio import to_thread
import asyncio


UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"txt"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = "secret"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["CACHE_TYPE"] = "SimpleCache"  # In-memory cache for development
app.config["CACHE_DEFAULT_TIMEOUT"] = 60 * 60  # 1 hour cache timeout
load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

brains = {}


@app.route("/")
def index():
    _lineaje_payload = "index.html"
    # LINEAJE: enforce() `_lineaje_payload` at html->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:0850b8d863ad4c83c1a483276137f13d3a73f16f9387e37e5c68ee52ae0e73fd'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:0850b8d863ad4c83c1a483276137f13d3a73f16f9387e37e5c68ee52ae0e73fd', phase='data_egress', boundary={'source': 'html', 'sink': 'user_interface'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='html', destination_type='user_interface', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 34, 'function': 'index'}, 'file': 'examples/quivr-whisper/app.py', 'line': 34, 'function': 'index', 'agent_name': 'index', 'agent_name_source': 'inferred_from_function'})
    try:
        _lineaje_payload = _gr_client.enforce(_gr_site, _lineaje_payload, content_type='text/html')
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    return render_template(_lineaje_payload)


def run_in_event_loop(func, *args, **kwargs):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    if asyncio.iscoroutinefunction(func):
        result = loop.run_until_complete(func(*args, **kwargs))
    else:
        result = func(*args, **kwargs)
    loop.close()
    # LINEAJE: enforce() `result` at agent->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:ffcbc0cc7116dfd3069669ce4b02abc06e13efebed2eef28bb263a3fa6709777'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:ffcbc0cc7116dfd3069669ce4b02abc06e13efebed2eef28bb263a3fa6709777', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='user_interface', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 45, 'function': 'run_in_event_loop'}, 'file': 'examples/quivr-whisper/app.py', 'line': 45, 'function': 'run_in_event_loop', 'agent_name': 'run_in_event_loop', 'agent_name_source': 'inferred_from_function'})
    try:
        result = _gr_client.enforce(_gr_site, result, content_type='text/plain')
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    return result


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/upload", methods=["POST"])
async def upload_file():
    if "file" not in request.files:
        return "No file part", 400

    file = request.files["file"]
    # LINEAJE: enforce() `file` at file_storage->agent file_upload — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:0a17d6cd796119b95a99601548610ba8bec94739b74fe1f859b0f47c66d0ceb2'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:0a17d6cd796119b95a99601548610ba8bec94739b74fe1f859b0f47c66d0ceb2', phase='file_upload', boundary={'source': 'file_upload', 'sink': 'agent_context'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='file_storage', destination_type='agent', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 57, 'function': 'upload_file'}, 'file': 'examples/quivr-whisper/app.py', 'line': 57, 'function': 'upload_file', 'agent_name': 'upload_file', 'agent_name_source': 'inferred_from_function'})
    try:
        file = _gr_client.enforce(_gr_site, file, content_type='application/json')
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        raise

    if file.filename == "":
        return "No selected file", 400
    if not (file and file.filename and allowed_file(file.filename)):
        return "Invalid file type", 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    _lineaje_payload = f"File uploaded and saved at: {filepath}"
    # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:e4b5b8f0a47e56169b0697dc231075350ebd17cad0545da6936da16622911761'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:e4b5b8f0a47e56169b0697dc231075350ebd17cad0545da6936da16622911761', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 68, 'function': 'upload_file'}, 'file': 'examples/quivr-whisper/app.py', 'line': 68, 'function': 'upload_file', 'agent_name': 'upload_file', 'agent_name_source': 'inferred_from_function'})
    try:
        _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json'))
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    print(_lineaje_payload)

    _lineaje_payload = "Creating brain instance..."
    # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:f93c73f830a174be772f85b2a54888b9e815ecd2a79a79c6cb89d0e6052b3ebd'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:f93c73f830a174be772f85b2a54888b9e815ecd2a79a79c6cb89d0e6052b3ebd', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 70, 'function': 'upload_file'}, 'file': 'examples/quivr-whisper/app.py', 'line': 70, 'function': 'upload_file', 'agent_name': 'upload_file', 'agent_name_source': 'inferred_from_function'})
    try:
        _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json'))
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    print(_lineaje_payload)

    brain: Brain = await to_thread(
        run_in_event_loop, Brain.from_files, name="user_brain", file_paths=[filepath]
    )

    # Store brain instance in cache
    session_id = session.sid if hasattr(session, "sid") else os.urandom(16).hex()
    session["session_id"] = session_id
    # cache.set(session_id, brain)  # Store the brain instance in the cache
    brains[session_id] = brain
    _lineaje_payload = f"Brain instance created and stored in cache for session ID: {session_id}"
    # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:1b14b7829a142ce941d1098f5d4fc53ab8795e231140002bd8fdbbf0fe4ad7af'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:1b14b7829a142ce941d1098f5d4fc53ab8795e231140002bd8fdbbf0fe4ad7af', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 81, 'function': 'upload_file'}, 'file': 'examples/quivr-whisper/app.py', 'line': 81, 'function': 'upload_file', 'agent_name': 'upload_file', 'agent_name_source': 'inferred_from_function'})
    try:
        _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json'))
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    print(_lineaje_payload)

    _lineaje_payload = {"message": "Brain created successfully"}
    # LINEAJE: enforce() `_lineaje_payload` at agent->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:7467efaf379c851ac52761b8eb98d9f5f8f584782411e28625360ea59f1917ad'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:7467efaf379c851ac52761b8eb98d9f5f8f584782411e28625360ea59f1917ad', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='user_interface', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 83, 'function': 'upload_file'}, 'file': 'examples/quivr-whisper/app.py', 'line': 83, 'function': 'upload_file', 'agent_name': 'upload_file', 'agent_name_source': 'inferred_from_function'})
    try:
        _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='text/plain'))
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    return jsonify(_lineaje_payload)


@app.route("/ask", methods=["POST"])
async def ask():
    if "audio_data" not in request.files:
        return "Missing audio data", 400

    # Retrieve the brain instance from the cache using the session ID
    session_id = session.get("session_id")
    if not session_id:
        return "Session ID not found. Upload a file first.", 400

    brain = brains.get(session_id)
    if not brain:
        return "Brain instance not found in dict. Upload a file first.", 400

    _lineaje_payload = "Brain instance loaded from cache."
    # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:b1aee21cc2efac7fc74cc55597f50d8d174d0e8505c2b41d8cc4fe69dfa928a6'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:b1aee21cc2efac7fc74cc55597f50d8d174d0e8505c2b41d8cc4fe69dfa928a6', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 100, 'function': 'ask'}, 'file': 'examples/quivr-whisper/app.py', 'line': 100, 'function': 'ask', 'agent_name': 'ask', 'agent_name_source': 'inferred_from_function'})
    try:
        _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json'))
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    print(_lineaje_payload)

    _lineaje_payload = "Speech to text..."
    # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:12357767cdadecd417245d788b24511aa36108c23208adccb6c96ccfb26e64f5'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:12357767cdadecd417245d788b24511aa36108c23208adccb6c96ccfb26e64f5', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 102, 'function': 'ask'}, 'file': 'examples/quivr-whisper/app.py', 'line': 102, 'function': 'ask', 'agent_name': 'ask', 'agent_name_source': 'inferred_from_function'})
    try:
        _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json'))
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    print(_lineaje_payload)
    audio_file = request.files["audio_data"]
    # LINEAJE: enforce() `audio_file` at file_storage->agent file_upload — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:899f0f8beb72bf6e7b112c38471dce25d6d9e29f0fe4d1fbff7ef01c5bfd1380'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:899f0f8beb72bf6e7b112c38471dce25d6d9e29f0fe4d1fbff7ef01c5bfd1380', phase='file_upload', boundary={'source': 'file_upload', 'sink': 'agent_context'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='file_storage', destination_type='agent', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 103, 'function': 'ask'}, 'file': 'examples/quivr-whisper/app.py', 'line': 103, 'function': 'ask', 'agent_name': 'ask', 'agent_name_source': 'inferred_from_function'})
    try:
        audio_file = _gr_client.enforce(_gr_site, audio_file, content_type='application/json')
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        raise
    transcript = transcribe_audio_file(audio_file)
    # LINEAJE: enforce() `transcript` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:0bc844c8c9eb7ab37fbb033fd4081b7b023e6e40321ca4a8a8f54ef1c1dac237'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:0bc844c8c9eb7ab37fbb033fd4081b7b023e6e40321ca4a8a8f54ef1c1dac237', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 105, 'function': 'ask'}, 'file': 'examples/quivr-whisper/app.py', 'line': 105, 'function': 'ask', 'agent_name': 'ask', 'agent_name_source': 'inferred_from_function'})
    try:
        transcript = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, transcript, content_type='application/json'))
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    print("Transcript result: ", transcript)

    _lineaje_payload = "Getting response..."
    # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:3f268ec6ce42fa6f0a5c56bd56f70f4f575536b79b493e0df57a5b734b6f2122'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:3f268ec6ce42fa6f0a5c56bd56f70f4f575536b79b493e0df57a5b734b6f2122', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 107, 'function': 'ask'}, 'file': 'examples/quivr-whisper/app.py', 'line': 107, 'function': 'ask', 'agent_name': 'ask', 'agent_name_source': 'inferred_from_function'})
    try:
        _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json'))
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    print(_lineaje_payload)
    quivr_response = await to_thread(run_in_event_loop, brain.ask, transcript)

    _lineaje_payload = "Text to speech..."
    # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:baf5d2bdd2057943b5c5b47f52b4af787dc2cecdb58cc3bab6ee73e2cfa26770'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:baf5d2bdd2057943b5c5b47f52b4af787dc2cecdb58cc3bab6ee73e2cfa26770', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 110, 'function': 'ask'}, 'file': 'examples/quivr-whisper/app.py', 'line': 110, 'function': 'ask', 'agent_name': 'ask', 'agent_name_source': 'inferred_from_function'})
    try:
        _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json'))
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    print(_lineaje_payload)
    audio_base64 = synthesize_speech(quivr_response.answer)

    _lineaje_payload = "Done"
    # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:e6d9f67066c351c6fccd2b2c093f0069f0d3a458c1e68c7b7f8c92ead77a07c4'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:e6d9f67066c351c6fccd2b2c093f0069f0d3a458c1e68c7b7f8c92ead77a07c4', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 113, 'function': 'ask'}, 'file': 'examples/quivr-whisper/app.py', 'line': 113, 'function': 'ask', 'agent_name': 'ask', 'agent_name_source': 'inferred_from_function'})
    try:
        _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json'))
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    print(_lineaje_payload)
    _lineaje_payload = {"audio_base64": audio_base64}
    # LINEAJE: enforce() `_lineaje_payload` at agent->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:7932e7672624b6773cbd554abfaa28c9f30f7ab524f0c4b0151979e652e8525e'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:7932e7672624b6773cbd554abfaa28c9f30f7ab524f0c4b0151979e652e8525e', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='user_interface', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 114, 'function': 'ask'}, 'file': 'examples/quivr-whisper/app.py', 'line': 114, 'function': 'ask', 'agent_name': 'ask', 'agent_name_source': 'inferred_from_function'})
    try:
        _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='text/plain'))
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    return jsonify(_lineaje_payload)


def transcribe_audio_file(audio_file):
    with NamedTemporaryFile(suffix=".webm", delete=False) as temp_audio_file:
        audio_file.save(temp_audio_file)
        temp_audio_file_path = temp_audio_file.name

    try:
        with open(temp_audio_file_path, "rb") as f:
            # LINEAJE: enforce() `f` at file_storage->agent file_upload — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:1f253705eef340fab908bb337534b3fb3b800686762f5ec2e1e2644a8d7e752c'
            _gr_client = _lineaje_load_gr_client()
            _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:1f253705eef340fab908bb337534b3fb3b800686762f5ec2e1e2644a8d7e752c', phase='file_upload', boundary={'source': 'file_upload', 'sink': 'agent_context'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='file_storage', destination_type='agent', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 124, 'function': 'transcribe_audio_file'}, 'file': 'examples/quivr-whisper/app.py', 'line': 124, 'function': 'transcribe_audio_file', 'agent_name': 'transcribe_audio_file', 'agent_name_source': 'inferred_from_function'})
            try:
                f = _gr_client.enforce(_gr_site, f, content_type='application/json')
            except _gr_client.GuardrailUnavailableError:
                pass
            except PermissionError:
                raise
            try:
                _lineaje_obs = _lineaje_load_gr_client()
                _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:34b874bb28d35fe8bbd740e342592571f074abfc93a8ce9038a34552e7d090f1', phase='', boundary={}, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], fail_mode='ALLOW', source_type='agent', destination_type='llm', project='lineaje-openclaw', organization='', components={'file': 'examples/quivr-whisper/app.py', 'line': 124, 'function': 'transcribe_audio_file', 'agent_name': 'transcribe_audio_file', 'agent_name_source': 'inferred_from_function', 'call_target': 'openai.audio.transcriptions.create', 'model': 'whisper-1'}, observe_only=True)
                _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_llm'}, content_type='application/json')
            except Exception:
                pass
            transcript_response = openai.audio.transcriptions.create(
                model="whisper-1", file=f
            )
        transcript = transcript_response.text
    finally:
        # LINEAJE: enforce() `temp_audio_file_path` at agent->system security_decision — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:0d83b71901cb8fa94db9955de9d711bd8f6cc102c4e0cc055fe2e4c7796575d2'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:0d83b71901cb8fa94db9955de9d711bd8f6cc102c4e0cc055fe2e4c7796575d2', phase='security_decision', boundary={'source': 'agent_message', 'sink': 'agent_message'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='system', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 129, 'function': 'transcribe_audio_file'}, 'file': 'examples/quivr-whisper/app.py', 'line': 129, 'function': 'transcribe_audio_file', 'agent_name': 'transcribe_audio_file', 'agent_name_source': 'inferred_from_function'})
        try:
            temp_audio_file_path = _gr_client.enforce(_gr_site, temp_audio_file_path, content_type='application/json', variable_name='temp_audio_file_path', source_file=__file__, before_line=129)
        except _gr_client.GuardrailUnavailableError:
            pass
        os.unlink(temp_audio_file_path)

    # LINEAJE: enforce() `transcript` at agent->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:45d3f7815a6db56c52bfb948a2a4b8b25a763e9f475f49d8e92bd33bc52600b6'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:45d3f7815a6db56c52bfb948a2a4b8b25a763e9f475f49d8e92bd33bc52600b6', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='user_interface', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 131, 'function': 'transcribe_audio_file'}, 'file': 'examples/quivr-whisper/app.py', 'line': 131, 'function': 'transcribe_audio_file', 'agent_name': 'transcribe_audio_file', 'agent_name_source': 'inferred_from_function'})
    try:
        transcript = _gr_client.enforce(_gr_site, transcript, content_type='text/plain')
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    return transcript


def synthesize_speech(text):
    try:
        _lineaje_obs = _lineaje_load_gr_client()
        _lineaje_obs_site = _lineaje_obs.SiteDescriptor(site_id='site:sha256:c3782ad0ada39ba4505e489e902492271c1350629e3cb87506e7a373421176ac', phase='', boundary={}, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], fail_mode='ALLOW', source_type='agent', destination_type='llm', project='lineaje-openclaw', organization='', components={'file': 'examples/quivr-whisper/app.py', 'line': 135, 'function': 'synthesize_speech', 'agent_name': 'synthesize_speech', 'agent_name_source': 'inferred_from_function', 'call_target': 'openai.audio.speech.create', 'model': 'tts-1'}, observe_only=True)
        _lineaje_obs.enforce(_lineaje_obs_site, {'activity': 'agent_to_llm'}, content_type='application/json')
    except Exception:
        pass
    speech_response = openai.audio.speech.create(
        model="tts-1", voice="nova", input=text
    )
    audio_content = speech_response.content
    # LINEAJE: enforce() `audio_content` at llm->agent post_model — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:d151e4dec8781b7e44ba87e5d785df70851e5c3ea9447e43ea30412b4bc684ba'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:d151e4dec8781b7e44ba87e5d785df70851e5c3ea9447e43ea30412b4bc684ba', phase='post_model', boundary={'source': 'model', 'sink': 'agent_message'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='llm', destination_type='agent', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'destination': {'entity_type': 'llm', 'name': 'whisper-1', 'version': '', 'provider': 'openai'}, 'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'Whisper', 'version': '1', 'purl': 'pkg:aimodel/Whisper@1'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 138, 'function': 'synthesize_speech'}, 'file': 'examples/quivr-whisper/app.py', 'line': 138, 'function': 'synthesize_speech', 'agent_name': 'synthesize_speech', 'agent_name_source': 'inferred_from_function'}, interaction_id=locals().get('_lineaje_interaction_id'))
    try:
        audio_content = _gr_client.enforce(_gr_site, audio_content, content_type='application/json', variable_name='audio_content', source_file=__file__, before_line=138)
    except _gr_client.GuardrailUnavailableError:
        pass
    audio_base64 = base64.b64encode(audio_content).decode("utf-8")
    # LINEAJE: enforce() `audio_base64` at agent->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:a9c6367d4a467e0baab232b2cad6d3af14b1edb1e01b63fe4f12c646492c79a2'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:a9c6367d4a467e0baab232b2cad6d3af14b1edb1e01b63fe4f12c646492c79a2', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='user_interface', project='lineaje-openclaw', organization='LOGMOD', project_name='quivr_lineaje', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/quivr-whisper/app.py', 'line': 140, 'function': 'synthesize_speech'}, 'file': 'examples/quivr-whisper/app.py', 'line': 140, 'function': 'synthesize_speech', 'agent_name': 'synthesize_speech', 'agent_name_source': 'inferred_from_function'})
    try:
        audio_base64 = _gr_client.enforce(_gr_site, audio_base64, content_type='text/plain')
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    return audio_base64


if __name__ == "__main__":
    app.run(debug=True)
