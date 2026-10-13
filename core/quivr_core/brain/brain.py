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
import logging
import os
from pathlib import Path
from pprint import PrettyPrinter
from typing import Any, AsyncGenerator, Callable, Dict, Self, Type, Union
from uuid import UUID, uuid4

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.vectorstores import VectorStore
from langchain_openai import OpenAIEmbeddings
from rich.console import Console
from rich.panel import Panel

from quivr_core.brain.info import BrainInfo, ChatHistoryInfo
from quivr_core.brain.serialization import (
    BrainSerialized,
    EmbedderConfig,
    FAISSConfig,
    LocalStorageConfig,
    TransparentStorageConfig,
)
from quivr_core.files.file import load_qfile
from quivr_core.llm import LLMEndpoint
from quivr_core.processor.registry import get_processor_class
from quivr_core.rag.entities.chat import ChatHistory
from quivr_core.rag.entities.config import RetrievalConfig
from quivr_core.rag.entities.models import (
    LangchainMetadata,
    ParsedRAGChunkResponse,
    ParsedRAGResponse,
    QuivrKnowledge,
    SearchResult,
)
from quivr_core.rag.quivr_rag import QuivrQARAG
from quivr_core.rag.quivr_rag_langgraph import QuivrQARAGLangGraph
from quivr_core.storage.local_storage import LocalStorage, TransparentStorage
from quivr_core.storage.storage_base import StorageBase

from .brain_defaults import build_default_vectordb, default_embedder, default_llm

logger = logging.getLogger("quivr_core")


async def process_files(
    storage: StorageBase, skip_file_error: bool, **processor_kwargs: dict[str, Any]
) -> list[Document]:
    """
    Process files in storage.
    This function takes a StorageBase and return a list of langchain documents.
    Args:
        storage (StorageBase): The storage containing the files to process.
        skip_file_error (bool): Whether to skip files that cannot be processed.
        processor_kwargs (dict[str, Any]): Additional arguments for the processor.
    Returns:
        list[Document]: List of processed documents in the Langchain Document format.
    Raises:
        ValueError: If a file cannot be processed and skip_file_error is False.
        Exception: If no processor is found for a file of a specific type and skip_file_error is False.
    """

    knowledge = []
    for file in await storage.get_files():
        try:
            if file.file_extension:
                processor_cls = get_processor_class(file.file_extension)
                _lineaje_payload = f"processing {file} using class {processor_cls.__name__}"
                # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:f2691307f34833bb0a19cc007a6ae256946125c32bbecde051672c42abd5483f'
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:f2691307f34833bb0a19cc007a6ae256946125c32bbecde051672c42abd5483f', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'core/quivr_core/brain/brain.py', 'line': 13, 'name': 'OpenAIEmbeddings'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'OpenAIEmbeddings', 'version': '1.0.0', 'purl': 'pkg:aiagent/OpenAIEmbeddings@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/brain/brain.py', 'line': 69, 'function': 'process_files'}})
                try:
                    _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json'))
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    pass
                logger.debug(_lineaje_payload)
                processor = processor_cls(**processor_kwargs)
                docs = await processor.process_file(file)
                knowledge.extend(docs)
            else:
                _lineaje_payload = f"can't find processor for {file}"
                # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:29d7a3e92f2def825dfd36011afa5f09d9b2c0a5cec8e364ded2bd062b644ac8'
                _gr_client = _lineaje_load_gr_client()
                _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:29d7a3e92f2def825dfd36011afa5f09d9b2c0a5cec8e364ded2bd062b644ac8', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'core/quivr_core/brain/brain.py', 'line': 13, 'name': 'OpenAIEmbeddings'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'OpenAIEmbeddings', 'version': '1.0.0', 'purl': 'pkg:aiagent/OpenAIEmbeddings@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/brain/brain.py', 'line': 74, 'function': 'process_files'}})
                try:
                    _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json'))
                except _gr_client.GuardrailUnavailableError:
                    pass
                except PermissionError:
                    pass
                logger.error(_lineaje_payload)
                if skip_file_error:
                    continue
                else:
                    raise ValueError(f"can't parse {file}. can't find file extension")
        except KeyError as e:
            if skip_file_error:
                continue
            else:
                raise Exception(f"Can't parse {file}. No available processor") from e

    # LINEAJE: enforce() `knowledge` at agent->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:f1f7dc277ae27ca95a324dd6853d1b8b4448161abf5fa588f627119f2235244e'
    _gr_client = _lineaje_load_gr_client()
    _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:f1f7dc277ae27ca95a324dd6853d1b8b4448161abf5fa588f627119f2235244e', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='user_interface', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'core/quivr_core/brain/brain.py', 'line': 13, 'name': 'OpenAIEmbeddings'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'OpenAIEmbeddings', 'version': '1.0.0', 'purl': 'pkg:aiagent/OpenAIEmbeddings@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/brain/brain.py', 'line': 85, 'function': 'process_files'}})
    try:
        knowledge = _gr_client.enforce(_gr_site, knowledge, content_type='text/plain')
    except _gr_client.GuardrailUnavailableError:
        pass
    except PermissionError:
        pass
    return knowledge


