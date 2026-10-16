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
    _obs = bool(context.get("observe_only"))  # a log-only call never enforces, so a block neither skips nor sets it
    _prior = None if _obs else _latch.get()
    if _prior:
        _log.warning("gr_client[%s]: skipping POST /enforce — request already blocked (%s)", hop_label, _prior[1])
        try:  # still tell the Guardrail the activity happened (no data, no policy)
            import sys as _s
            _m = _s.modules.get("_lineaje_gr_stub_client")
            if _m is not None and hasattr(_m, "_report_skipped_after_block"):
                _f = getattr(_m.SiteDescriptor, "__dataclass_fields__", {})
                _m._report_skipped_after_block(_m.SiteDescriptor(site_id=context.get("site_id") or "", source_type=source_type, destination_type=destination_type, **{k: context[k] for k in ("components", "interaction_id") if context.get(k) and k in _f}), tenant_id or _os.environ.get("GR_TENANT_ID", ""))
        except Exception:
            pass
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
        if not _obs: _latch.set((policy_id, reason))
        raise GRBlockedError(policy_id, reason)
    tid = tenant_id or _os.environ.get("GR_TENANT_ID", "")
    _sc = _stub_client()
    if _sc is not None:
        try:
            _cp = [p if isinstance(p, dict) else {"policy_id": p} for p in (context.get("candidate_policies") or [])]
            _kw = {k: context[k] for k in ("components", "interaction_id", "observe_only") if context.get(k) and k in getattr(_sc.SiteDescriptor, "__dataclass_fields__", {})}
            _site = _sc.SiteDescriptor(site_id=context.get("site_id") or "", candidate_policies=_cp, fail_mode="BLOCK", source_type=source_type, destination_type=destination_type, **_kw)
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
import asyncio
import datetime
import logging
from collections import OrderedDict
from typing import (
    Annotated,
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypedDict,
)
from uuid import UUID, uuid4

import openai
from langchain.retrievers import ContextualCompressionRetriever
from langchain_cohere import CohereRerank
from langchain_community.document_compressors import JinaRerank
from langchain_core.callbacks import Callbacks
from langchain_core.documents import BaseDocumentCompressor, Document
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.prompts.base import BasePromptTemplate
from langchain_core.runnables.schema import StreamEvent
from langchain_core.vectorstores import VectorStore
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Send
from pydantic import BaseModel, Field

from quivr_core.llm import LLMEndpoint
from quivr_core.llm_tools.llm_tools import LLMToolFactory
from quivr_core.rag.entities.chat import ChatHistory
from quivr_core.rag.entities.config import DefaultRerankers, NodeConfig, RetrievalConfig
from quivr_core.rag.entities.models import (
    LangchainMetadata,
    ParsedRAGChunkResponse,
    QuivrKnowledge,
    RAGResponseMetadata,
)
from quivr_core.rag.prompts import TemplatePromptName, custom_prompts
from quivr_core.rag.utils import (
    LangfuseService,
    collect_tools,
    combine_documents,
    format_dict,
    format_file_list,
    get_chunk_metadata,
    parse_chunk_response,
)

logger = logging.getLogger("quivr_core")

langfuse_service = LangfuseService()
langfuse_handler = langfuse_service.get_handler()


class SplittedInput(BaseModel):
    instructions_reasoning: Optional[str] = Field(
        default=None,
        description="The reasoning that leads to identifying the user instructions to the system",
    )
    instructions: Optional[str] = Field(
        default=None, description="The instructions to the system"
    )

    tasks_reasoning: Optional[str] = Field(
        default=None,
        description="The reasoning that leads to identifying the explicit or implicit user tasks and questions",
    )
    task_list: Optional[List[str]] = Field(
        default_factory=lambda: ["No explicit or implicit tasks found"],
        description="The list of standalone, self-contained tasks or questions.",
    )


class TasksCompletion(BaseModel):
    is_task_completable_reasoning: Optional[str] = Field(
        default=None,
        description="The reasoning that leads to identifying whether the user task or question can be completed using the provided context and chat history BEFORE any tool is used.",
    )

    is_task_completable: bool = Field(
        description="Whether the user task or question can be completed using the provided context and chat history BEFORE any tool is used.",
    )

    tool_reasoning: Optional[str] = Field(
        default=None,
        description="The reasoning that leads to identifying the tool that shall be used to complete the task.",
    )
    tool: Optional[str] = Field(
        description="The tool that shall be used to complete the task.",
    )


class FinalAnswer(BaseModel):
    reasoning_answer: str = Field(
        description="The step-by-step reasoning that led to the final answer"
    )
    answer: str = Field(description="The final answer to the user tasks/questions")

    all_tasks_completed: bool = Field(
        description="Whether all tasks/questions have been successfully answered/completed or not. "
        " If the final answer to the user is 'I don't know' or 'I don't have enough information' or 'I'm not sure', "
        " this variable should be 'false'"
    )


class UpdatedPromptAndTools(BaseModel):
    prompt_reasoning: Optional[str] = Field(
        default=None,
        description="The step-by-step reasoning that leads to the updated system prompt",
    )
    prompt: Optional[str] = Field(default=None, description="The updated system prompt")

    tools_reasoning: Optional[str] = Field(
        default=None,
        description="The reasoning that leads to activating and deactivating the tools",
    )
    tools_to_activate: Optional[List[str]] = Field(
        default_factory=list, description="The list of tools to activate"
    )
    tools_to_deactivate: Optional[List[str]] = Field(
        default_factory=list, description="The list of tools to deactivate"
    )


class UserTaskEntity(BaseModel):
    id: UUID
    definition: str
    docs: List[Document] = Field(default_factory=list)
    completable: bool = Field(
        default=False, description="Whether the task has been completed or not"
    )
    tool: Optional[str] = Field(
        default=None, description="The tool that shall be used to complete the task"
    )

    def has_tool(self) -> bool:
        return bool(self.tool)

    def is_completable(self) -> bool:
        return self.completable


class UserTasks:
    def __init__(self, task_definitions: List[str] | None = None):
        self.user_tasks = {}
        if task_definitions:
            for definition in task_definitions:
                id = uuid4()
                self.user_tasks[id] = UserTaskEntity(
                    id=id, definition=definition, docs=[]
                )

    def __iter__(self):
        return iter(self.user_tasks.values())

    def set_docs(self, id: UUID, docs: List[Document]):
        if self.user_tasks:
            if id in self.user_tasks:
                self.user_tasks[id].docs = docs
            else:
                raise ValueError(f"Task with id {id} not found")

    def set_definition(self, id: UUID, definition: str):
        if self.user_tasks:
            if id in self.user_tasks:
                self.user_tasks[id].definition = definition
            else:
                raise ValueError(f"Task with id {id} not found")

    def set_completion(self, id: UUID, completable: bool):
        if self.user_tasks:
            if id in self.user_tasks:
                self.user_tasks[id].completable = completable
            else:
                raise ValueError(f"Task with id {id} not found")

    def set_tool(self, id: UUID, tool: str):
        if self.user_tasks:
            if id in self.user_tasks:
                self.user_tasks[id].tool = tool
            else:
                raise ValueError(f"Task with id {id} not found")

    def __call__(self, id: UUID) -> UserTaskEntity:
        return self.user_tasks[id]

    def has_tasks(self) -> bool:
        return bool(self.user_tasks)

    def has_non_completable_tasks(self) -> bool:
        return bool(self.non_completable_tasks)

    @property
    def non_completable_tasks(self) -> List[UserTaskEntity]:
        return [task for task in self.user_tasks.values() if not task.is_completable()]

    @property
    def completable_tasks(self) -> List[UserTaskEntity]:
        return [task for task in self.user_tasks.values() if task.is_completable()]

    @property
    def ids(self) -> List[UUID]:
        return list(self.user_tasks.keys())

    @property
    def definitions(self) -> List[str]:
        return [task.definition for task in self.user_tasks.values()]

    @property
    def docs(self) -> List[Document]:
        # Return the concatenation of all docs
        return [doc for task in self.user_tasks.values() for doc in task.docs]


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    reasoning: List[str]
    chat_history: ChatHistory
    files: str
    tasks: UserTasks
    instructions: str
    ticket_metadata: Optional[dict[str, str]]
    user_metadata: Optional[dict[str, str]]
    additional_information: Optional[dict[str, str]]
    tool: str
    guidelines: str
    enforced_system_prompt: str
    _filter: Optional[Dict[str, Any]]
    ticket_history: str


