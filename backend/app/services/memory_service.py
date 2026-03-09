"""
长期记忆服务：按 user_id 隔离的向量存储

使用 Chroma 持久化，OpenAI 做 embedding。MemoryService.add(user_id, text, tags)、search(user_id, query, top_k)。
"""

import logging
import os
import uuid
from typing import List, Optional

from app.core.config import settings

logger = logging.getLogger("uvicorn")

_COLLECTION_NAME = "alphabot_memory"
_client = None
_embedding_fn = None


def _get_client():
    global _client
    if _client is None:
        try:
            import chromadb
            path = os.path.abspath(settings.CHROMA_PERSIST_PATH)
            os.makedirs(path, exist_ok=True)
            _client = chromadb.PersistentClient(path=path)
        except Exception as e:
            logger.warning("Chroma 初始化失败: %s", e)
    return _client


def _get_embedding_function():
    """返回 Chroma 可用的 embedding 函数。

    优先使用 EMBEDDING_* 配置，未设置时回退到 LLM_*，便于将聊天模型与向量模型解耦。
    """
    global _embedding_fn
    if _embedding_fn is not None:
        return _embedding_fn
    try:
        from chromadb.utils import embedding_functions
        # 优先使用专门的 EMBEDDING_API_KEY，其次回退到 LLM_API_KEY，
        # 并通过 api_key_env_var 告诉 Chroma 从哪个环境变量读取，避免直接传 api_key。
        embedding_key = (settings.EMBEDDING_API_KEY or "").strip()
        llm_key = (settings.LLM_API_KEY or "").strip()

        if embedding_key:
            env_var = "EMBEDDING_API_KEY"
        elif llm_key:
            env_var = "LLM_API_KEY"
        else:
            logger.warning(
                "Embedding 函数未配置 API key，请在环境变量 EMBEDDING_API_KEY 或 LLM_API_KEY 中提供密钥"
            )
            _embedding_fn = None
            return _embedding_fn

        base = (settings.EMBEDDING_API_BASE or settings.LLM_API_BASE or "").strip() or None
        _embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
            model_name=settings.EMBEDDING_MODEL,
            api_base=base,
            api_key_env_var=env_var,
        )
    except Exception as e:
        logger.warning("Embedding 函数初始化失败: %s", e)
        _embedding_fn = None
    return _embedding_fn


def _get_collection():
    client = _get_client()
    if client is None:
        return None
    ef = _get_embedding_function()
    if ef is None:
        return None
    return client.get_or_create_collection(
        name=_COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


class MemoryService:
    """长期记忆：add、search，按 user_id 隔离。"""

    @staticmethod
    def add(user_id: int, text: str, tags: Optional[List[str]] = None) -> bool:
        """写入一条记忆，按 user_id 隔离。"""
        if not text or not text.strip():
            return False
        coll = _get_collection()
        if coll is None:
            logger.warning("记忆服务不可用，跳过写入")
            return False
        try:
            doc_id = str(uuid.uuid4())
            meta = {"user_id": str(user_id), "tags": ",".join(tags) if tags else ""}
            coll.add(ids=[doc_id], documents=[text.strip()], metadatas=[meta])
            return True
        except Exception as e:
            logger.exception("MemoryService.add 失败: %s", e)
            return False

    @staticmethod
    def search(user_id: int, query: str, top_k: int = 5) -> List[dict]:
        """
        按 user_id 检索相关记忆，返回 [{"text": str, "metadata": dict, "distance": float}, ...]。
        若服务不可用返回 []。
        """
        if not query or not query.strip():
            return []
        coll = _get_collection()
        if coll is None:
            return []
        try:
            results = coll.query(
                query_texts=[query.strip()],
                n_results=top_k,
                where={"user_id": str(user_id)},
                include=["documents", "metadatas", "distances"],
            )
            out = []
            docs = (results.get("documents") or [[]])[0]
            metas = (results.get("metadatas") or [[]])[0]
            dists = (results.get("distances") or [[]])[0]
            for i, doc in enumerate(docs):
                out.append({
                    "text": doc or "",
                    "metadata": (metas[i] if i < len(metas) else {}) or {},
                    "distance": dists[i] if i < len(dists) else None,
                })
            return out
        except Exception as e:
            logger.exception("MemoryService.search 失败: %s", e)
            return []
