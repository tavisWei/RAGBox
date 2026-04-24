"""
Shared pytest fixtures for RAG platform tests.
"""

import os
import sys
import pytest
from typing import Generator, Dict, Any, List

# Add project root directory to path for imports
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, project_root)

from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def test_config() -> Dict[str, Any]:
    """Test configuration fixture."""
    return {
        "database_url": "sqlite:///:memory:",
        "embedding_model": "text-embedding-ada-002",
        "chunk_size": 512,
        "chunk_overlap": 50,
        "top_k": 5,
    }


@pytest.fixture(scope="session")
def test_client() -> Generator[TestClient, None, None]:
    """FastAPI test client fixture."""
    from api.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_document() -> Dict[str, Any]:
    """Sample document fixture for testing."""
    return {
        "id": "test-doc-001",
        "title": "Test Document",
        "content": "This is a test document for RAG system testing.",
        "metadata": {
            "source": "test",
            "created_at": "2024-01-01T00:00:00Z",
        },
    }


@pytest.fixture
def sample_documents() -> List[Dict[str, Any]]:
    """Multiple sample documents fixture."""
    return [
        {
            "id": "doc-001",
            "title": "Introduction to RAG",
            "content": "RAG (Retrieval-Augmented Generation) combines retrieval and generation.",
            "metadata": {"category": "tech", "language": "en"},
        },
        {
            "id": "doc-002",
            "title": "Vector Databases",
            "content": "Vector databases store embeddings for semantic search.",
            "metadata": {"category": "tech", "language": "en"},
        },
        {
            "id": "doc-003",
            "title": "Machine Learning Basics",
            "content": "Machine learning enables computers to learn from data.",
            "metadata": {"category": "tech", "language": "en"},
        },
    ]


@pytest.fixture
def sample_query() -> str:
    """Sample query fixture."""
    return "What is RAG?"


@pytest.fixture
def sample_queries() -> List[str]:
    """Multiple sample queries fixture."""
    return [
        "What is RAG?",
        "How do vector databases work?",
        "Explain machine learning basics.",
    ]