class Brain:
    """
    A class representing a Brain.
    This class allows for the creation of a Brain, which is a collection of knowledge one wants to retrieve information from.
    A Brain is set to:
    * Store files in the storage of your choice (local, S3, etc.)
    * Process the files in the storage to extract text and metadata in a wide range of format.
    * Store the processed files in the vector store of your choice (FAISS, PGVector, etc.) - default to FAISS.
    * Create an index of the processed files.
    * Use the *Quivr* workflow for the retrieval augmented generation.
    A Brain is able to:
    * Search for information in the vector store.
    * Answer questions about the knowledges in the Brain.
    * Stream the answer to the question.
    Attributes:
        name (str): The name of the brain.
        id (UUID): The unique identifier of the brain.
        storage (StorageBase): The storage used to store the files.
        llm (LLMEndpoint): The language model used to generate the answer.
        vector_db (VectorStore): The vector store used to store the processed files.
        embedder (Embeddings): The embeddings used to create the index of the processed files.
    """

    def __init__(
        self,
        *,
        name: str,
        llm: LLMEndpoint,
        id: UUID | None = None,
        vector_db: VectorStore | None = None,
        embedder: Embeddings | None = None,
        storage: StorageBase | None = None,
        workspace_id: UUID | None = None,
        chat_id: UUID | None = None,
    ):
        self.id = id
        self.name = name
        self.storage = storage
        self.workspace_id = workspace_id
        self.chat_id = chat_id
        # Chat history
        self._chats = self._init_chats()
        self.default_chat = list(self._chats.values())[0]

        # RAG dependencies:
        self.llm = llm
        self.vector_db = vector_db
        self.embedder = embedder

    def __repr__(self) -> str:
        pp = PrettyPrinter(width=80, depth=None, compact=False, sort_dicts=False)
        return pp.pformat(self.info())

    def print_info(self):
        console = Console()
        tree = self.info().to_tree()
        panel = Panel(tree, title="Brain Info", expand=False, border_style="bold")
        # LINEAJE: enforce() `panel` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:845dd4959d03f2dce6585f53bef1241c8924547cacb9d53a311946e2b662a2c3'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:845dd4959d03f2dce6585f53bef1241c8924547cacb9d53a311946e2b662a2c3', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'core/quivr_core/brain/brain.py', 'line': 13, 'name': 'OpenAIEmbeddings'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'OpenAIEmbeddings', 'version': '1.0.0', 'purl': 'pkg:aiagent/OpenAIEmbeddings@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/brain/brain.py', 'line': 145, 'function': 'Brain.print_info'}})
        try:
            panel = _gr_client.enforce(_gr_site, panel, content_type='application/json')
        except _gr_client.GuardrailUnavailableError:
            pass
        except PermissionError:
            pass
        console.print(panel)

    @classmethod
    def load(cls, folder_path: str | Path) -> Self:
        """
        Load a brain from a folder path.
        Args:
            folder_path (str | Path): The path to the folder containing the brain.
        Returns:
            Brain: The brain loaded from the folder path.
        Example:
        ```python
        brain_loaded = Brain.load("path/to/brain")
        brain_loaded.print_info()
        ```
        """
        if isinstance(folder_path, str):
            folder_path = Path(folder_path)
        if not folder_path.exists():
            raise ValueError(f"path {folder_path} doesn't exist")

        # Load brainserialized
        with open(os.path.join(folder_path, "config.json"), "r") as f:
            bserialized = BrainSerialized.model_validate_json(f.read())

        storage: StorageBase | None = None
        # Loading storage
        if bserialized.storage_config.storage_type == "transparent_storage":
            storage = TransparentStorage.load(bserialized.storage_config)
        elif bserialized.storage_config.storage_type == "local_storage":
            storage = LocalStorage.load(bserialized.storage_config)
        else:
            raise ValueError("unknown storage")

        # Load Embedder
        if bserialized.embedding_config.embedder_type == "openai_embedding":
            from langchain_openai import OpenAIEmbeddings

            embedder = OpenAIEmbeddings(**bserialized.embedding_config.config)
        else:
            raise ValueError("unknown embedder")

        # Load vector db
        if bserialized.vectordb_config.vectordb_type == "faiss":
            from langchain_community.vectorstores import FAISS

            vector_db = FAISS.load_local(
                folder_path=bserialized.vectordb_config.vectordb_folder_path,
                embeddings=embedder,
                allow_dangerous_deserialization=True,
            )
        else:
            raise ValueError("Unsupported vectordb")

        return cls(
            id=bserialized.id,
            name=bserialized.name,
            embedder=embedder,
            llm=LLMEndpoint.from_config(bserialized.llm_config),
            storage=storage,
            vector_db=vector_db,
        )

    async def save(self, folder_path: str | Path):
        """
        Save the brain to a folder path.
        Args:
            folder_path (str | Path): The path to the folder where the brain will be saved.
        Returns:
            str: The path to the folder where the brain was saved.
        Example:
        ```python
        await brain.save("path/to/brain")
        ```
        """
        if isinstance(folder_path, str):
            folder_path = Path(folder_path)

        brain_path = os.path.join(folder_path, f"brain_{self.id}")
        os.makedirs(brain_path, exist_ok=True)

        from langchain_community.vectorstores import FAISS

        if isinstance(self.vector_db, FAISS):
            vectordb_path = os.path.join(brain_path, "vector_store")
            os.makedirs(vectordb_path, exist_ok=True)
            self.vector_db.save_local(folder_path=vectordb_path)
            vector_store = FAISSConfig(vectordb_folder_path=vectordb_path)
        else:
            raise Exception("can't serialize other vector stores for now")

        if isinstance(self.embedder, OpenAIEmbeddings):
            embedder_config = EmbedderConfig(
                config=self.embedder.dict(exclude={"openai_api_key"})
            )
        else:
            raise Exception("can't serialize embedder other than openai for now")

        storage_config: Union[LocalStorageConfig, TransparentStorageConfig]
        # TODO : each instance should know how to serialize/deserialize itself
        if isinstance(self.storage, LocalStorage):
            serialized_files = {
                f.id: f.serialize() for f in await self.storage.get_files()
            }
            storage_config = LocalStorageConfig(
                storage_path=self.storage.dir_path, files=serialized_files
            )
        elif isinstance(self.storage, TransparentStorage):
            serialized_files = {
                f.id: f.serialize() for f in await self.storage.get_files()
            }
            storage_config = TransparentStorageConfig(files=serialized_files)
        else:
            raise Exception("can't serialize storage. not supported for now")

        bserialized = BrainSerialized(
            id=self.id,
            name=self.name,
            chat_history=self.chat_history.get_chat_history(),
            llm_config=self.llm.get_config(),
            vectordb_config=vector_store,
            embedding_config=embedder_config,
            storage_config=storage_config,
        )

        with open(os.path.join(brain_path, "config.json"), "w") as f:
            _lineaje_payload = bserialized.model_dump_json()
            # LINEAJE: enforce() `_lineaje_payload` at agent->file file_write — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:87683b6b1a4f0a293731b39b2ae0867b1f05c57cda01349be83c9eb41189b5a8'
            _gr_client = _lineaje_load_gr_client()
            _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:87683b6b1a4f0a293731b39b2ae0867b1f05c57cda01349be83c9eb41189b5a8', phase='file_write', boundary={'source': 'agent_message', 'sink': 'file_content'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='file', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'core/quivr_core/brain/brain.py', 'line': 13, 'name': 'OpenAIEmbeddings'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'OpenAIEmbeddings', 'version': '1.0.0', 'purl': 'pkg:aiagent/OpenAIEmbeddings@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/brain/brain.py', 'line': 271, 'function': 'Brain.save'}})
            try:
                _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json', variable_name='_lineaje_payload', source_file=__file__, before_line=271))
            except _gr_client.GuardrailUnavailableError:
                pass
            f.write(_lineaje_payload)
        # LINEAJE: enforce() `brain_path` at agent->user_interface data_egress — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:9164ca246d5e66e207c4f47febb7a28670e505a1420b76f4d13cd69eb5e5c882'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:9164ca246d5e66e207c4f47febb7a28670e505a1420b76f4d13cd69eb5e5c882', phase='data_egress', boundary={'source': 'agent_message', 'sink': 'user_interface'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='user_interface', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'core/quivr_core/brain/brain.py', 'line': 13, 'name': 'OpenAIEmbeddings'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'OpenAIEmbeddings', 'version': '1.0.0', 'purl': 'pkg:aiagent/OpenAIEmbeddings@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/brain/brain.py', 'line': 272, 'function': 'Brain.save'}})
        try:
            brain_path = _gr_client.enforce(_gr_site, brain_path, content_type='text/plain')
        except _gr_client.GuardrailUnavailableError:
            pass
        except PermissionError:
            pass
        return brain_path

    def info(self) -> BrainInfo:
        # TODO: dim of embedding
        # "embedder": {},
        chats_info = ChatHistoryInfo(
            nb_chats=len(self._chats),
            current_default_chat=self.default_chat.id,
            current_chat_history_length=len(self.default_chat),
        )

        return BrainInfo(
            brain_id=self.id,
            brain_name=self.name,
            files_info=self.storage.info() if self.storage else None,
            chats_info=chats_info,
            llm_info=self.llm.info(),
        )

    @property
    def chat_history(self) -> ChatHistory:
        return self.default_chat

    def _init_chats(self) -> Dict[UUID, ChatHistory]:
        chat_id = uuid4()
        default_chat = ChatHistory(chat_id=chat_id, brain_id=self.id)
        return {chat_id: default_chat}

    @classmethod
    async def afrom_files(
        cls,
        *,
        name: str,
        file_paths: list[str | Path],
        vector_db: VectorStore | None = None,
        storage: StorageBase = TransparentStorage(),
        llm: LLMEndpoint | None = None,
        embedder: Embeddings | None = None,
        skip_file_error: bool = False,
        processor_kwargs: dict[str, Any] | None = None,
    ):
        """
        Create a brain from a list of file paths.
        Args:
            name (str): The name of the brain.
            file_paths (list[str | Path]): The list of file paths to add to the brain.
            vector_db (VectorStore | None): The vector store used to store the processed files.
            storage (StorageBase): The storage used to store the files.
            llm (LLMEndpoint | None): The language model used to generate the answer.
            embedder (Embeddings | None): The embeddings used to create the index of the processed files.
            skip_file_error (bool): Whether to skip files that cannot be processed.
            processor_kwargs (dict[str, Any] | None): Additional arguments for the processor.
        Returns:
            Brain: The brain created from the file paths.
        Example:
        ```python
        brain = await Brain.afrom_files(name="My Brain", file_paths=["file1.pdf", "file2.pdf"])
        brain.print_info()
        ```
        """
        if llm is None:
            llm = default_llm()

        if embedder is None:
            embedder = default_embedder()

        processor_kwargs = processor_kwargs or {}

        brain_id = uuid4()

        # TODO: run in parallel using tasks

        for path in file_paths:
            file = await load_qfile(brain_id, path)
            await storage.upload_file(file)

        _lineaje_payload = f"uploaded all files to {storage}"
        # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:9e8c4ba7bfa74eb2a9279c72bd250bc8f92b86675b4f77898639b31fd41553b6'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:9e8c4ba7bfa74eb2a9279c72bd250bc8f92b86675b4f77898639b31fd41553b6', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'core/quivr_core/brain/brain.py', 'line': 13, 'name': 'OpenAIEmbeddings'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'OpenAIEmbeddings', 'version': '1.0.0', 'purl': 'pkg:aiagent/OpenAIEmbeddings@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/brain/brain.py', 'line': 348, 'function': 'Brain.afrom_files'}})
        try:
            _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json'))
        except _gr_client.GuardrailUnavailableError:
            pass
        except PermissionError:
            pass
        logger.debug(_lineaje_payload)

        # Parse files
        docs = await process_files(
            storage=storage,
            skip_file_error=skip_file_error,
            **processor_kwargs,
        )

        # Building brain's vectordb
        if vector_db is None:
            vector_db = await build_default_vectordb(docs, embedder)
        else:
            # LINEAJE: enforce() `docs` at agent->external pre_tool — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:c347c4d0b54401dcea07e39c22ee26350edcb1cd17d20b5810fc494a18bef3e4'
            _gr_client = _lineaje_load_gr_client()
            _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:c347c4d0b54401dcea07e39c22ee26350edcb1cd17d20b5810fc494a18bef3e4', phase='pre_tool', boundary={'source': 'rag_pipeline', 'sink': 'vector_store'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='external', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'core/quivr_core/brain/brain.py', 'line': 13, 'name': 'OpenAIEmbeddings'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'OpenAIEmbeddings', 'version': '1.0.0', 'purl': 'pkg:aiagent/OpenAIEmbeddings@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/brain/brain.py', 'line': 361, 'function': 'Brain.afrom_files'}})
            try:
                docs = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, docs, content_type='application/json', variable_name='docs', source_file=__file__, before_line=361))
            except _gr_client.GuardrailUnavailableError:
                pass
            await vector_db.aadd_documents(docs)

        _lineaje_payload = f"added {len(docs)} chunks to vectordb"
        # LINEAJE: enforce() `_lineaje_payload` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:9ec5307255e0f9ad9284be09a004d251b1bd9de36a21d89589b2dbdee4b82a66'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:9ec5307255e0f9ad9284be09a004d251b1bd9de36a21d89589b2dbdee4b82a66', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'core/quivr_core/brain/brain.py', 'line': 13, 'name': 'OpenAIEmbeddings'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'OpenAIEmbeddings', 'version': '1.0.0', 'purl': 'pkg:aiagent/OpenAIEmbeddings@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/brain/brain.py', 'line': 363, 'function': 'Brain.afrom_files'}})
        try:
            _lineaje_payload = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, _lineaje_payload, content_type='application/json'))
        except _gr_client.GuardrailUnavailableError:
            pass
        except PermissionError:
            pass
        logger.debug(_lineaje_payload)

        return cls(
            id=brain_id,
            name=name,
            storage=storage,
            llm=llm,
            embedder=embedder,
            vector_db=vector_db,
        )

    @classmethod
    def from_files(
        cls,
        *,
        name: str,
        file_paths: list[str | Path],
        vector_db: VectorStore | None = None,
        storage: StorageBase = TransparentStorage(),
        llm: LLMEndpoint | None = None,
        embedder: Embeddings | None = None,
        skip_file_error: bool = False,
        processor_kwargs: dict[str, Any] | None = None,
    ) -> Self:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(
            cls.afrom_files(
                name=name,
                file_paths=file_paths,
                vector_db=vector_db,
                storage=storage,
                llm=llm,
                embedder=embedder,
                skip_file_error=skip_file_error,
                processor_kwargs=processor_kwargs,
            )
        )

    @classmethod
    async def afrom_langchain_documents(
        cls,
        *,
        name: str,
        langchain_documents: list[Document],
        vector_db: VectorStore | None = None,
        storage: StorageBase = TransparentStorage(),
        llm: LLMEndpoint | None = None,
        embedder: Embeddings | None = None,
    ) -> Self:
        """
        Create a brain from a list of langchain documents.
        Args:
            name (str): The name of the brain.
            langchain_documents (list[Document]): The list of langchain documents to add to the brain.
            vector_db (VectorStore | None): The vector store used to store the processed files.
            storage (StorageBase): The storage used to store the files.
            llm (LLMEndpoint | None): The language model used to generate the answer.
            embedder (Embeddings | None): The embeddings used to create the index of the processed files.
        Returns:
            Brain: The brain created from the langchain documents.
        Example:
        ```python
        from langchain_core.documents import Document
        documents = [Document(page_content="Hello, world!")]
        brain = await Brain.afrom_langchain_documents(name="My Brain", langchain_documents=documents)
        brain.print_info()
        ```
        """

        if llm is None:
            llm = default_llm()

        if embedder is None:
            embedder = default_embedder()

        brain_id = uuid4()

        # Building brain's vectordb
        if vector_db is None:
            vector_db = await build_default_vectordb(langchain_documents, embedder)
        else:
            # LINEAJE: enforce() `langchain_documents` at agent->external pre_tool — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:7a7bf7778338d99d7a547dc5bc5e9dde5c34db2ade774c8a7140a17f12455d7d'
            _gr_client = _lineaje_load_gr_client()
            _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:7a7bf7778338d99d7a547dc5bc5e9dde5c34db2ade774c8a7140a17f12455d7d', phase='pre_tool', boundary={'source': 'rag_pipeline', 'sink': 'vector_store'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='external', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'core/quivr_core/brain/brain.py', 'line': 13, 'name': 'OpenAIEmbeddings'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'OpenAIEmbeddings', 'version': '1.0.0', 'purl': 'pkg:aiagent/OpenAIEmbeddings@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/brain/brain.py', 'line': 444, 'function': 'Brain.afrom_langchain_documents'}})
            try:
                langchain_documents = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, langchain_documents, content_type='application/json', variable_name='langchain_documents', source_file=__file__, before_line=444))
            except _gr_client.GuardrailUnavailableError:
                pass
            await vector_db.aadd_documents(langchain_documents)

        return cls(
            id=brain_id,
            name=name,
            storage=storage,
            llm=llm,
            embedder=embedder,
            vector_db=vector_db,
        )

    async def asearch(
        self,
        query: str | Document,
        n_results: int = 5,
        filter: Callable | Dict[str, Any] | None = None,
        fetch_n_neighbors: int = 20,
    ) -> list[SearchResult]:
        """
        Search for relevant documents in the brain based on a query.
        Args:
            query (str | Document): The query to search for.
            n_results (int): The number of results to return.
            filter (Callable | Dict[str, Any] | None): The filter to apply to the search.
            fetch_n_neighbors (int): The number of neighbors to fetch.
        Returns:
            list[SearchResult]: The list of retrieved chunks.
        Example:
        ```python
        brain = Brain.from_files(name="My Brain", file_paths=["file1.pdf", "file2.pdf"])
        results = await brain.asearch("Why everybody loves Quivr?")
        for result in results:
            print(result.chunk.page_content)
        ```
        """
        if not self.vector_db:
            raise ValueError("No vector db configured for this brain")

        result = await self.vector_db.asimilarity_search_with_score(
            query, k=n_results, filter=filter, fetch_k=fetch_n_neighbors
        )
        # LINEAJE: enforce() `result` at agent->external post_tool — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:ae1aad6c610e718a7c20228ab14682be985a534ec571c9b4650fda8030408618'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:ae1aad6c610e718a7c20228ab14682be985a534ec571c9b4650fda8030408618', phase='post_tool', boundary={'source': 'vector_store', 'sink': 'agent_context'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='external', project='', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'source': {'entity_type': 'agent', 'unique_org_id': 'vdna_Zaf1x0VOTwdhYyf8', 'repository_uri': 'https://github.com/lineaje-demo/quivr', 'file_path': 'core/quivr_core/brain/brain.py', 'line': 13, 'name': 'OpenAIEmbeddings'}, 'identity': {'source': {'entity_type': 'aiagent', 'name': 'OpenAIEmbeddings', 'version': '1.0.0', 'purl': 'pkg:aiagent/OpenAIEmbeddings@1.0.0'}, 'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'core/quivr_core/brain/brain.py', 'line': 482, 'function': 'Brain.asearch'}})
        try:
            result = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, result, content_type='application/json', variable_name='result', source_file=__file__, before_line=482))
        except _gr_client.GuardrailUnavailableError:
            pass

        return [SearchResult(chunk=d, distance=s) for d, s in result]

    def get_chat_history(self, chat_id: UUID):
        return self._chats[chat_id]

    # TODO(@aminediro)
    def add_file(self) -> None:
        # add it to storage
        # add it to vectorstore
        raise NotImplementedError

    async def ask_streaming(
        self,
        question: str,
        run_id: UUID,
        system_prompt: str | None = None,
        retrieval_config: RetrievalConfig | None = None,
        rag_pipeline: Type[Union[QuivrQARAG, QuivrQARAGLangGraph]] | None = None,
        list_files: list[QuivrKnowledge] | None = None,
        chat_history: ChatHistory | None = None,
        **input_kwargs,
    ) -> AsyncGenerator[ParsedRAGChunkResponse, ParsedRAGChunkResponse]:
        """
        Ask a question to the brain and get a streamed generated answer.
        Args:
            question (str): The question to ask.
            retrieval_config (RetrievalConfig | None): The retrieval configuration (see RetrievalConfig docs).
            rag_pipeline (Type[Union[QuivrQARAG, QuivrQARAGLangGraph]] | None): The RAG pipeline to use.
        list_files (list[QuivrKnowledge] | None): The list of files to include in the RAG pipeline.
            chat_history (ChatHistory | None): The chat history to use.
        Returns:
            AsyncGenerator[ParsedRAGChunkResponse, ParsedRAGChunkResponse]: The streamed generated answer.
        Example:
        ```python
        brain = Brain.from_files(name="My Brain", file_paths=["file1.pdf", "file2.pdf"])
        async for chunk in brain.ask_streaming("What is the meaning of life?"):
            print(chunk.answer)
        ```
        """
        llm = self.llm

        # If you passed a different llm model we'll override the brain  one
        if retrieval_config:
            if retrieval_config.llm_config != self.llm.get_config():
                llm = LLMEndpoint.from_config(config=retrieval_config.llm_config)
        else:
            retrieval_config = RetrievalConfig(llm_config=self.llm.get_config())

        rag_instance = QuivrQARAGLangGraph(
            retrieval_config=retrieval_config, llm=llm, vector_store=self.vector_db
        )

        chat_history = self.default_chat if chat_history is None else chat_history
        list_files = [] if list_files is None else list_files

        full_answer = ""

        metadata = LangchainMetadata(
            langfuse_trace_id=str(run_id),
            langfuse_user_id=str(self.workspace_id),
            langfuse_session_id=str(self.chat_id),
        )

        async for response in rag_instance.answer_astream(
            run_id=run_id,
            question=question,
            system_prompt=system_prompt or None,
            history=chat_history,
            list_files=list_files,
            metadata=metadata,
            **input_kwargs,
        ):
            # Format output to be correct servicedf;j
            if not response.last_chunk:
                yield response
            full_answer += response.answer

        # TODO : add sources, metdata etc  ...
        chat_history.append(HumanMessage(content=question))
        chat_history.append(AIMessage(content=full_answer))
        yield response

    async def aask(
        self,
        run_id: UUID,
        question: str,
        system_prompt: str | None = None,
        retrieval_config: RetrievalConfig | None = None,
        rag_pipeline: Type[Union[QuivrQARAG, QuivrQARAGLangGraph]] | None = None,
        list_files: list[QuivrKnowledge] | None = None,
        chat_history: ChatHistory | None = None,
        **input_kwargs,
    ) -> ParsedRAGResponse:
        """
        Synchronous version that asks a question to the brain and gets a generated answer.
        Args:
            question (str): The question to ask.
            retrieval_config (RetrievalConfig | None): The retrieval configuration (see RetrievalConfig docs).
            rag_pipeline (Type[Union[QuivrQARAG, QuivrQARAGLangGraph]] | None): The RAG pipeline to use.
            list_files (list[QuivrKnowledge] | None): The list of files to include in the RAG pipeline.
            chat_history (ChatHistory | None): The chat history to use.
        Returns:
            ParsedRAGResponse: The generated answer.
        """
        # question_language = detect_language(question) -- Commented until we use it
        full_answer = ""
        metadata = None

        async for response in self.ask_streaming(
            run_id=run_id,
            question=question,
            system_prompt=system_prompt,
            retrieval_config=retrieval_config,
            rag_pipeline=rag_pipeline,
            list_files=list_files,
            chat_history=chat_history,
            **input_kwargs,
        ):
            full_answer += response.answer
            if response.metadata:
                metadata = response.metadata

        return ParsedRAGResponse(answer=full_answer, metadata=metadata)

    def ask(
        self,
        run_id: UUID,
        question: str,
        system_prompt: str | None = None,
        retrieval_config: RetrievalConfig | None = None,
        rag_pipeline: Type[Union[QuivrQARAG, QuivrQARAGLangGraph]] | None = None,
        list_files: list[QuivrKnowledge] | None = None,
        chat_history: ChatHistory | None = None,
    ) -> ParsedRAGResponse:
        """
        Fully synchronous version that asks a question to the brain and gets a generated answer.
        Args:
            question (str): The question to ask.
            system_prompt (str | None): The system prompt to use.
            retrieval_config (RetrievalConfig | None): The retrieval configuration (see RetrievalConfig docs).
            rag_pipeline (Type[Union[QuivrQARAG, QuivrQARAGLangGraph]] | None): The RAG pipeline to use.
            list_files (list[QuivrKnowledge] | None): The list of files to include in the RAG pipeline.
            chat_history (ChatHistory | None): The chat history to use.
        Returns:
            ParsedRAGResponse: The generated answer.
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(
            self.aask(
                run_id=run_id,
                question=question,
                system_prompt=system_prompt,
                retrieval_config=retrieval_config,
                rag_pipeline=rag_pipeline,
                list_files=list_files,
                chat_history=chat_history,
            )
        )
