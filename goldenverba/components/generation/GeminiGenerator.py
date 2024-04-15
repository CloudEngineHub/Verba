import asyncio
import os
from collections.abc import Iterator
import vertexai
from vertexai.preview.generative_models import GenerativeModel
from dotenv import load_dotenv

from goldenverba.components.generation.interface import Generator

load_dotenv()


class GPT4Generator(Generator):
    """
    Gemini Generator.
    """

    def __init__(self):
        super().__init__()
        self.name = "GeminiGenerator"
        self.description = "Generator using Google's Gemini 1.5 Pro model"
        self.requires_library = ["google-cloud-aiplatform"]
        self.requires_env = ["GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT"]
        self.streamable = True
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro-preview-0409")
        self.context_window = 10000

    async def generate(
        self,
        queries: list[str],
        context: list[str],
        conversation: dict = None,
    ) -> str:
        """Generate an answer based on a list of queries and list of contexts, and includes conversational context
        @parameter: queries : list[str] - List of queries
        @parameter: context : list[str] - List of contexts
        @parameter: conversation : dict - Conversational context
        @returns str - Answer generated by the Generator.
        """
        if conversation is None:
            conversation = {}
        messages = self.prepare_messages(queries, context, conversation)

        try:

            project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

            REGION = "us-central1"
            vertexai.init(project=project_id, location=REGION)

            chat_completion_arguments = {"model": self.model_name, "messages": messages}
            if openai.api_type == "azure":
                chat_completion_arguments["deployment_id"] = self.model_name

            base_url = os.environ.get("OPENAI_BASE_URL", "")
            if base_url:
                openai.api_base = base_url

            completion = await asyncio.to_thread(
                openai.ChatCompletion.create, **chat_completion_arguments
            )
            system_msg = str(completion["choices"][0]["message"]["content"])

        except Exception:
            raise

        return system_msg

    async def generate_stream(
        self,
        queries: list[str],
        context: list[str],
        conversation: dict = None,
    ) -> Iterator[dict]:
        """Generate a stream of response dicts based on a list of queries and list of contexts, and includes conversational context
        @parameter: queries : list[str] - List of queries
        @parameter: context : list[str] - List of contexts
        @parameter: conversation : dict - Conversational context
        @returns Iterator[dict] - Token response generated by the Generator in this format {system:TOKEN, finish_reason:stop or empty}.
        """
        if conversation is None:
            conversation = {}
        messages = self.prepare_messages(queries, context, conversation)

        try:
            import openai

            openai.api_key = os.getenv("OPENAI_API_KEY")
            base_url = os.environ.get("OPENAI_BASE_URL", "")
            if base_url:
                openai.api_base = base_url

            if "OPENAI_API_TYPE" in os.environ:
                openai.api_type = os.getenv("OPENAI_API_TYPE")
            if "OPENAI_API_BASE" in os.environ:
                openai.api_base = os.getenv("OPENAI_API_BASE")
            if "OPENAI_API_VERSION" in os.environ:
                openai.api_version = os.getenv("OPENAI_API_VERSION")

            chat_completion_arguments = {
                "model": self.model_name,
                "messages": messages,
                "stream": True,
                "temperature": 0.0,
            }
            if openai.api_type == "azure":
                chat_completion_arguments["deployment_id"] = self.model_name

            completion = await openai.ChatCompletion.acreate(
                **chat_completion_arguments
            )

            try:
                while True:
                    chunk = await completion.__anext__()
                    if len(chunk["choices"]) > 0:
                        if "content" in chunk["choices"][0]["delta"]:
                            yield {
                                "message": chunk["choices"][0]["delta"]["content"],
                                "finish_reason": chunk["choices"][0]["finish_reason"],
                            }
                        else:
                            yield {
                                "message": "",
                                "finish_reason": chunk["choices"][0]["finish_reason"],
                            }
            except StopAsyncIteration:
                pass

        except Exception:
            raise

    def prepare_messages(
        self, queries: list[str], context: list[str], conversation: dict[str, str]
    ) -> dict[str, str]:
        """
        Prepares a list of messages formatted for a Retrieval Augmented Generation chatbot system, including system instructions, previous conversation, and a new user query with context.

        @parameter queries: A list of strings representing the user queries to be answered.
        @parameter context: A list of strings representing the context information provided for the queries.
        @parameter conversation: A list of previous conversation messages that include the role and content.

        @returns A list of message dictionaries formatted for the chatbot. This includes an initial system message, the previous conversation messages, and the new user query encapsulated with the provided context.

        Each message in the list is a dictionary with 'role' and 'content' keys, where 'role' is either 'system' or 'user', and 'content' contains the relevant text. This will depend on the LLM used.
        """
        messages = [
            {
                "role": "system",
                "content": "You are Verba, The Golden RAGtriever, a chatbot for Retrieval Augmented Generation (RAG). You will receive a user query and context pieces that have a semantic similarity to that specific query. Please answer these user queries only their provided context. If the provided documentation does not provide enough information, say so. If the user asks questions about you as a chatbot specifially, answer them naturally. If the answer requires code examples encapsulate them with ```programming-language-name ```. Don't do pseudo-code.",
            }
        ]

        for message in conversation:
            messages.append({"role": message.type, "content": message.content})

        query = " ".join(queries)
        user_context = " ".join(context)

        messages.append(
            {
                "role": "user",
                "content": f"Please answer this query: '{query}' with this provided context: {user_context}",
            }
        )

        return messages