class IdempotentCompressor(BaseDocumentCompressor):
    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Optional[Callbacks] = None,
    ) -> Sequence[Document]:
        """
        A no-op document compressor that simply returns the documents it is given.

        This is a placeholder until a more sophisticated document compression
        algorithm is implemented.
        """
        try:
            documents = gr_check(documents, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:58dba1272b49cd57d0b75c28159382429c9783c3c5f11e9400f0832aced37ebd', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 253, 'function': 'IdempotentCompressor.compress_documents'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 253, 'function': 'compress_documents', 'agent_name': 'IdempotentCompressor', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            documents = documents
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
        return documents


class QuivrQARAGLangGraph:
    def __init__(
        self,
        *,
        retrieval_config: RetrievalConfig,
        llm: LLMEndpoint,
        vector_store: VectorStore | None = None,
    ):
        """
        Construct a QuivrQARAGLangGraph object.

        Args:
            retrieval_config (RetrievalConfig): The configuration for the RAG model.
            llm (LLMEndpoint): The LLM to use for generating text.
            vector_store (VectorStore): The vector store to use for storing and retrieving documents.
            reranker (BaseDocumentCompressor | None): The document compressor to use for re-ranking documents. Defaults to IdempotentCompressor if not provided.
        """
        self.retrieval_config = retrieval_config
        self.vector_store = vector_store
        self.llm_endpoint = llm

        self.graph = None

    def get_reranker(self, **kwargs):
        # Extract the reranker configuration from self
        config = self.retrieval_config.reranker_config

        # Allow kwargs to override specific config values
        supplier = kwargs.pop("supplier", config.supplier)
        model = kwargs.pop("model", config.model)
        top_n = kwargs.pop("top_n", config.top_n)
        api_key = kwargs.pop("api_key", config.api_key)

        if supplier == DefaultRerankers.COHERE:
            reranker = CohereRerank(
                model=model, top_n=top_n, cohere_api_key=api_key, **kwargs
            )
        elif supplier == DefaultRerankers.JINA:
            reranker = JinaRerank(
                model=model, top_n=top_n, jina_api_key=api_key, **kwargs
            )
        else:
            reranker = IdempotentCompressor()

        return reranker

    def get_retriever(self, **kwargs):
        """
        Returns a retriever that can retrieve documents from the vector store.

        Returns:
            VectorStoreRetriever: The retriever.
        """
        if self.vector_store:
            retriever = self.vector_store.as_retriever(**kwargs)
        else:
            raise ValueError("No vector store provided")

        return retriever

    def routing(self, state: AgentState) -> List[Send]:
        """
        The routing function for the RAG model.

        Args:
            state (AgentState): The current state of the agent.

        Returns:
            dict: The next state of the agent.
        """

        msg = custom_prompts[TemplatePromptName.SPLIT_PROMPT].format(
            user_input=state["messages"][0].content,
        )

        response: SplittedInput

        try:
            structured_llm = self.llm_endpoint._llm.with_structured_output(
                SplittedInput, method="json_schema"
            )
            response = structured_llm.invoke(msg)

        except openai.BadRequestError:
            structured_llm = self.llm_endpoint._llm.with_structured_output(
                SplittedInput
            )
            _lineaje_interaction_id = __import__("uuid").uuid4().hex
            try:
                msg = gr_check(msg, "agent", "llm", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_070', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:0d4a8228f9b53d8c3d8bea4f7b07979d3311ebca3acf97b7ab801f8508502c0b', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'destination': {'entity_type': 'llm', 'name': 'openai', 'version': '', 'provider': ''}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'openai', 'version': '', 'purl': 'pkg:aimodel/openai@1.0.0'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 343, 'function': 'QuivrQARAGLangGraph.routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 343, 'function': 'routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'structured_llm.invoke'}, interaction_id=_lineaje_interaction_id)
            except Exception as _gr_exc:
                if type(_gr_exc).__name__ == "GRBlockedError": raise
                msg = msg
                __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->llm' — passing data through unchecked")
            response = structured_llm.invoke(msg)
            try:
                response = gr_check(response, "llm", "agent", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:40ae66340d5773901df72c93ec2f282cb652d4ff0757743ea208c17076f3a85a', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'destination': {'entity_type': 'llm', 'name': 'openai', 'version': '', 'provider': ''}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'openai', 'version': '', 'purl': 'pkg:aimodel/openai@1.0.0'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 343, 'function': 'QuivrQARAGLangGraph.routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 343, 'function': 'routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'structured_llm.invoke'}, interaction_id=locals().get('_lineaje_interaction_id'))
            except Exception as _gr_exc:
                if type(_gr_exc).__name__ == "GRBlockedError": raise
                response = response
                __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'llm->agent' — passing data through unchecked")

        send_list: List[Send] = []

        instructions = (
            response.instructions
            if response.instructions
            else self.retrieval_config.prompt
        )

        if instructions:
            try:
                gr_check({"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:737e1b1d25ab6a27cdbb1bf0bb4efec87fb6339293100d7350a4f22cdab02de3', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=7fc7055a9bde18615a76542daeb0443354e5f57b&commit-time=2026-10-15%2021%3A30%3A36%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 555, 'function': 'QuivrQARAGLangGraph.routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 555, 'function': 'routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            send_list.append(Send("edit_system_prompt", {"instructions": instructions}))
        elif response.task_list:
            chat_history = state["chat_history"]
            try:
                gr_check({"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:13aeb5be35a56af3fb4a252304b7c42900d300d0a579996c3b5e88e807135d96', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 358, 'function': 'QuivrQARAGLangGraph.routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 358, 'function': 'routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            try:
                gr_check({"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:0931e79018617cb697a425a3911a7912717d5a9e2635b97320d967d2d77b1846', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=87929c913d1fa21471c076eb86747e9d325d3e6e&commit-time=2026-10-16%2001%3A29%3A09%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 567, 'function': 'QuivrQARAGLangGraph.routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 567, 'function': 'routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            try:
                gr_check({"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:0931e79018617cb697a425a3911a7912717d5a9e2635b97320d967d2d77b1846', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=fbecb3dd8756db019fc5d1b906964893812b2721&commit-time=2026-10-16%2002%3A57%3A22%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 571, 'function': 'QuivrQARAGLangGraph.routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 571, 'function': 'routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            send_list.append(
                Send(
                    "filter_history",
                    {
                        "chat_history": chat_history,
                        "tasks": UserTasks(response.task_list),
                    },
                )
            )

        try:
            send_list = gr_check(send_list, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:71d0ae9e91d666610108a3ecd5527edc1eed884294ff4dc07c2b5ab6d05ea8bc', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 367, 'function': 'QuivrQARAGLangGraph.routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 367, 'function': 'routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            send_list = send_list
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
        try:
            send_list = gr_check(send_list, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:dcbe5036985c32e5201c6db8cbe9c8b2bd1f20ecdc05b46fecd41b8e0dc889e3', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=7fc7055a9bde18615a76542daeb0443354e5f57b&commit-time=2026-10-15%2021%3A30%3A36%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 578, 'function': 'QuivrQARAGLangGraph.routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 578, 'function': 'routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            send_list = send_list
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
        try:
            send_list = gr_check(send_list, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:dcbe5036985c32e5201c6db8cbe9c8b2bd1f20ecdc05b46fecd41b8e0dc889e3', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=87929c913d1fa21471c076eb86747e9d325d3e6e&commit-time=2026-10-16%2001%3A29%3A09%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 588, 'function': 'QuivrQARAGLangGraph.routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 588, 'function': 'routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            send_list = send_list
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
        try:
            send_list = gr_check(send_list, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:dcbe5036985c32e5201c6db8cbe9c8b2bd1f20ecdc05b46fecd41b8e0dc889e3', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=fbecb3dd8756db019fc5d1b906964893812b2721&commit-time=2026-10-16%2002%3A57%3A22%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 598, 'function': 'QuivrQARAGLangGraph.routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 598, 'function': 'routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            send_list = send_list
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
        return send_list

    def routing_split(self, state: AgentState):
        response: SplittedInput = self.invoke_structured_output(
            custom_prompts[TemplatePromptName.SPLIT_PROMPT].format(
                chat_history=state["chat_history"].to_list(),
                user_input=state["messages"][0].content,
            ),
            SplittedInput,
        )

        instructions = response.instructions or self.retrieval_config.prompt
        tasks = UserTasks(response.task_list) if response.task_list else None

        if instructions:
            try:
                gr_check({"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:5e688c3cc66db38a0700a2a3bb12a9fa2ee2bd1d506d8bcf4da4e97f99b4c19f', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 383, 'function': 'QuivrQARAGLangGraph.routing_split'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 383, 'function': 'routing_split', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            try:
                gr_check({"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:0931e79018617cb697a425a3911a7912717d5a9e2635b97320d967d2d77b1846', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=7fc7055a9bde18615a76542daeb0443354e5f57b&commit-time=2026-10-15%2021%3A30%3A36%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 598, 'function': 'QuivrQARAGLangGraph.routing_split'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 598, 'function': 'routing_split', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            try:
                gr_check({"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:0931e79018617cb697a425a3911a7912717d5a9e2635b97320d967d2d77b1846', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=87929c913d1fa21471c076eb86747e9d325d3e6e&commit-time=2026-10-16%2001%3A29%3A09%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 612, 'function': 'QuivrQARAGLangGraph.routing_split'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 612, 'function': 'routing_split', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            try:
                gr_check({"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:0931e79018617cb697a425a3911a7912717d5a9e2635b97320d967d2d77b1846', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=fbecb3dd8756db019fc5d1b906964893812b2721&commit-time=2026-10-16%2002%3A57%3A22%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 626, 'function': 'QuivrQARAGLangGraph.routing_split'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 626, 'function': 'routing_split', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            return [
                Send(
                    "edit_system_prompt",
                    {**state, "instructions": instructions, "tasks": tasks},
                )
            ]
        elif tasks:
            try:
                gr_check({"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:61dd87ad65397f10f9bf4738f7b7bf25e803d5ed3e22bf494143515d07bf38f4', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 389, 'function': 'QuivrQARAGLangGraph.routing_split'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 389, 'function': 'routing_split', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            try:
                gr_check({"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:0931e79018617cb697a425a3911a7912717d5a9e2635b97320d967d2d77b1846', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=7fc7055a9bde18615a76542daeb0443354e5f57b&commit-time=2026-10-15%2021%3A30%3A36%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 608, 'function': 'QuivrQARAGLangGraph.routing_split'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 608, 'function': 'routing_split', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            try:
                gr_check({"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:0931e79018617cb697a425a3911a7912717d5a9e2635b97320d967d2d77b1846', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=87929c913d1fa21471c076eb86747e9d325d3e6e&commit-time=2026-10-16%2001%3A29%3A09%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 626, 'function': 'QuivrQARAGLangGraph.routing_split'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 626, 'function': 'routing_split', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            try:
                gr_check({"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:0931e79018617cb697a425a3911a7912717d5a9e2635b97320d967d2d77b1846', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=fbecb3dd8756db019fc5d1b906964893812b2721&commit-time=2026-10-16%2002%3A57%3A22%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 644, 'function': 'QuivrQARAGLangGraph.routing_split'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 644, 'function': 'routing_split', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            return [Send("filter_history", {**state, "tasks": tasks})]

        return []

    def update_active_tools(self, updated_prompt_and_tools: UpdatedPromptAndTools):
        if updated_prompt_and_tools.tools_to_activate:
            for tool in updated_prompt_and_tools.tools_to_activate:
                for (
                    validated_tool
                ) in self.retrieval_config.workflow_config.validated_tools:
                    if tool == validated_tool.name:
                        self.retrieval_config.workflow_config.activated_tools.append(
                            validated_tool
                        )

        if updated_prompt_and_tools.tools_to_deactivate:
            for tool in updated_prompt_and_tools.tools_to_deactivate:
                for (
                    activated_tool
                ) in self.retrieval_config.workflow_config.activated_tools:
                    if tool == activated_tool.name:
                        self.retrieval_config.workflow_config.activated_tools.remove(
                            activated_tool
                        )

    def edit_system_prompt(self, state: AgentState) -> AgentState:
        user_instruction = state["instructions"]
        prompt = self.retrieval_config.prompt
        available_tools, activated_tools = collect_tools(
            self.retrieval_config.workflow_config
        )
        inputs = {
            "instruction": user_instruction,
            "system_prompt": prompt if prompt else "",
            "available_tools": available_tools,
            "activated_tools": activated_tools,
        }

        msg = custom_prompts[TemplatePromptName.UPDATE_PROMPT].format(**inputs)

        response: UpdatedPromptAndTools = self.invoke_structured_output(
            msg, UpdatedPromptAndTools
        )

        self.update_active_tools(response)
        self.retrieval_config.prompt = response.prompt

        reasoning = [response.prompt_reasoning] if response.prompt_reasoning else []
        reasoning += [response.tools_reasoning] if response.tools_reasoning else []

        return {**state, "messages": [], "reasoning": reasoning}

    def filter_history(self, state: AgentState) -> AgentState:
        """
        Filter out the chat history to only include the messages that are relevant to the current question

        Takes in a chat_history= [HumanMessage(content='Qui est Chloé ? '),
        AIMessage(content="Chloé est une salariée travaillant pour l'entreprise Quivr en tant qu'AI Engineer,
        sous la direction de son supérieur hiérarchique, Stanislas Girard."),
        HumanMessage(content='Dis moi en plus sur elle'), AIMessage(content=''),
        HumanMessage(content='Dis moi en plus sur elle'),
        AIMessage(content="Désolé, je n'ai pas d'autres informations sur Chloé à partir des fichiers fournis.")]
        Returns a filtered chat_history with in priority: first max_tokens, then max_history where a Human message and an AI message count as one pair
        a token is 4 characters
        """

        chat_history = state["chat_history"]
        total_tokens = 0
        total_pairs = 0
        _chat_id = uuid4()
        _chat_history = ChatHistory(chat_id=_chat_id, brain_id=chat_history.brain_id)
        for human_message, ai_message in reversed(list(chat_history.iter_pairs())):
            # TODO: replace with tiktoken
            message_tokens = self.llm_endpoint.count_tokens(
                human_message.content
            ) + self.llm_endpoint.count_tokens(ai_message.content)

            if (
                total_tokens + message_tokens
                > self.retrieval_config.llm_config.max_context_tokens
                or total_pairs >= self.retrieval_config.max_history
            ):
                break
            _chat_history.append(human_message)
            _chat_history.append(ai_message)
            total_tokens += message_tokens
            total_pairs += 1

        return {**state, "chat_history": _chat_history}

    async def rewrite(self, state: AgentState) -> AgentState:
        """
        Transform the query to produce a better question.

        Args:
            state (messages): The current state

        Returns:
            dict: The updated state with re-phrased question
        """

        if "tasks" in state and state["tasks"]:
            tasks = state["tasks"]
        else:
            tasks = UserTasks([state["messages"][0].content])

        # Prepare the async tasks for all user tsks
        async_jobs = []
        for task_id in tasks.ids:
            msg = custom_prompts[TemplatePromptName.CONDENSE_TASK_PROMPT].format(
                chat_history=state["chat_history"].to_list(),
                task=tasks(task_id).definition,
            )

            model = self.llm_endpoint._llm
            # Asynchronously invoke the model for each question
            _lineaje_interaction_id = __import__("uuid").uuid4().hex
            try:
                import asyncio as _gr_asyncio
                msg = await _gr_asyncio.to_thread(gr_check, msg, "agent", "llm", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_070', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:4ca2c3c020d7bbd2547e1f4a0ea72ab93c1eeccd800c0a9922c962c97b48f8b2', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'destination': {'entity_type': 'llm', 'name': 'openai', 'version': '', 'provider': ''}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'openai', 'version': '', 'purl': 'pkg:aimodel/openai@1.0.0'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 505, 'function': 'QuivrQARAGLangGraph.rewrite'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 505, 'function': 'rewrite', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'model.ainvoke'}, interaction_id=_lineaje_interaction_id)
            except Exception as _gr_exc:
                if type(_gr_exc).__name__ == "GRBlockedError": raise
                msg = msg
                __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->llm' — passing data through unchecked")
            _lineaje_interaction_id = __import__("uuid").uuid4().hex
            try:
                import asyncio as _gr_asyncio
                msg = await _gr_asyncio.to_thread(gr_check, msg, "agent", "llm", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_070', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:f3043ac28ea221283924262c6c347414db53ffb1dd269bb309c6680a5c170927', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'destination': {'entity_type': 'llm', 'name': 'openai', 'version': '', 'provider': ''}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=7fc7055a9bde18615a76542daeb0443354e5f57b&commit-time=2026-10-15%2021%3A30%3A36%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'openai', 'version': '', 'purl': 'pkg:aimodel/openai@1.0.0'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 732, 'function': 'QuivrQARAGLangGraph.rewrite'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 732, 'function': 'rewrite', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'model.ainvoke'}, interaction_id=_lineaje_interaction_id)
            except Exception as _gr_exc:
                if type(_gr_exc).__name__ == "GRBlockedError": raise
                msg = msg
                __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->llm' — passing data through unchecked")
            async_jobs.append((model.ainvoke(msg), task_id))

        # Gather all the responses asynchronously
        responses = (
            await asyncio.gather(*(jobs[0] for jobs in async_jobs))
            if async_jobs
            else []
        )
        task_ids = [jobs[1] for jobs in async_jobs] if async_jobs else []

        # Replace each question with its condensed version
        for response, task_id in zip(responses, task_ids, strict=False):
            tasks.set_definition(task_id, response.content)
            try:
                import asyncio as _gr_asyncio
                response = await _gr_asyncio.to_thread(gr_check, response, "llm", "agent", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:82c69e77e7909612460ca546a1af1d025c1ed98f1e3b89279b6e7b674b666d31', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'destination': {'entity_type': 'llm', 'name': 'openai', 'version': '', 'provider': ''}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'openai', 'version': '', 'purl': 'pkg:aimodel/openai@1.0.0'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 517, 'function': 'QuivrQARAGLangGraph.rewrite'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 517, 'function': 'rewrite', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'tasks.set_definition'})
            except Exception as _gr_exc:
                if type(_gr_exc).__name__ == "GRBlockedError": raise
                response = response
                __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'llm->agent' — passing data through unchecked")

        return {**state, "tasks": tasks}

    def filter_chunks_by_relevance(self, chunks: List[Document], **kwargs):
        config = self.retrieval_config.reranker_config
        relevance_score_threshold = kwargs.get(
            "relevance_score_threshold", config.relevance_score_threshold
        )

        if relevance_score_threshold is None:
            try:
                chunks = gr_check(chunks, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:47b73da74fb8498a8cbc754a31025541f24e12a71ccd3511ab213b9d5363e151', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 528, 'function': 'QuivrQARAGLangGraph.filter_chunks_by_relevance'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 528, 'function': 'filter_chunks_by_relevance', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
            except Exception as _gr_exc:
                if type(_gr_exc).__name__ == "GRBlockedError": raise
                chunks = chunks
                __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
            try:
                chunks = gr_check(chunks, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:dcbe5036985c32e5201c6db8cbe9c8b2bd1f20ecdc05b46fecd41b8e0dc889e3', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=7fc7055a9bde18615a76542daeb0443354e5f57b&commit-time=2026-10-15%2021%3A30%3A36%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 768, 'function': 'QuivrQARAGLangGraph.filter_chunks_by_relevance'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 768, 'function': 'filter_chunks_by_relevance', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
            except Exception as _gr_exc:
                if type(_gr_exc).__name__ == "GRBlockedError": raise
                chunks = chunks
                __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
            try:
                chunks = gr_check(chunks, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:dcbe5036985c32e5201c6db8cbe9c8b2bd1f20ecdc05b46fecd41b8e0dc889e3', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=87929c913d1fa21471c076eb86747e9d325d3e6e&commit-time=2026-10-16%2001%3A29%3A09%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 800, 'function': 'QuivrQARAGLangGraph.filter_chunks_by_relevance'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 800, 'function': 'filter_chunks_by_relevance', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
            except Exception as _gr_exc:
                if type(_gr_exc).__name__ == "GRBlockedError": raise
                chunks = chunks
                __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
            try:
                chunks = gr_check(chunks, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:dcbe5036985c32e5201c6db8cbe9c8b2bd1f20ecdc05b46fecd41b8e0dc889e3', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=fbecb3dd8756db019fc5d1b906964893812b2721&commit-time=2026-10-16%2002%3A57%3A22%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 824, 'function': 'QuivrQARAGLangGraph.filter_chunks_by_relevance'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 824, 'function': 'filter_chunks_by_relevance', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
            except Exception as _gr_exc:
                if type(_gr_exc).__name__ == "GRBlockedError": raise
                chunks = chunks
                __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
            return chunks

        filtered_chunks = []
        for chunk in chunks:
            if config.relevance_score_key not in chunk.metadata:
                _lineaje_payload = f"Relevance score key {config.relevance_score_key} not found in metadata, cannot filter chunks by relevance"
                try:
                    _lineaje_payload = gr_check(_lineaje_payload, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:0300eea5637c93444dc88251be43b5e77c5afbfacb58b438e0df0fea07d891c4', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 533, 'function': 'QuivrQARAGLangGraph.filter_chunks_by_relevance'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 533, 'function': 'filter_chunks_by_relevance', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'logger.warning'})
                except Exception as _gr_exc:
                    if type(_gr_exc).__name__ == "GRBlockedError": raise
                    _lineaje_payload = _lineaje_payload
                    __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                _lineaje_payload_780 = f"Relevance score key {config.relevance_score_key} not found in metadata, cannot filter chunks by relevance"
                try:
                    _lineaje_payload_780 = gr_check(_lineaje_payload_780, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:b3ca64b3bd83c80bc4c1f1ed0c37595438212e9ca09ca38a60e1c70f5340f500', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=7fc7055a9bde18615a76542daeb0443354e5f57b&commit-time=2026-10-15%2021%3A30%3A36%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 780, 'function': 'QuivrQARAGLangGraph.filter_chunks_by_relevance'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 780, 'function': 'filter_chunks_by_relevance', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'logger.warning'})
                except Exception as _gr_exc:
                    if type(_gr_exc).__name__ == "GRBlockedError": raise
                    _lineaje_payload_780 = _lineaje_payload_780
                    __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                logger.warning(
                    f"Relevance score key {config.relevance_score_key} not found in metadata, cannot filter chunks by relevance"
                )
                filtered_chunks.append(chunk)
            elif (
                chunk.metadata[config.relevance_score_key] >= relevance_score_threshold
            ):
                filtered_chunks.append(chunk)

        try:
            filtered_chunks = gr_check(filtered_chunks, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:56f6bc28f9acb5b97e2dd6dd97769ba3b42afc8a1c9e1e7fcde6bc640d47f276', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 542, 'function': 'QuivrQARAGLangGraph.filter_chunks_by_relevance'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 542, 'function': 'filter_chunks_by_relevance', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            filtered_chunks = filtered_chunks
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
        try:
            filtered_chunks = gr_check(filtered_chunks, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:dcbe5036985c32e5201c6db8cbe9c8b2bd1f20ecdc05b46fecd41b8e0dc889e3', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=7fc7055a9bde18615a76542daeb0443354e5f57b&commit-time=2026-10-15%2021%3A30%3A36%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 795, 'function': 'QuivrQARAGLangGraph.filter_chunks_by_relevance'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 795, 'function': 'filter_chunks_by_relevance', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            filtered_chunks = filtered_chunks
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
        try:
            filtered_chunks = gr_check(filtered_chunks, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:dcbe5036985c32e5201c6db8cbe9c8b2bd1f20ecdc05b46fecd41b8e0dc889e3', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=87929c913d1fa21471c076eb86747e9d325d3e6e&commit-time=2026-10-16%2001%3A29%3A09%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 840, 'function': 'QuivrQARAGLangGraph.filter_chunks_by_relevance'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 840, 'function': 'filter_chunks_by_relevance', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            filtered_chunks = filtered_chunks
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
        try:
            filtered_chunks = gr_check(filtered_chunks, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:dcbe5036985c32e5201c6db8cbe9c8b2bd1f20ecdc05b46fecd41b8e0dc889e3', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=fbecb3dd8756db019fc5d1b906964893812b2721&commit-time=2026-10-16%2002%3A57%3A22%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 870, 'function': 'QuivrQARAGLangGraph.filter_chunks_by_relevance'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 870, 'function': 'filter_chunks_by_relevance', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            filtered_chunks = filtered_chunks
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
        return filtered_chunks

    async def tool_routing(self, state: AgentState):
        tasks = state["tasks"]
        if not tasks.has_tasks():
            try:
                import asyncio as _gr_asyncio
                await _gr_asyncio.to_thread(gr_check, {"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:8f2d3b75a42d2bc1806cb9d7c3f5db11aa067bb4652c9bf24de69ee38035d5b1', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 547, 'function': 'QuivrQARAGLangGraph.tool_routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 547, 'function': 'tool_routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            return [Send("generate_rag", state)]

        validated_tools, _ = collect_tools(self.retrieval_config.workflow_config)

        async_jobs = []
        for task_id in tasks.ids:
            input = {
                "chat_history": state["chat_history"].to_list(),
                "tasks": tasks(task_id).definition,
                "context": combine_documents(tasks(task_id).docs),
                "activated_tools": validated_tools,
            }

            msg = custom_prompts[TemplatePromptName.TOOL_ROUTING_PROMPT].format(**input)
            async_jobs.append(
                (self.ainvoke_structured_output(msg, TasksCompletion), task_id)
            )

        responses: List[TasksCompletion] = (
            await asyncio.gather(*(jobs[0] for jobs in async_jobs))
            if async_jobs
            else []
        )
        task_ids = [jobs[1] for jobs in async_jobs] if async_jobs else []

        for response, task_id in zip(responses, task_ids, strict=False):
            tasks.set_completion(task_id, response.is_task_completable)
            if not response.is_task_completable and response.tool:
                tasks.set_tool(task_id, response.tool)

        send_list: List[Send] = []

        payload = {**state, "tasks": tasks}

        if tasks.has_non_completable_tasks():
            send_list.append(Send("run_tool", payload))
        else:
            try:
                import asyncio as _gr_asyncio
                await _gr_asyncio.to_thread(gr_check, {"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:8a4433cca4cc4d5aade189baabbc57e13e6b37bdd7159ba06991eb9a74de4e5f', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 584, 'function': 'QuivrQARAGLangGraph.tool_routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 584, 'function': 'tool_routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            try:
                import asyncio as _gr_asyncio
                await _gr_asyncio.to_thread(gr_check, {"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:8a4433cca4cc4d5aade189baabbc57e13e6b37bdd7159ba06991eb9a74de4e5f', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=7fc7055a9bde18615a76542daeb0443354e5f57b&commit-time=2026-10-15%2021%3A30%3A36%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 847, 'function': 'QuivrQARAGLangGraph.tool_routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 847, 'function': 'tool_routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            try:
                import asyncio as _gr_asyncio
                await _gr_asyncio.to_thread(gr_check, {"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:8a4433cca4cc4d5aade189baabbc57e13e6b37bdd7159ba06991eb9a74de4e5f', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=87929c913d1fa21471c076eb86747e9d325d3e6e&commit-time=2026-10-16%2001%3A29%3A09%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 897, 'function': 'QuivrQARAGLangGraph.tool_routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 897, 'function': 'tool_routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            try:
                import asyncio as _gr_asyncio
                await _gr_asyncio.to_thread(gr_check, {"activity": "agent_to_agent"}, "agent", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:8a4433cca4cc4d5aade189baabbc57e13e6b37bdd7159ba06991eb9a74de4e5f', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=fbecb3dd8756db019fc5d1b906964893812b2721&commit-time=2026-10-16%2002%3A57%3A22%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 932, 'function': 'QuivrQARAGLangGraph.tool_routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 932, 'function': 'tool_routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'Send'})
            except Exception:
                pass
            send_list.append(Send("generate_rag", payload))

        try:
            import asyncio as _gr_asyncio
            send_list = await _gr_asyncio.to_thread(gr_check, send_list, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:36d08a9b6f61f005406ce8e2fccf6df6e10930cbcc6e3a57b62faf4699df7343', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 586, 'function': 'QuivrQARAGLangGraph.tool_routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 586, 'function': 'tool_routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            send_list = send_list
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
        try:
            import asyncio as _gr_asyncio
            send_list = await _gr_asyncio.to_thread(gr_check, send_list, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:dcbe5036985c32e5201c6db8cbe9c8b2bd1f20ecdc05b46fecd41b8e0dc889e3', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=7fc7055a9bde18615a76542daeb0443354e5f57b&commit-time=2026-10-15%2021%3A30%3A36%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 856, 'function': 'QuivrQARAGLangGraph.tool_routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 856, 'function': 'tool_routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            send_list = send_list
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
        try:
            import asyncio as _gr_asyncio
            send_list = await _gr_asyncio.to_thread(gr_check, send_list, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:dcbe5036985c32e5201c6db8cbe9c8b2bd1f20ecdc05b46fecd41b8e0dc889e3', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=87929c913d1fa21471c076eb86747e9d325d3e6e&commit-time=2026-10-16%2001%3A29%3A09%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 913, 'function': 'QuivrQARAGLangGraph.tool_routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 913, 'function': 'tool_routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            send_list = send_list
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
        try:
            import asyncio as _gr_asyncio
            send_list = await _gr_asyncio.to_thread(gr_check, send_list, "agent", "user_interface", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:dcbe5036985c32e5201c6db8cbe9c8b2bd1f20ecdc05b46fecd41b8e0dc889e3', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=fbecb3dd8756db019fc5d1b906964893812b2721&commit-time=2026-10-16%2002%3A57%3A22%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 955, 'function': 'QuivrQARAGLangGraph.tool_routing'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 955, 'function': 'tool_routing', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'site_kind': 'return'})
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            send_list = send_list
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->user_interface' — passing data through unchecked")
        return send_list

    async def run_tool(self, state: AgentState) -> AgentState:
        # if tool not in [
        #     t.name for t in self.retrieval_config.workflow_config.activated_tools
        # ]:
        #     raise ValueError(f"Tool {tool} not activated")

        tasks = state["tasks"]

        # Prepare the async tasks for all questions
        async_jobs = []
        for task_id in tasks.ids:
            if not tasks(task_id).is_completable() and tasks(task_id).has_tool():
                tool = tasks(task_id).tool
                tool_wrapper = LLMToolFactory.create_tool(tool, {})
                formatted_input = tool_wrapper.format_input(tasks(task_id).definition)
                try:
                    import asyncio as _gr_asyncio
                    formatted_input = await _gr_asyncio.to_thread(gr_check, formatted_input, "agent", "tool", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:ff66f03abb184c2fe6f68bee25fcba21779759e8ee2ee98062f266acc6acf8af', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 603, 'function': 'QuivrQARAGLangGraph.run_tool'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 603, 'function': 'run_tool', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'tool_wrapper.tool.ainvoke', 'tool_protocol': 'local', 'tool_protocol_source': 'scan: no MCP client imported'})
                except Exception as _gr_exc:
                    if type(_gr_exc).__name__ == "GRBlockedError": raise
                    formatted_input = formatted_input
                    __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->tool' — passing data through unchecked")
                try:
                    import asyncio as _gr_asyncio
                    formatted_input = await _gr_asyncio.to_thread(gr_check, formatted_input, "agent", "tool", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:6d13eb4c320ff9f211e534c6de73e77a16ea2f4378a007fc7b94fbbe442d36e3', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=7fc7055a9bde18615a76542daeb0443354e5f57b&commit-time=2026-10-15%2021%3A30%3A36%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 880, 'function': 'QuivrQARAGLangGraph.run_tool'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 880, 'function': 'run_tool', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'tool_wrapper.tool.ainvoke', 'tool_protocol': 'local', 'tool_protocol_source': 'scan: no MCP client imported'})
                except Exception as _gr_exc:
                    if type(_gr_exc).__name__ == "GRBlockedError": raise
                    formatted_input = formatted_input
                    __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->tool' — passing data through unchecked")
                async_jobs.append((tool_wrapper.tool.ainvoke(formatted_input), task_id))

        # Gather all the responses asynchronously
        responses = (
            await asyncio.gather(*(jobs[0] for jobs in async_jobs))
            if async_jobs
            else []
        )
        task_ids = [jobs[1] for jobs in async_jobs] if async_jobs else []

        for response, task_id in zip(responses, task_ids, strict=False):
            _docs = tool_wrapper.format_output(response)
            _docs = self.filter_chunks_by_relevance(_docs)
            tasks.set_docs(task_id, _docs)

        return {**state, "tasks": tasks}

    async def retrieve(self, state: AgentState) -> AgentState:
        """
        Retrieve relevent chunks

        Args:
            state (messages): The current state

        Returns:
            dict: The retrieved chunks
        """
        if "tasks" in state:
            tasks = state["tasks"]
        else:
            tasks = UserTasks([state["messages"][0].content])

        if not tasks.has_tasks():
            return {**state}

        _filter = state.get("_filter", None)

        kwargs = {
            "search_kwargs": {
                "k": self.retrieval_config.k,
                "filter": _filter,  # Add your desired filter here
            }
        }  # type: ignore
        base_retriever = self.get_retriever(**kwargs)

        kwargs = {"top_n": self.retrieval_config.reranker_config.top_n}  # type: ignore
        reranker = self.get_reranker(**kwargs)

        compression_retriever = ContextualCompressionRetriever(
            base_compressor=reranker, base_retriever=base_retriever
        )

        # Prepare the async tasks for all questions
        async_jobs = []
        for task_id in tasks.ids:
            # Create a tuple of the retrieval task and task_id
            async_jobs.append(
                (compression_retriever.ainvoke(tasks(task_id).definition), task_id)
            )

        # Gather all the responses asynchronously
        responses = (
            await asyncio.gather(*(task[0] for task in async_jobs))
            if async_jobs
            else []
        )
        task_ids = [task[1] for task in async_jobs] if async_jobs else []

        # Process responses and associate docs with tasks
        for response, task_id in zip(responses, task_ids, strict=False):
            _docs = self.filter_chunks_by_relevance(response)
            tasks.set_docs(task_id, _docs)  # Associate docs with the specific task

        return {**state, "tasks": tasks}

    async def dynamic_retrieve(self, state: AgentState) -> AgentState:
        """
        Retrieve relevent chunks

        Args:
            state (messages): The current state

        Returns:
            dict: The retrieved chunks
        """

        MAX_ITERATIONS = 3

        if "tasks" in state:
            tasks = state["tasks"]
        else:
            tasks = UserTasks([state["messages"][0].content])

        if not tasks or not tasks.has_tasks():
            return {**state}

        k = self.retrieval_config.k
        top_n = self.retrieval_config.reranker_config.top_n
        number_of_relevant_chunks = top_n
        i = 1

        while number_of_relevant_chunks == top_n and i <= MAX_ITERATIONS:
            top_n = self.retrieval_config.reranker_config.top_n * i
            kwargs = {"top_n": top_n}
            reranker = self.get_reranker(**kwargs)

            k = max([top_n * 2, self.retrieval_config.k])
            kwargs = {"search_kwargs": {"k": k}}  # type: ignore
            base_retriever = self.get_retriever(**kwargs)

            if i > 1:
                _lineaje_payload = f"Increasing top_n to {top_n} and k to {k} to retrieve more relevant chunks"
                try:
                    import asyncio as _gr_asyncio
                    _lineaje_payload = await _gr_asyncio.to_thread(gr_check, _lineaje_payload, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:b4f3afcade4c9d6ecef363ed1d5f34c369e2e228f00dfe77dc60c3030e309e8d', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 714, 'function': 'QuivrQARAGLangGraph.dynamic_retrieve'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 714, 'function': 'dynamic_retrieve', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'logging.info'})
                except Exception as _gr_exc:
                    if type(_gr_exc).__name__ == "GRBlockedError": raise
                    _lineaje_payload = _lineaje_payload
                    __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                _lineaje_payload_999 = f"Increasing top_n to {top_n} and k to {k} to retrieve more relevant chunks"
                try:
                    import asyncio as _gr_asyncio
                    _lineaje_payload_999 = await _gr_asyncio.to_thread(gr_check, _lineaje_payload_999, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:80874f12e906105999dc9f9c3d5dd3ab47b41131e943ab4b09cc1470cd771eca', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=7fc7055a9bde18615a76542daeb0443354e5f57b&commit-time=2026-10-15%2021%3A30%3A36%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 999, 'function': 'QuivrQARAGLangGraph.dynamic_retrieve'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 999, 'function': 'dynamic_retrieve', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'logging.info'})
                except Exception as _gr_exc:
                    if type(_gr_exc).__name__ == "GRBlockedError": raise
                    _lineaje_payload_999 = _lineaje_payload_999
                    __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                logging.info(
                    f"Increasing top_n to {top_n} and k to {k} to retrieve more relevant chunks"
                )

            compression_retriever = ContextualCompressionRetriever(
                base_compressor=reranker, base_retriever=base_retriever
            )

            # Prepare the async tasks for all questions
            async_jobs = []
            for task_id in tasks.ids:
                # Asynchronously invoke the model for each question
                try:
                    import asyncio as _gr_asyncio
                    await _gr_asyncio.to_thread(gr_check, {"activity": "rag_retrieve"}, "vector_store", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:57cdb3d212118338f59fd2c3797129bbf6a0e0621eaf18b24b729ff6f166e086', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 727, 'function': 'QuivrQARAGLangGraph.dynamic_retrieve'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 727, 'function': 'dynamic_retrieve', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'tasks'})
                except Exception:
                    pass
                try:
                    import asyncio as _gr_asyncio
                    await _gr_asyncio.to_thread(gr_check, {"activity": "rag_retrieve"}, "vector_store", "agent", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:d07ebecf4f510fbddced4816f0ebe8d90762c31f441a7f41cd4da750ba4ab36a', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=7fc7055a9bde18615a76542daeb0443354e5f57b&commit-time=2026-10-15%2021%3A30%3A36%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1017, 'function': 'QuivrQARAGLangGraph.dynamic_retrieve'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1017, 'function': 'dynamic_retrieve', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'tasks'})
                except Exception:
                    pass
                async_jobs.append(
                    (compression_retriever.ainvoke(tasks(task_id).definition), task_id)
                )

            # Gather all the responses asynchronously
            responses = (
                await asyncio.gather(*(jobs[0] for jobs in async_jobs))
                if async_jobs
                else []
            )
            task_ids = [jobs[1] for jobs in async_jobs] if async_jobs else []

            _n = []
            for response, task_id in zip(responses, task_ids, strict=False):
                _docs = self.filter_chunks_by_relevance(response)
                _n.append(len(_docs))
                tasks.set_docs(task_id, _docs)

            docs = tasks.docs
            if not docs:
                break

            context_length = self.get_rag_context_length(state, docs)
            if context_length >= self.retrieval_config.llm_config.max_context_tokens:
                _lineaje_payload = (f"The context length is {context_length} which is greater than "
                    f"the max context tokens of {self.retrieval_config.llm_config.max_context_tokens}")
                try:
                    import asyncio as _gr_asyncio
                    _lineaje_payload = await _gr_asyncio.to_thread(gr_check, _lineaje_payload, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:a1d0e957d35878b96c99a8dfe42ba84ca10cc74e84afaa6b30d8fff1a298ca58', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 750, 'function': 'QuivrQARAGLangGraph.dynamic_retrieve'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 750, 'function': 'dynamic_retrieve', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'logging.warning'})
                except Exception as _gr_exc:
                    if type(_gr_exc).__name__ == "GRBlockedError": raise
                    _lineaje_payload = _lineaje_payload
                    __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                logging.warning(
                    f"The context length is {context_length} which is greater than "
                    f"the max context tokens of {self.retrieval_config.llm_config.max_context_tokens}"
                )
                break

            number_of_relevant_chunks = max(_n)
            i += 1

        return {**state, "tasks": tasks}

    def _sort_docs_by_relevance(self, docs: List[Document]) -> List[Document]:
        return sorted(
            docs,
            key=lambda x: x.metadata[
                self.retrieval_config.reranker_config.relevance_score_key
            ],
            reverse=True,
        )

    async def retrieve_full_documents_context(self, state: AgentState) -> AgentState:
        if "tasks" in state:
            tasks = state["tasks"]
        else:
            tasks = UserTasks([state["messages"][0].content])

        if not tasks.has_tasks():
            return {**state}

        docs = tasks.docs if tasks else []

        relevant_knowledge: Dict[str, Dict[str, Any]] = {}
        for doc in docs:
            knowledge_id = doc.metadata["knowledge_id"]
            similarity_score = doc.metadata.get("similarity", 0)
            if knowledge_id in relevant_knowledge:
                relevant_knowledge[knowledge_id]["count"] += 1
                relevant_knowledge[knowledge_id]["max_similarity_score"] = max(
                    relevant_knowledge[knowledge_id]["max_similarity_score"],
                    similarity_score,
                )
                relevant_knowledge[knowledge_id]["chunk_index"] = max(
                    doc.metadata["chunk_index"],
                    relevant_knowledge[knowledge_id]["chunk_index"],
                )
            else:
                relevant_knowledge[knowledge_id] = {
                    "count": 1,
                    "max_similarity_score": similarity_score,
                    "chunk_index": doc.metadata["chunk_index"],
                }

        top_n = min(3, len(relevant_knowledge))
        # FIXME: Tweak this to return the most relevant knowledges
        top_knowledge_ids = OrderedDict(
            sorted(
                relevant_knowledge.items(),
                key=lambda x: (
                    x[1]["max_similarity_score"],
                    x[1]["count"],
                ),
                reverse=True,
            )[:top_n]
        )

        _lineaje_payload = f"Top knowledge IDs: {top_knowledge_ids}"
        try:
            import asyncio as _gr_asyncio
            _lineaje_payload = await _gr_asyncio.to_thread(gr_check, _lineaje_payload, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:68da78994b82bd5ee5f3d86b3f93cbf138199c430182672f66293e2344af5b43', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 815, 'function': 'QuivrQARAGLangGraph.retrieve_full_documents_context'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 815, 'function': 'retrieve_full_documents_context', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'logger.info'})
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            _lineaje_payload = _lineaje_payload
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
        _lineaje_payload_1122 = f"Top knowledge IDs: {top_knowledge_ids}"
        try:
            import asyncio as _gr_asyncio
            _lineaje_payload_1122 = await _gr_asyncio.to_thread(gr_check, _lineaje_payload_1122, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:a6a84b874c67ec9ddec3f36e68dca4ba069030fba458df2aa08dfd870d54f606', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=7fc7055a9bde18615a76542daeb0443354e5f57b&commit-time=2026-10-15%2021%3A30%3A36%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1122, 'function': 'QuivrQARAGLangGraph.retrieve_full_documents_context'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1122, 'function': 'retrieve_full_documents_context', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'logger.info'})
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            _lineaje_payload_1122 = _lineaje_payload_1122
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
        logger.info(f"Top knowledge IDs: {top_knowledge_ids}")

        _docs = []

        assert hasattr(
            self.vector_store, "get_vectors_by_knowledge_id"
        ), "Vector store must have method 'get_vectors_by_knowledge_id', this is an enterprise only feature"

        for knowledge_id in top_knowledge_ids:
            _docs.append(
                await self.vector_store.get_vectors_by_knowledge_id(  # type: ignore
                    knowledge_id,
                    end_index=relevant_knowledge[knowledge_id]["chunk_index"],
                )
            )

        tasks.set_docs(
            id=tasks.ids[0], docs=_docs
        )  # FIXME If multiple IDs is not handled.

        return {**state, "tasks": tasks}

    def get_rag_context_length(self, state: AgentState, docs: List[Document]) -> int:
        final_inputs = self._build_rag_prompt_inputs(state, docs)
        msg = custom_prompts[TemplatePromptName.RAG_ANSWER_PROMPT].format(
            **final_inputs
        )
        return self.llm_endpoint.count_tokens(msg)

    def reduce_rag_context(
        self,
        state: AgentState,
        inputs: Dict[str, Any],
        prompt: BasePromptTemplate,
        max_context_tokens: int | None = None,
    ) -> Tuple[AgentState, Dict[str, Any]]:
        MAX_ITERATIONS = 20
        SECURITY_FACTOR = 0.85
        iteration = 0

        tasks = state["tasks"] if "tasks" in state else None
        docs = tasks.docs if tasks else []
        msg = prompt.format(**inputs)
        n = self.llm_endpoint.count_tokens(msg)

        max_context_tokens = (
            max_context_tokens
            if max_context_tokens
            else self.retrieval_config.llm_config.max_context_tokens
        )

        # Get token counts for each doc in each task
        if tasks:
            task_token_counts = {}
            for task_id in tasks.ids:
                doc_tokens = [
                    self.llm_endpoint.count_tokens(doc.page_content)
                    for doc in tasks(task_id).docs
                ]
                task_token_counts[task_id] = {
                    "docs": doc_tokens,
                    "total": sum(doc_tokens),
                }

        while n > max_context_tokens * SECURITY_FACTOR:
            chat_history = inputs["chat_history"] if "chat_history" in inputs else []

            if len(chat_history) > 0:
                inputs["chat_history"] = chat_history[2:]
            elif tasks:
                longest_task_id = max(
                    task_token_counts.items(), key=lambda x: x[1]["total"]
                )[0]

                # Remove last doc from that task
                if task_token_counts[longest_task_id]["docs"]:
                    removed_tokens = task_token_counts[longest_task_id]["docs"].pop()
                    task_token_counts[longest_task_id]["total"] -= removed_tokens
                    tasks.set_docs(longest_task_id, tasks(longest_task_id).docs[:-1])
            else:
                logging.warning(
                    f"Not enough context to reduce. The context length is {n} "
                    f"which is greater than the max context tokens of {max_context_tokens}"
                )
                break

            docs = tasks.docs if tasks else []
            inputs["context"] = combine_documents(docs)

            msg = prompt.format(**inputs)
            n = self.llm_endpoint.count_tokens(msg)

            iteration += 1
            if iteration > MAX_ITERATIONS:
                _lineaje_payload = f"Attained the maximum number of iterations ({MAX_ITERATIONS})"
                try:
                    _lineaje_payload = gr_check(_lineaje_payload, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:7d61ffcea9ce191a08dca54a978266822907119a04e548fcf8300d8b34ef1c75', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 909, 'function': 'QuivrQARAGLangGraph.reduce_rag_context'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 909, 'function': 'reduce_rag_context', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'logging.warning'})
                except Exception as _gr_exc:
                    if type(_gr_exc).__name__ == "GRBlockedError": raise
                    _lineaje_payload = _lineaje_payload
                    __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                _lineaje_payload_1223 = f"Attained the maximum number of iterations ({MAX_ITERATIONS})"
                try:
                    _lineaje_payload_1223 = gr_check(_lineaje_payload_1223, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:668423150b2f80c01416b0692e9cf38417aebcb28a268ceb9c8b9f682fe28751', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=7fc7055a9bde18615a76542daeb0443354e5f57b&commit-time=2026-10-15%2021%3A30%3A36%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1223, 'function': 'QuivrQARAGLangGraph.reduce_rag_context'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1223, 'function': 'reduce_rag_context', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'logging.warning'})
                except Exception as _gr_exc:
                    if type(_gr_exc).__name__ == "GRBlockedError": raise
                    _lineaje_payload_1223 = _lineaje_payload_1223
                    __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                _lineaje_payload_1315 = f"Attained the maximum number of iterations ({MAX_ITERATIONS})"
                try:
                    _lineaje_payload_1315 = gr_check(_lineaje_payload_1315, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:668423150b2f80c01416b0692e9cf38417aebcb28a268ceb9c8b9f682fe28751', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=87929c913d1fa21471c076eb86747e9d325d3e6e&commit-time=2026-10-16%2001%3A29%3A09%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1315, 'function': 'QuivrQARAGLangGraph.reduce_rag_context'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1315, 'function': 'reduce_rag_context', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'logging.warning'})
                except Exception as _gr_exc:
                    if type(_gr_exc).__name__ == "GRBlockedError": raise
                    _lineaje_payload_1315 = _lineaje_payload_1315
                    __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                _lineaje_payload_1364 = f"Attained the maximum number of iterations ({MAX_ITERATIONS})"
                try:
                    _lineaje_payload_1364 = gr_check(_lineaje_payload_1364, "agent", "log", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_014', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_033', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_006', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:668423150b2f80c01416b0692e9cf38417aebcb28a268ceb9c8b9f682fe28751', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_uucWXDTUdAY6ryDB', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=fbecb3dd8756db019fc5d1b906964893812b2721&commit-time=2026-10-16%2002%3A57%3A22%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1364, 'function': 'QuivrQARAGLangGraph.reduce_rag_context'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1364, 'function': 'reduce_rag_context', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'logging.warning'})
                except Exception as _gr_exc:
                    if type(_gr_exc).__name__ == "GRBlockedError": raise
                    _lineaje_payload_1364 = _lineaje_payload_1364
                    __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->log' — passing data through unchecked")
                logging.warning(
                    f"Attained the maximum number of iterations ({MAX_ITERATIONS})"
                )
                break

        return {**state, "tasks": tasks}, inputs

    def bind_tools_to_llm(self, node_name: str):
        if self.llm_endpoint.supports_func_calling():
            tools = self.retrieval_config.workflow_config.get_node_tools(node_name)
            if tools:  # Only bind tools if there are any available
                return self.llm_endpoint._llm.bind_tools(tools, tool_choice="any")
        return self.llm_endpoint._llm

    def generate_zendesk_rag(self, state: AgentState) -> AgentState:
        tasks = state["tasks"]
        docs: List[Document] = tasks.docs if tasks else []
        messages = state["messages"]
        user_task = messages[0].content
        prompt_template: BasePromptTemplate = custom_prompts[
            TemplatePromptName.ZENDESK_TEMPLATE_PROMPT
        ]

        ticket_metadata = state["ticket_metadata"] or {}
        user_metadata = state["user_metadata"] or {}
        ticket_history = state.get("ticket_history", "")
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        inputs = {
            "similar_tickets": "\n".join([doc.page_content for doc in docs]),
            "ticket_metadata": format_dict(ticket_metadata),
            "user_metadata": format_dict(user_metadata),
            "client_query": user_task,
            "ticket_history": ticket_history,
            "current_time": current_time,
        }
        required_variables = prompt_template.input_variables
        for variable in required_variables:
            if variable not in inputs:
                inputs[variable] = state.get(variable, "")

        msg = prompt_template.format_prompt(**inputs)
        llm = self.bind_tools_to_llm(self.generate_zendesk_rag.__name__)

        _lineaje_interaction_id = __import__("uuid").uuid4().hex
        try:
            msg = gr_check(msg, "agent", "llm", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_070', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:27eb55300402f0bc08d9ab42158f1afe7379393f1d76fa161aaefc96220264b2', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'destination': {'entity_type': 'llm', 'name': 'openai', 'version': '', 'provider': ''}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'openai', 'version': '', 'purl': 'pkg:aimodel/openai@1.0.0'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 952, 'function': 'QuivrQARAGLangGraph.generate_zendesk_rag'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 952, 'function': 'generate_zendesk_rag', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'llm.invoke'}, interaction_id=_lineaje_interaction_id)
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            msg = msg
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->llm' — passing data through unchecked")
        response = llm.invoke(msg)
        try:
            response = gr_check(response, "llm", "agent", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:235e285f1488973d9a48ccd221d93cc1df5a64c4ca59f13c482c1891e63b8918', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'destination': {'entity_type': 'llm', 'name': 'openai', 'version': '', 'provider': ''}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'openai', 'version': '', 'purl': 'pkg:aimodel/openai@1.0.0'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 952, 'function': 'QuivrQARAGLangGraph.generate_zendesk_rag'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 952, 'function': 'generate_zendesk_rag', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'llm.invoke'}, interaction_id=locals().get('_lineaje_interaction_id'))
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            response = response
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'llm->agent' — passing data through unchecked")

        return {**state, "messages": [response]}

    def generate_rag(self, state: AgentState) -> AgentState:
        tasks = state["tasks"]
        docs = tasks.docs if tasks else []
        inputs = self._build_rag_prompt_inputs(state, docs)
        prompt = custom_prompts[TemplatePromptName.RAG_ANSWER_PROMPT]
        state, inputs = self.reduce_rag_context(state, inputs, prompt)
        msg = prompt.format(**inputs)
        llm = self.bind_tools_to_llm(self.generate_rag.__name__)
        _lineaje_interaction_id = __import__("uuid").uuid4().hex
        try:
            msg = gr_check(msg, "agent", "llm", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_070', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:6f310daf8d1fc35fa942643f396e0dd6ffdb12987f30437d40733f8b764b3046', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'destination': {'entity_type': 'llm', 'name': 'openai', 'version': '', 'provider': ''}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'openai', 'version': '', 'purl': 'pkg:aimodel/openai@1.0.0'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 964, 'function': 'QuivrQARAGLangGraph.generate_rag'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 964, 'function': 'generate_rag', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'llm.invoke'}, interaction_id=_lineaje_interaction_id)
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            msg = msg
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->llm' — passing data through unchecked")
        response = llm.invoke(msg)
        try:
            response = gr_check(response, "llm", "agent", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:5d8dd67261b095913a80d08a6da3f065ab5274bda2c16702e846245a7e2da1f1', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'destination': {'entity_type': 'llm', 'name': 'openai', 'version': '', 'provider': ''}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'openai', 'version': '', 'purl': 'pkg:aimodel/openai@1.0.0'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 964, 'function': 'QuivrQARAGLangGraph.generate_rag'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 964, 'function': 'generate_rag', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'llm.invoke'}, interaction_id=locals().get('_lineaje_interaction_id'))
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            response = response
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'llm->agent' — passing data through unchecked")

        return {**state, "messages": [response]}

    def generate_chat_llm(self, state: AgentState) -> AgentState:
        """
        Generate answer

        Args:
            state (messages): The current state

        Returns:
            dict: The updated state with re-phrased question
        """
        messages = state["messages"]

        # Check if there is a system message in messages
        system_message = None
        user_message = None

        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_message = str(msg.content)
            elif isinstance(msg, HumanMessage):
                user_message = str(msg.content)

        user_task = (
            user_message if user_message else (messages[0].content if messages else "")
        )

        # Prompt
        prompt = self.retrieval_config.prompt

        final_inputs = {}
        final_inputs["task"] = user_task
        final_inputs["custom_instructions"] = prompt if prompt else "None"
        final_inputs["chat_history"] = state["chat_history"].to_list()

        # LLM
        llm = self.llm_endpoint._llm

        prompt = custom_prompts[TemplatePromptName.CHAT_LLM_PROMPT]
        state, reduced_inputs = self.reduce_rag_context(
            state, final_inputs, system_message if system_message else prompt
        )
        CHAT_LLM_PROMPT = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=str(system_message)),
                MessagesPlaceholder(variable_name="chat_history"),
                HumanMessage(content=str(user_message)),
            ]
        )
        # Run
        _lineaje_payload = {"chat_history": final_inputs["chat_history"]}
        _lineaje_interaction_id = __import__("uuid").uuid4().hex
        try:
            _lineaje_payload = gr_check(_lineaje_payload, "agent", "llm", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_070', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:aba415e6d06f0a76401670fcb9060bae7d4debea3d7618a59e4296b2fcf4d495', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'destination': {'entity_type': 'llm', 'name': 'openai', 'version': '', 'provider': ''}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'openai', 'version': '', 'purl': 'pkg:aimodel/openai@1.0.0'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1017, 'function': 'QuivrQARAGLangGraph.generate_chat_llm'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1017, 'function': 'generate_chat_llm', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'CHAT_LLM_PROMPT.invoke'}, interaction_id=_lineaje_interaction_id)
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            _lineaje_payload = _lineaje_payload
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->llm' — passing data through unchecked")
        _lineaje_payload_1365 = {"chat_history": final_inputs["chat_history"]}
        _lineaje_interaction_id = __import__("uuid").uuid4().hex
        try:
            _lineaje_payload_1365 = gr_check(_lineaje_payload_1365, "agent", "llm", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_070', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:7ac8c3ff06a83a4ec4c6298cc978da35a160eb857a00dbf79df95ea4ee5f1227', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 203, 'name': 'CohereRerank'}, 'destination': {'entity_type': 'llm', 'name': 'openai', 'version': '', 'provider': ''}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=7fc7055a9bde18615a76542daeb0443354e5f57b&commit-time=2026-10-15%2021%3A30%3A36%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'openai', 'version': '', 'purl': 'pkg:aimodel/openai@1.0.0'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1365, 'function': 'QuivrQARAGLangGraph.generate_chat_llm'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1365, 'function': 'generate_chat_llm', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'CHAT_LLM_PROMPT.invoke'}, interaction_id=_lineaje_interaction_id)
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            _lineaje_payload_1365 = _lineaje_payload_1365
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->llm' — passing data through unchecked")
        chat_llm_prompt = CHAT_LLM_PROMPT.invoke(
            {"chat_history": final_inputs["chat_history"]}
        )
        _lineaje_interaction_id = __import__("uuid").uuid4().hex
        try:
            chat_llm_prompt = gr_check(chat_llm_prompt, "agent", "llm", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_070', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:2791dfe3c21a8dab118acea2ac667242c7296ca8cce0ab01c8e6d7288d46620b', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'destination': {'entity_type': 'llm', 'name': 'openai', 'version': '', 'provider': ''}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'openai', 'version': '', 'purl': 'pkg:aimodel/openai@1.0.0'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1020, 'function': 'QuivrQARAGLangGraph.generate_chat_llm'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1020, 'function': 'generate_chat_llm', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'llm.invoke'}, interaction_id=_lineaje_interaction_id)
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            chat_llm_prompt = chat_llm_prompt
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->llm' — passing data through unchecked")
        response = llm.invoke(chat_llm_prompt)
        try:
            response = gr_check(response, "llm", "agent", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:05232b3cd58eb985085104dc0a6114dec4d3268362c66fdf59309f69e309ebf3', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'destination': {'entity_type': 'llm', 'name': 'openai', 'version': '', 'provider': ''}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'openai', 'version': '', 'purl': 'pkg:aimodel/openai@1.0.0'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1020, 'function': 'QuivrQARAGLangGraph.generate_chat_llm'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1020, 'function': 'generate_chat_llm', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'llm.invoke'}, interaction_id=locals().get('_lineaje_interaction_id'))
        except Exception as _gr_exc:
            if type(_gr_exc).__name__ == "GRBlockedError": raise
            response = response
            __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'llm->agent' — passing data through unchecked")
        return {**state, "messages": [response]}

    def build_chain(self):
        """
        Builds the langchain chain for the given configuration.

        Returns:
            Callable[[Dict], Dict]: The langchain chain.
        """
        if not self.graph:
            self.graph = self.create_graph()

        return self.graph

    def create_graph(self):
        workflow = StateGraph(AgentState)
        self.final_nodes = []

        self._build_workflow(workflow)

        return workflow.compile()

    def _build_workflow(self, workflow: StateGraph):
        for node in self.retrieval_config.workflow_config.nodes:
            if node.name not in [START, END]:
                workflow.add_node(node.name, getattr(self, node.name))

        for node in self.retrieval_config.workflow_config.nodes:
            self._add_node_edges(workflow, node)

    def _add_node_edges(self, workflow: StateGraph, node: NodeConfig):
        if node.edges:
            for edge in node.edges:
                workflow.add_edge(node.name, edge)
                if edge == END:
                    self.final_nodes.append(node.name)
        elif node.conditional_edge:
            routing_function = getattr(self, node.conditional_edge.routing_function)
            workflow.add_conditional_edges(
                node.name, routing_function, node.conditional_edge.conditions
            )
            if END in node.conditional_edge.conditions:
                self.final_nodes.append(node.name)
        else:
            raise ValueError("Node should have at least one edge or conditional_edge")

    async def answer_astream(
        self,
        run_id: UUID,
        question: str,
        system_prompt: str | None,
        history: ChatHistory,
        list_files: list[QuivrKnowledge],
        metadata: LangchainMetadata | None = None,
        **input_kwargs,
    ) -> AsyncGenerator[ParsedRAGChunkResponse, ParsedRAGChunkResponse]:
        """
        Answer a question using the langgraph chain and yield each chunk of the answer separately.
        """
        concat_list_files = format_file_list(
            list_files, self.retrieval_config.max_files
        )
        conversational_qa_chain = self.build_chain()

        rolling_message = AIMessageChunk(content="")
        docs: list[Document] | None = None
        previous_content = ""
        system_prompt = system_prompt
        messages = [("system", system_prompt)] if system_prompt else []
        messages.append(("user", question))

        try:
            import asyncio as _gr_asyncio
            await _gr_asyncio.to_thread(gr_check, {"activity": "agent_to_llm"}, "agent", "llm", observe_only=True, candidate_policies=['AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:2767f8292f08f8493d84d82b95cff8d59e19f42cce29cdf7795c4785f7d0c23f', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'destination': {'entity_type': 'llm', 'name': 'openai', 'version': '', 'provider': ''}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'openai', 'version': '', 'purl': 'pkg:aimodel/openai@1.0.0'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1092, 'function': 'QuivrQARAGLangGraph.answer_astream'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1092, 'function': 'answer_astream', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'conversational_qa_chain.astream_events'})
        except Exception:
            pass
        async for event in conversational_qa_chain.astream_events(
            {
                "messages": messages,
                "chat_history": history,
                "files": concat_list_files,
                **input_kwargs,
            },
            version="v1",
            config={
                "run_id": run_id,
                "metadata": metadata.model_dump() if metadata else {},
                "callbacks": [langfuse_handler],
            },
        ):
            node_name = self._extract_node_name(event)

            if self._is_final_node_with_docs(event):
                tasks = event["data"]["output"]["tasks"]
                docs = tasks.docs if tasks else []

            if self._is_final_node_and_chat_model_stream(event):
                chunk = event["data"]["chunk"]
                rolling_message, new_content, previous_content = parse_chunk_response(
                    rolling_message,
                    chunk,
                    self.llm_endpoint.supports_func_calling(),
                    previous_content,
                )

                if new_content:
                    chunk_metadata = get_chunk_metadata(rolling_message, docs)
                    if node_name:
                        chunk_metadata.workflow_step = node_name
                    yield ParsedRAGChunkResponse(
                        answer=new_content, metadata=chunk_metadata
                    )
            else:
                if node_name:
                    yield ParsedRAGChunkResponse(
                        answer="",
                        metadata=RAGResponseMetadata(workflow_step=node_name),
                    )

        # Yield final metadata chunk
        chunk_metadata = get_chunk_metadata(rolling_message, docs)
        if metadata:
            chunk_metadata.langchain_metadata = metadata
            chunk_metadata.langchain_metadata.langfuse_trace_url = (
                langfuse_handler.get_trace_url()
            )

        yield ParsedRAGChunkResponse(
            answer="",
            metadata=chunk_metadata,
            last_chunk=True,
        )

    def _is_final_node_with_docs(self, event: StreamEvent) -> bool:
        return (
            "output" in event["data"]
            and event["data"]["output"] is not None
            and "tasks" in event["data"]["output"]
            and event["metadata"]["langgraph_node"] in self.final_nodes
        )

    def _is_final_node_and_chat_model_stream(self, event: StreamEvent) -> bool:
        return (
            event["event"] == "on_chat_model_stream"
            and "langgraph_node" in event["metadata"]
            and event["metadata"]["langgraph_node"] in self.final_nodes
        )

    def _extract_node_name(self, event: StreamEvent) -> str:
        if "metadata" in event and "langgraph_node" in event["metadata"]:
            name = event["metadata"]["langgraph_node"]
            for node in self.retrieval_config.workflow_config.nodes:
                if node.name == name:
                    if node.description:
                        return node.description
                    else:
                        return node.name
        return ""

    async def ainvoke_structured_output(
        self, prompt: str, output_class: Type[BaseModel]
    ) -> Any:
        try:
            structured_llm = self.llm_endpoint._llm.with_structured_output(
                output_class, method="json_schema"
            )
            return await structured_llm.ainvoke(prompt)
        except openai.BadRequestError:
            structured_llm = self.llm_endpoint._llm.with_structured_output(output_class)
            _lineaje_interaction_id = __import__("uuid").uuid4().hex
            try:
                import asyncio as _gr_asyncio
                prompt = await _gr_asyncio.to_thread(gr_check, prompt, "agent", "llm", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_070', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:7c634181d5021524a8d56df9955b8eb4e74fa70e83020a689b0d3861723fcee2', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'destination': {'entity_type': 'llm', 'name': 'openai', 'version': '', 'provider': ''}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'openai', 'version': '', 'purl': 'pkg:aimodel/openai@1.0.0'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1185, 'function': 'QuivrQARAGLangGraph.ainvoke_structured_output'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1185, 'function': 'ainvoke_structured_output', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'structured_llm.ainvoke'}, interaction_id=_lineaje_interaction_id)
            except Exception as _gr_exc:
                if type(_gr_exc).__name__ == "GRBlockedError": raise
                prompt = prompt
                __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->llm' — passing data through unchecked")
            return await structured_llm.ainvoke(prompt)

    def invoke_structured_output(
        self, prompt: str, output_class: Type[BaseModel]
    ) -> Any:
        try:
            structured_llm = self.llm_endpoint._llm.with_structured_output(
                output_class, method="json_schema"
            )
            return structured_llm.invoke(prompt)
        except openai.BadRequestError:
            structured_llm = self.llm_endpoint._llm.with_structured_output(output_class)
            _lineaje_interaction_id = __import__("uuid").uuid4().hex
            try:
                prompt = gr_check(prompt, "agent", "llm", candidate_policies=['AI_APP_SEC_001', 'AI_APP_SEC_002', 'AI_APP_SEC_006', 'AI_APP_SEC_022', 'AI_APP_SEC_023', 'AI_APP_SEC_028', 'AI_APP_SEC_029', 'AI_APP_SEC_032', 'AI_APP_SEC_034', 'AI_APP_SEC_035', 'AI_APP_SEC_038', 'AI_APP_SEC_039', 'AI_APP_SEC_040', 'AI_APP_SEC_059', 'AI_APP_SEC_064', 'AI_APP_SEC_066', 'AI_APP_SEC_067', 'AI_APP_SEC_068', 'AI_APP_SEC_069', 'AI_APP_SEC_070', 'AI_APP_SEC_071', 'AI_APP_SEC_075', 'AI_APP_SEC_078', 'AI_DAT_SEC_001', 'AI_DAT_SEC_009', 'AI_DAT_SEC_010', 'AI_DAT_SEC_011', 'AI_DAT_SEC_012', 'AI_DAT_SEC_023', 'AI_DAT_SEC_024', 'AI_DAT_SEC_025', 'AI_DAT_SEC_027', 'AI_DAT_SEC_029', 'AI_DAT_SEC_030', 'AI_IAC_002', 'AI_IAC_007', 'AI_IAC_008', 'AI_IAC_009', 'AI_IAC_014', 'AI_IAC_015', 'AI_IAC_016', 'AI_IAC_017', 'AI_IAC_018', 'AI_IAC_020', 'AI_IAC_022', 'AI_IAC_023', 'AI_IAC_024', 'AI_IAC_025', 'AI_IAC_026', 'AI_IAC_031', 'AI_VULN_SEC_005', 'AI_AGENT_ACTIVITY_LOG'], site_id='site:sha256:94e66e40112a220834f5532fb9c6167ca6478126d0adbf5379657658b404b6be', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_6dXylGIYVjVO6Lkf', 'repository_uri': 'https://github.com/anaghatestuser/quivr_lineaje', 'file_path': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 21, 'name': 'CohereRerank'}, 'destination': {'entity_type': 'llm', 'name': 'openai', 'version': '', 'provider': ''}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'CohereRerank', 'version': '1.0.0', 'purl': 'pkg:aiagent/CohereRerank@1.0.0'}, 'app': {'name': 'quivr_lineaje', 'version': 'main', 'purl': 'pkg:github/anaghatestuser/quivr_lineaje@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}, 'destination': {'entity_type': 'aimodel', 'name': 'openai', 'version': '', 'purl': 'pkg:aimodel/openai@1.0.0'}}, 'invocation': {'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1197, 'function': 'QuivrQARAGLangGraph.invoke_structured_output'}, 'file': 'core/quivr_core/rag/quivr_rag_langgraph.py', 'line': 1197, 'function': 'invoke_structured_output', 'agent_name': 'QuivrQARAGLangGraph', 'agent_name_source': 'inferred_from_class', 'call_target': 'structured_llm.invoke'}, interaction_id=_lineaje_interaction_id)
            except Exception as _gr_exc:
                if type(_gr_exc).__name__ == "GRBlockedError": raise
                prompt = prompt
                __import__("logging").getLogger("lineaje.gr_client").warning("Lineaje guardrail unavailable at 'agent->llm' — passing data through unchecked")
            return structured_llm.invoke(prompt)

    def _build_rag_prompt_inputs(
        self, state: AgentState, docs: List[Document] | None
    ) -> Dict[str, Any]:
        """Build the input dictionary for RAG_ANSWER_PROMPT.

        Args:
            state: Current agent state
            docs: List of documents or None

        Returns:
            Dictionary containing all inputs needed for RAG_ANSWER_PROMPT
        """
        messages = state["messages"]
        user_task = messages[0].content
        files = state["files"]
        prompt = self.retrieval_config.prompt
        # available_tools, _ = collect_tools(self.retrieval_config.workflow_config)

        return {
            "context": combine_documents(docs) if docs else "None",
            "task": user_task,
            "rephrased_task": state["tasks"].definitions if state["tasks"] else "None",
            "custom_instructions": prompt if prompt else "None",
            "files": files if files else "None",
            "chat_history": state["chat_history"].to_list(),
            # "reasoning": state["reasoning"] if "reasoning" in state else "None",
            # "tools": available_tools,
        }
