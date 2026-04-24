"""
Document fixtures for RAG platform tests.

Contains sample documents in various formats (text, PDF, HTML, Markdown)
for testing document processing and retrieval functionality.
"""

from typing import Dict, Any, List


ENGLISH_NEWS_SAMPLE = """
Breaking: New AI Model Achieves Human-Level Performance

San Francisco, CA - Researchers at TechLabs announced today that their latest
artificial intelligence model has achieved human-level performance on a
comprehensive set of reasoning tasks. The model, named Atlas-7, demonstrates
remarkable capabilities in natural language understanding, mathematical
reasoning, and code generation.

"This represents a significant milestone in AI development," said Dr. Sarah Chen,
lead researcher on the project. "Atlas-7 can now handle complex multi-step
reasoning tasks that were previously challenging for AI systems."

The model was trained on a diverse dataset spanning scientific papers, code
repositories, and educational materials. Early testing shows particular
strength in areas requiring logical deduction and creative problem-solving.

Industry analysts predict this advancement could accelerate AI adoption across
healthcare, finance, and education sectors. However, experts also emphasize
the importance of responsible deployment and ongoing safety research.
"""

ENGLISH_TECHNICAL_SAMPLE = """
# Technical Architecture Overview

## System Components

The RAG platform consists of three primary layers:

1. **Ingestion Layer**: Handles document upload, parsing, and chunking
2. **Retrieval Layer**: Manages vector storage and similarity search
3. **Generation Layer**: Interfaces with LLMs for answer synthesis

## Data Flow

Documents enter through the ingestion pipeline where they are:
- Parsed into structured text
- Split into overlapping chunks
- Embedded using sentence transformers
- Stored in the vector database

## Vector Database Options

| Database  | Use Case           | Scalability |
|----------|-------------------|-------------|
| SQLite   | Development/Small | Low         |
| PGVector | Production/Medium | Medium      |
| Elastic  | Enterprise/Large  | High        |

## Performance Considerations

- Chunk size: 256-512 tokens recommended
- Overlap: 10-20% for context preservation
- Embedding dimension: 1536 for OpenAI, 768 for open-source models
"""

ENGLISH_MIXED_SAMPLE = """
Project Update: Customer Portal Redesign

Team,
We've completed Phase 1 of the customer portal redesign. Here's the summary:

**Completed Tasks:**
- New dashboard UI with React 18
- API integration with FastAPI backend
- Authentication via OAuth 2.0

**Technical Details:**
The frontend uses Next.js 14 with the App Router pattern. State management
is handled by Zustand, and we're using Tailwind CSS for styling.

```python
# Example API endpoint
@app.get("/api/v1/users/{user_id}")
async def get_user(user_id: str):
    return await user_service.get(user_id)
```

**Next Steps:**
1. Performance optimization (target: < 200ms response time)
2. Mobile responsiveness testing
3. Security audit scheduled for next week

Questions? Reach out to the dev team on Slack #portal-redesign.

Best,
Alex
"""

SAMPLE_PDF_CONTENT = {
    "filename": "research_paper.pdf",
    "content_type": "application/pdf",
    "text_content": ENGLISH_TECHNICAL_SAMPLE,
    "metadata": {
        "pages": 5,
        "author": "Research Team",
        "created": "2024-01-15",
    },
}

SAMPLE_HTML_CONTENT = {
    "filename": "documentation.html",
    "content_type": "text/html",
    "text_content": """
<!DOCTYPE html>
<html>
<head><title>API Documentation</title></head>
<body>
<h1>API Reference</h1>
<h2>Authentication</h2>
<p>All API requests require a Bearer token in the Authorization header.</p>
<h2>Endpoints</h2>
<ul>
<li>GET /api/v1/documents - List all documents</li>
<li>POST /api/v1/documents - Create new document</li>
<li>GET /api/v1/search - Search documents</li>
</ul>
</body>
</html>
""",
    "metadata": {
        "source_url": "https://docs.example.com/api",
    },
}

SAMPLE_MARKDOWN_CONTENT = {
    "filename": "readme.md",
    "content_type": "text/markdown",
    "text_content": ENGLISH_TECHNICAL_SAMPLE,
    "metadata": {
        "repository": "example/rag-platform",
    },
}


def get_sample_documents() -> List[Dict[str, Any]]:
    """Return list of sample documents for testing."""
    return [
        {
            "id": "doc-en-001",
            "title": "AI News Article",
            "content": ENGLISH_NEWS_SAMPLE.strip(),
            "metadata": {"language": "en", "type": "news"},
        },
        {
            "id": "doc-en-002",
            "title": "Technical Architecture",
            "content": ENGLISH_TECHNICAL_SAMPLE.strip(),
            "metadata": {"language": "en", "type": "technical"},
        },
        {
            "id": "doc-en-003",
            "title": "Project Update",
            "content": ENGLISH_MIXED_SAMPLE.strip(),
            "metadata": {"language": "en", "type": "mixed"},
        },
    ]


def get_multiformat_documents() -> List[Dict[str, Any]]:
    """Return documents in various formats for format testing."""
    return [
        SAMPLE_PDF_CONTENT,
        SAMPLE_HTML_CONTENT,
        SAMPLE_MARKDOWN_CONTENT,
    ]
