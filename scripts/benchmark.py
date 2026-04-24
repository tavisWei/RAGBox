"""
Performance benchmark script for the RAG Platform.

Measures document indexing throughput, query latency, and retrieval quality
across all three resource levels.

Usage:
    python scripts/benchmark.py --backend sqlite --docs 1000 --queries 100
    python scripts/benchmark.py --backend pgvector --docs 10000 --queries 500
    python scripts/benchmark.py --backend elasticsearch --docs 100000 --queries 1000
"""

import argparse
import os
import random
import string
import sys
import tempfile
import time
from typing import Any, Dict, List

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.core.rag.datasource.unified.base_data_store import Document, SearchResult
from api.core.rag.datasource.unified.data_store_factory import DataStoreFactory
from api.core.rag.retrieval.multi_way_retriever import MultiWayRetriever
from api.core.rag.retrieval.reranker import Reranker


def generate_random_text(length: int = 100) -> str:
    words = [
        "Python", "machine", "learning", "database", "search", "vector",
        "embedding", "retrieval", "index", "query", "document", "chunk",
        "semantic", "keyword", "fulltext", "hybrid", "fusion", "rank",
        "model", "training", "inference", "pipeline", "storage", "memory",
        "performance", "latency", "throughput", "concurrent", "scalable",
    ]
    return " ".join(random.choices(words, k=length // 5))


def generate_documents(count: int, dimension: int) -> tuple:
    docs = []
    embeddings = []
    for i in range(count):
        doc = Document(
            page_content=generate_random_text(),
            metadata={"doc_id": f"doc_{i}", "index": i},
        )
        docs.append(doc)
        vec = np.random.randn(dimension).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        embeddings.append(vec.tolist())
    return docs, embeddings


def benchmark_indexing(store, collection_name: str, docs: List[Document], embeddings: List[List[float]]) -> Dict[str, Any]:
    start = time.time()
    doc_ids = store.add_documents(collection_name, docs, embeddings)
    elapsed = time.time() - start
    return {
        "total_docs": len(doc_ids),
        "elapsed_seconds": elapsed,
        "docs_per_second": len(doc_ids) / elapsed if elapsed > 0 else 0,
    }


def benchmark_search(store, collection_name: str, queries: List[str], query_vectors: List[List[float]], top_k: int = 10) -> Dict[str, Any]:
    latencies = []
    results_counts = []

    for query, qvec in zip(queries, query_vectors):
        start = time.time()
        results = store.search(
            collection_name,
            query,
            query_vector=qvec,
            top_k=top_k,
            search_method="hybrid",
        )
        elapsed = time.time() - start
        latencies.append(elapsed * 1000)
        results_counts.append(len(results))

    return {
        "total_queries": len(queries),
        "avg_latency_ms": sum(latencies) / len(latencies),
        "min_latency_ms": min(latencies),
        "max_latency_ms": max(latencies),
        "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)],
        "avg_results": sum(results_counts) / len(results_counts),
    }


def benchmark_multi_way_retriever(store, collection_name: str, queries: List[str], query_vectors: List[List[float]], top_k: int = 10) -> Dict[str, Any]:
    retriever = MultiWayRetriever(data_store=store)
    latencies = []

    for query, qvec in zip(queries, query_vectors):
        start = time.time()
        results = retriever.retrieve(
            collection_name,
            query,
            query_vector=qvec,
            top_k=top_k,
            methods=["vector", "fulltext"],
        )
        elapsed = time.time() - start
        latencies.append(elapsed * 1000)

    return {
        "total_queries": len(queries),
        "avg_latency_ms": sum(latencies) / len(latencies),
        "min_latency_ms": min(latencies),
        "max_latency_ms": max(latencies),
        "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)],
    }


def benchmark_health_check(store, iterations: int = 100) -> Dict[str, Any]:
    start = time.time()
    for _ in range(iterations):
        store.health_check()
    elapsed = time.time() - start
    return {
        "iterations": iterations,
        "total_ms": elapsed * 1000,
        "per_check_ms": (elapsed / iterations) * 1000,
    }


def run_benchmark(backend: str, doc_count: int, query_count: int, dimension: int = 768) -> Dict[str, Any]:
    print(f"\n{'='*60}")
    print(f"Benchmarking: {backend}")
    print(f"Documents: {doc_count}, Queries: {query_count}, Dimension: {dimension}")
    print(f"{'='*60}")

    config = {}
    if backend == "sqlite":
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        config = {"db_path": db_path, "vector_enabled": True}
    elif backend == "pgvector":
        config = {
            "host": os.getenv("PGVECTOR_HOST", "localhost"),
            "port": int(os.getenv("PGVECTOR_PORT", "5432")),
            "database": os.getenv("PGVECTOR_DATABASE", "rag_platform"),
            "user": os.getenv("PGVECTOR_USER", "postgres"),
            "password": os.getenv("PGVECTOR_PASSWORD", "password"),
        }
    elif backend == "elasticsearch":
        config = {
            "hosts": [os.getenv("ELASTICSEARCH_HOSTS", "http://localhost:9200")],
        }

    store = DataStoreFactory.create(backend, config)
    collection_name = f"benchmark_{backend}"

    print("\n[1/5] Generating test data...")
    docs, embeddings = generate_documents(doc_count, dimension)
    queries = [generate_random_text(30) for _ in range(query_count)]
    query_vectors = [np.random.randn(dimension).astype(np.float32).tolist() for _ in range(query_count)]

    print("[2/5] Creating collection...")
    store.create_collection(collection_name, dimension=dimension)

    print("[3/5] Benchmarking indexing...")
    indexing_results = benchmark_indexing(store, collection_name, docs, embeddings)
    print(f"  Indexed {indexing_results['total_docs']} docs in {indexing_results['elapsed_seconds']:.2f}s")
    print(f"  Throughput: {indexing_results['docs_per_second']:.1f} docs/sec")

    print("[4/5] Benchmarking search...")
    search_results = benchmark_search(store, collection_name, queries, query_vectors)
    print(f"  Avg latency: {search_results['avg_latency_ms']:.2f}ms")
    print(f"  P95 latency: {search_results['p95_latency_ms']:.2f}ms")
    print(f"  Min/Max: {search_results['min_latency_ms']:.2f}ms / {search_results['max_latency_ms']:.2f}ms")

    print("[5/5] Benchmarking MultiWayRetriever...")
    retriever_results = benchmark_multi_way_retriever(store, collection_name, queries[:50], query_vectors[:50])
    print(f"  Avg latency: {retriever_results['avg_latency_ms']:.2f}ms")
    print(f"  P95 latency: {retriever_results['p95_latency_ms']:.2f}ms")

    print("\n[Bonus] Benchmarking health checks...")
    health_results = benchmark_health_check(store)
    print(f"  Per check: {health_results['per_check_ms']:.3f}ms")

    stats = store.get_stats(collection_name)
    print(f"\nCollection stats:")
    print(f"  Total documents: {stats.total_documents}")
    print(f"  Total chunks: {stats.total_chunks}")
    print(f"  Index size: {stats.index_size_bytes / 1024 / 1024:.2f} MB")

    store.delete_collection(collection_name)

    if backend == "sqlite":
        os.unlink(db_path)

    return {
        "backend": backend,
        "doc_count": doc_count,
        "query_count": query_count,
        "dimension": dimension,
        "indexing": indexing_results,
        "search": search_results,
        "retriever": retriever_results,
        "health_check": health_results,
        "stats": {
            "total_documents": stats.total_documents,
            "total_chunks": stats.total_chunks,
            "index_size_mb": stats.index_size_bytes / 1024 / 1024,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="RAG Platform Performance Benchmark")
    parser.add_argument("--backend", choices=["sqlite", "pgvector", "elasticsearch", "all"], default="sqlite", help="Backend to benchmark")
    parser.add_argument("--docs", type=int, default=1000, help="Number of documents to index")
    parser.add_argument("--queries", type=int, default=100, help="Number of queries to run")
    parser.add_argument("--dimension", type=int, default=768, help="Embedding dimension")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file for results")

    args = parser.parse_args()

    backends = ["sqlite", "pgvector", "elasticsearch"] if args.backend == "all" else [args.backend]

    all_results = []
    for backend in backends:
        try:
            result = run_benchmark(backend, args.docs, args.queries, args.dimension)
            all_results.append(result)
        except Exception as exc:
            print(f"ERROR benchmarking {backend}: {exc}")

    if args.output and all_results:
        import json
        with open(args.output, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nResults saved to {args.output}")

    print(f"\n{'='*60}")
    print("Benchmark complete!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
