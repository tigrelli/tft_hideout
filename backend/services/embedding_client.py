"""CHAT-02: 실시간 사용자 질문을 BGE-M3로 임베딩해 pgvector 검색 쿼리 벡터를
만든다.

batch/embeddings.py의 HuggingFaceEmbeddingClient와 로직이 동일하지만, Render에
배포되는 backend 서비스는 rootDir이 backend/로 제한돼 있어(render.yaml) batch/
쪽 코드를 임포트할 수 없다 — 그래서 이 파일에 필요한 부분만 복제해 둔다.
"""

from __future__ import annotations

import time
from typing import Self

import httpx

DEFAULT_HF_BASE_URL = "https://router.huggingface.co/hf-inference/models"
DEFAULT_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024


class EmbeddingError(Exception):
    """HF Inference API 호출 실패(HTTP 오류, 콜드스타트 재시도 소진 등)."""


class HuggingFaceEmbeddingClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_HF_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 2.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = f"{base_url}/{model}/pipeline/feature-extraction"
        self._api_key = api_key
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._http = httpx.Client(timeout=timeout, transport=transport)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """texts 순서 그대로 임베딩 벡터 리스트를 반환한다. 빈 입력은 빈 리스트."""
        if not texts:
            return []

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._http.post(
                    self._url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"inputs": texts, "options": {"wait_for_model": True}},
                )
                if response.status_code == 503:
                    # 무료 인프라 콜드스타트(모델 로딩 중) 대응(policies.md 9번)
                    last_error = EmbeddingError(f"모델 로딩 중(503): {response.text}")
                    if attempt < self._max_retries:
                        time.sleep(self._retry_backoff_seconds)
                        continue
                    raise last_error
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    time.sleep(self._retry_backoff_seconds)
        raise EmbeddingError(
            f"HF Inference API 요청 실패: {last_error}"
        ) from last_error

    def embed_one(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]
