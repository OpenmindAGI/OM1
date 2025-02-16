import asyncio
import logging
import os
import uuid
from queue import Empty, Queue
from typing import List, Optional

import aiohttp
import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.document_loaders import DirectoryLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from inputs.base import SensorConfig
from inputs.base.loop import FuserInput


class RAGInput(FuserInput[str]):
    """RAG input handler for OpenMind O1"""

    def __init__(self, config: Optional[SensorConfig] = None):
        super().__init__(config or SensorConfig())

        self.buffer: List[str] = []
        self.message_buffer: Queue[str] = Queue()
        self.context: Optional[str] = None
        self.session: Optional[aiohttp.ClientSession] = None

        # Configuration parameters
        self.doc_directory = getattr(config, "data_path", "./data")
        self.embedding_model = getattr(
            config, "embedding_model", "text-embedding-3-large"
        )
        self.api_key = getattr(config, "openai_api_key")
        self.chunk_size = getattr(config, "chunk_size")
        self.chunk_overlap = getattr(config, "chunk_overlap")

        self.embeddings = OpenAIEmbeddings(
            model=self.embedding_model, api_key=self.api_key
        )
        self.vector_store = self._initialize_vector_store()

    async def __aenter__(self):
        """Async context manager entry"""
        await self._init_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def _init_session(self):
        """Initialize aiohttp session if not exists."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=10)
            self.session = aiohttp.ClientSession(timeout=timeout)

    def _initialize_vector_store(self):
        """Initialize FAISS vector store with documents"""

        loader = DirectoryLoader(
            self.doc_directory, glob=["**/*.pdf", "**/*.txt", "**/*.md"]
        )
        docs = loader.load()

        # Split documents
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap
        )
        all_splits = text_splitter.split_documents(docs)

        # Create FAISS index
        index = faiss.IndexFlatL2(len(self.embeddings.embed_query("my_index")))

        vector_store = FAISS(
            embedding_function=self.embeddings,
            index=index,
            docstore=InMemoryDocstore(),
            index_to_docstore_id={},
        )

        # Add documents with UUIDs
        uuids = [str(uuid.uuid4()) for _ in range(len(all_splits))]
        vector_store.add_documents(documents=all_splits, ids=uuids)
        vector_store.save_local(f"{os.path.join(self.doc_directory, 'faiss_index')}")
        return vector_store

    async def _poll(self) -> Optional[str]:
        """
        Poll for new messages in the buffer.

        Returns
        -------
        Optional[str]
            Message from the buffer if available, None otherwise
        """
        await asyncio.sleep(0.5)
        try:
            message = self.message_buffer.get_nowait()
            return message
        except Empty:
            return None

    async def raw_to_text(self, raw_input: Optional[str] = None):
        """Convert raw input to text format and add to buffer.

        Parameters
        ----------
        raw_input : Optional[str]
            Raw input to process. If None, process from message buffer.

        Returns
        -------
        str
            The processed text
        """
        if raw_input:
            self.message_buffer.put_nowait(raw_input)

        if self.message_buffer:
            try:
                message = self.message_buffer.get_nowait()
                if message:
                    self.buffer.append(message)
                    logging.debug(f"Added to buffer: {message}")
                    return message
            except Empty:
                pass

        return ""

    async def _raw_to_text(self, raw_input: Optional[str] = None):
        """Convert raw input to text format and add to buffer.

        Parameters
        ----------
        raw_input : Optional[str]
            Raw input to process. If None, process from message buffer.

        Returns
        -------
        str
            The processed text
        """
        if raw_input:
            self.message_buffer.put_nowait(raw_input)

        if self.message_buffer:
            try:
                message = self.message_buffer.get_nowait()
                if message:
                    self.buffer.append(message)
                    logging.debug(f"Added to buffer: {message}")
                    return message
            except Empty:
                pass

        return ""

    async def start(self):
        """Start the input handler with initial query."""
        print("Creating store")
        await self._initialize_vector_store()
