"""
Phase 3 长期记忆 + 组合体检 测试

ROADMAP: T3.1 MemoryService | T3.2 Context 集成 | T3.3 save_investment_note | T3.4 get_portfolio_health
验收：add/search 按 user_id 隔离；get_portfolio_health 返回 labels/comment（组合体检在 phase1 已测）
"""
import pytest
from unittest.mock import patch, MagicMock

from app.services.memory_service import MemoryService


class TestMemoryService:
    """T3.1 MemoryService：add、search，按 user_id 隔离"""

    def test_add_empty_text_returns_false(self):
        """空文本不写入"""
        with patch("app.services.memory_service._get_collection", return_value=MagicMock()):
            ok = MemoryService.add(1, "")
            assert ok is False
        with patch("app.services.memory_service._get_collection", return_value=MagicMock()):
            ok = MemoryService.add(1, "   ")
            assert ok is False

    def test_add_when_collection_none_returns_false(self):
        """Chroma 不可用时 add 返回 False"""
        with patch("app.services.memory_service._get_collection", return_value=None):
            ok = MemoryService.add(1, "用户偏好保守")
            assert ok is False

    def test_add_success_when_collection_mocked(self):
        """有 collection 时 add 写入并返回 True"""
        mock_coll = MagicMock()
        with patch("app.services.memory_service._get_collection", return_value=mock_coll):
            ok = MemoryService.add(1, "我偏好保守投资", tags=["preference"])
            assert ok is True
            mock_coll.add.assert_called_once()
            call_kw = mock_coll.add.call_args
            assert call_kw[1]["documents"] == ["我偏好保守投资"]
            assert "user_id" in str(call_kw[1].get("metadatas", [{}])[0])

    def test_search_empty_query_returns_empty(self):
        """空 query 返回空列表"""
        result = MemoryService.search(1, "")
        assert result == []
        result = MemoryService.search(1, "   ")
        assert result == []

    def test_search_when_collection_none_returns_empty(self):
        """Chroma 不可用时 search 返回 []"""
        with patch("app.services.memory_service._get_collection", return_value=None):
            result = MemoryService.search(1, "风险偏好")
            assert result == []

    def test_search_returns_docs_with_user_id_filter(self):
        """search 使用 user_id 条件并返回 [{"text", "metadata", "distance"}]"""
        mock_coll = MagicMock()
        mock_coll.query.return_value = {
            "documents": [["用户偏好保守"]],
            "metadatas": [[{"user_id": "1", "tags": "preference"}]],
            "distances": [[0.1]],
        }
        with patch("app.services.memory_service._get_collection", return_value=mock_coll):
            result = MemoryService.search(1, "风险偏好", top_k=5)
            assert len(result) == 1
            assert result[0]["text"] == "用户偏好保守"
            assert "metadata" in result[0]
            assert result[0].get("distance") is not None
            mock_coll.query.assert_called_once()
            call_kw = mock_coll.query.call_args[1]
            assert call_kw["where"] == {"user_id": "1"}
            assert call_kw["n_results"] == 5
