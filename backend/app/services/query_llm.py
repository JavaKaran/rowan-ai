import os

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel

from app.exceptions import SQLGenerationFailed
from app.schemas import QueryTokenUsage


class GeneratedSQL(BaseModel):
    sql_query: str
    summary: str


class QueryGenerationResult(BaseModel):
    sql_query: str
    summary: str
    token_usage: QueryTokenUsage
    provider: str
    model_name: str


class LangChainGroqQueryLLMClient:
    def __init__(self, model_name: str, temperature: float = 0.0):
        self.model_name = model_name
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                ("user", "{prompt_text}"),
            ]
        )
        llm = ChatGroq(model_name=model_name, temperature=temperature)
        self.chain = self.prompt | llm.with_structured_output(GeneratedSQL, include_raw=True)

    def generate_sql(
        self,
        system_prompt: str,
        prompt_text: str,
    ) -> QueryGenerationResult:
        try:
            response = self.chain.invoke(
                {
                    "system_prompt": system_prompt,
                    "prompt_text": prompt_text,
                }
            )
        except Exception as exc:
            raise SQLGenerationFailed("Failed to generate SQL query.") from exc

        parsed = response.get("parsed")
        raw_message = response.get("raw")

        if parsed is None:
            raise SQLGenerationFailed("Model response could not be parsed.")

        sql_query = parsed.sql_query.strip()
        if not sql_query:
            raise SQLGenerationFailed("Model returned an empty SQL query.")

        summary = parsed.summary.strip()
        if not summary:
            raise SQLGenerationFailed("Model returned an empty query summary.")

        usage_metadata = getattr(raw_message, "usage_metadata", {}) or {}
        input_details = usage_metadata.get("input_token_details", {}) or {}

        return QueryGenerationResult(
            sql_query=sql_query,
            summary=summary,
            token_usage=QueryTokenUsage(
                total_tokens=usage_metadata.get("total_tokens", 0),
                input_tokens=usage_metadata.get("input_tokens", 0),
                output_tokens=usage_metadata.get("output_tokens", 0),
                cached_input_tokens=input_details.get("cache_read", 0) or 0,
            ),
            provider="groq",
            model_name=self.model_name,
        )


def create_query_llm_client() -> LangChainGroqQueryLLMClient:
    provider = os.getenv("QUERY_MODEL_PROVIDER", "groq").lower()
    model_name = os.getenv("QUERY_MODEL_NAME", "llama-3.3-70b-versatile")

    if provider == "groq":
        return LangChainGroqQueryLLMClient(model_name=model_name, temperature=0.0)

    raise ValueError(f"Unsupported QUERY_MODEL_PROVIDER: {provider}")
