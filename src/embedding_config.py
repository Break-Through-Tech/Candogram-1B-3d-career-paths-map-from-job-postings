"""Shared settings and request helper for job, profile, and goal embeddings."""

import numpy as np
from google import genai
from google.genai import types

MODEL_NAME = "gemini-embedding-2"
MODEL_MAX_INPUT_TOKENS = 8192
EMBEDDING_DIMENSIONS = 1536
QUERY_TASK_PREFIX = "task: search result | query: "


def embed_text(client: genai.Client, text: str) -> np.ndarray:
    # Gemini silently truncates over-limit input. Short UTF-8 inputs fit without
    # a separate token-count request.
    if len(text.encode("utf-8")) > MODEL_MAX_INPUT_TOKENS - 2:
        tokens = client.models.count_tokens(
            model=MODEL_NAME, contents=text
        ).total_tokens
        if tokens > MODEL_MAX_INPUT_TOKENS:
            raise ValueError(
                f"Embedding input has {tokens} tokens; "
                f"{MODEL_NAME} accepts at most {MODEL_MAX_INPUT_TOKENS}"
            )
    response = client.models.embed_content(
        model=MODEL_NAME,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
    )
    vector = np.asarray(response.embeddings[0].values, dtype=np.float32)
    return vector / np.linalg.norm(vector)
