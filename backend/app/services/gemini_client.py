"""Thin wrapper around the Google Gen AI SDK.

This is the only module that talks to Gemini. Everything above it depends on the
two methods `generate_text` and `embed`, which makes the AI boundary trivially
fakeable in tests.
"""

from functools import lru_cache

from fastapi import HTTPException, status

from app.config import get_settings


class GeminiClient:
    def __init__(self, api_key: str, model: str, embedding_model: str):
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set. Add it to backend/.env.")

        from google import genai  # imported lazily so tests without the key never touch it

        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self.model_name = model
        self.embedding_model = embedding_model

    def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        json_schema: dict | None = None,
    ) -> str:
        types = self._genai.types

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
            response_mime_type="application/json" if json_schema else None,
            response_json_schema=json_schema,
        )

        # Try the configured/primary model first.
        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )

        # If the primary model is temporarily unavailable, try the fallback.
        except Exception as exc:
            print(f"Primary Gemini model failed ({self.model_name}): {exc}")

            fallback_model = "gemini-3.5-flash"

            # Prevent an unnecessary second request if the fallback is already
            # configured as the primary model.
            if self.model_name == fallback_model:
                raise

            print(f"Trying fallback Gemini model: {fallback_model}")

            response = self._client.models.generate_content(
                model=fallback_model,
                contents=prompt,
                config=config,
            )

        text = response.text or ""

        if not text.strip():
            raise RuntimeError(
                "Gemini returned an empty response "
                "(possibly blocked by safety filters)."
            )

        return text

    def embed(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        types = self._genai.types
        out: list[list[float]] = []

        # The embeddings endpoint accepts batches; keep batches modest to stay
        # under request limits.
        for i in range(0, len(texts), 50):
            batch = texts[i : i + 50]

            res = self._client.models.embed_content(
                model=self.embedding_model,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=768,
                ),
            )

            out.extend([list(e.values) for e in res.embeddings])

        return out


@lru_cache
def _cached_client() -> GeminiClient:
    s = get_settings()

    return GeminiClient(
        api_key=s.gemini_api_key,
        model=s.gemini_model,
        embedding_model=s.gemini_embedding_model,
    )


def get_gemini() -> GeminiClient:
    """FastAPI dependency. Fails with a clear 503 if the key is missing."""
    try:
        return _cached_client()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc