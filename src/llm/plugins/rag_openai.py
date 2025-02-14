import logging
import time
import typing as T
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
import uuid

import openai
from pydantic import BaseModel

from llm import LLM, LLMConfig

R = T.TypeVar("R", bound=BaseModel)


class OpenAILLMv2(LLM[R]):
    """
    An OpenAI-based Language Learning Model implementation.

    This class implements the LLM interface for OpenAI's GPT models, handling
    configuration, authentication, and async API communication.

    Parameters
    ----------
    output_model : Type[R]
        A Pydantic BaseModel subclass defining the expected response structure.
    config : LLMConfig, optional
        Configuration object containing API settings. If not provided, defaults
        will be used.
    """

    def __init__(self, output_model: T.Type[R], config: T.Optional[LLMConfig] = None):
        """
        Initialize the OpenAI LLM instance.

        Parameters
        ----------
        output_model : Type[R]
            Pydantic model class for response validation.
        config : LLMConfig, optional
            Configuration settings for the LLM.
        """
        super().__init__(output_model, config)
        
        self.embedding_model = getattr(config, "embedding_model", "text-embedding-3-large")
        self.doc_directory = config.doc_directory
        self.api_key = config.openai_api_key
        self.question = config.question
        
        self.embeddings = OpenAIEmbeddings(model=self.embedding_model, api_key=self.api_key)
        base_url = config.base_url or "https://api.openmind.org/api/core/openai"

        if config.api_key is None or config.api_key == "":
            raise ValueError("config file missing api_key")
        else:
            api_key = config.api_key

        client_kwargs = {}
        client_kwargs["base_url"] = base_url
        client_kwargs["api_key"] = api_key

        logging.info(f"Initializing OpenAI client with {client_kwargs}")
        self._client = openai.AsyncClient(**client_kwargs)

    async def ask(self, prompt: str) -> R | None:

        docsearch = FAISS.load_local(self.doc_directory, self.embeddings, allow_dangerous_deserialization=True)

        docsearch = docsearch.as_retriever(search_type="mmr", search_kwargs={"k": 4})
        retrieved_docs = docsearch.invoke(self.question)

        docs_content = "\n\n".join(doc.page_content for doc in retrieved_docs)

        prompt = f"Based on the context given below:\n {docs_content}\n Answer the question: {self.question}\n " 
        print("\n\nressss...\n\n")
        print(prompt)
        """
        Send a prompt to the OpenAI API and get a structured response.

        Parameters
        ----------
        prompt : str
            The input prompt to send to the model.

        Returns
        -------
        R or None
            Parsed response matching the output_model structure, or None if
            parsing fails.
        """
        try:
            logging.debug(f"OpenAI LLM input: {prompt}")
            self.io_provider.llm_start_time = time.time()
            self.io_provider.set_llm_prompt(prompt)

            parsed_response = await self._client.beta.chat.completions.parse(
                model=(
                    "gpt-4o-mini" if self._config.model is None else self._config.model
                ),
                messages=[{"role": "user", "content": prompt}],
                response_format=self._output_model,
            )

            message_content = parsed_response.choices[0].message.content
            self.io_provider.llm_end_time = time.time()
            
            print("\n\nressss...\n\n")
            print(message_content)

            try:
                parsed_response = self._output_model.model_validate_json(
                    message_content
                )
                logging.debug(f"LLM output: {parsed_response}")
                return parsed_response
            except Exception as e:
                logging.error(f"Error parsing response: {e}")
                return None
        except Exception as e:
            logging.error(f"Error asking LLM: {e}")
            return None
