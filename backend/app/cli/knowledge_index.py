"""
CLI commands for managing the Template Knowledge Index.

Usage:
    python -m app.cli.knowledge_index build [--max-templates N] [--no-embeddings]
    python -m app.cli.knowledge_index update
    python -m app.cli.knowledge_index status
    python -m app.cli.knowledge_index search "query text"
    python -m app.cli.knowledge_index clear
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import get_settings
from app.services.fetcher import TemplateFetcherService
from app.services.parser import ParserService
from app.services.template_knowledge import (
    OllamaEmbeddingClient,
    TemplateKnowledgeBuilder,
    TemplateKnowledgeIndex,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_index_path() -> Path:
    """Get the path to the knowledge index database."""
    settings = get_settings()
    return settings.magic_import_cache_dir / "template_knowledge" / "index.db"


async def cmd_build(
    max_templates: int | None = None,
    no_embeddings: bool = False,
    status_filter: list[str] | None = None,
) -> int:
    """Build the template knowledge index from scratch."""
    print("=" * 60)
    print("Template Knowledge Index Builder")
    print("=" * 60)

    db_path = get_index_path()
    print(f"Database path: {db_path}")

    # Initialize services
    settings = get_settings()
    fetcher = TemplateFetcherService(settings)
    parser = ParserService()

    # Check Ollama availability
    embedding_client = OllamaEmbeddingClient(
        base_url=settings.ollama_base_url,
        model="nomic-embed-text",
    )

    if not no_embeddings:
        print("\nChecking Ollama availability...")
        ollama_available = await embedding_client.is_available()
        if ollama_available:
            print("✓ Ollama is available with nomic-embed-text model")
        else:
            print("✗ Ollama not available. Embeddings will be skipped.")
            print("  To enable embeddings, run: ollama pull nomic-embed-text")
            no_embeddings = True

    # Initialize index and builder
    index = TemplateKnowledgeIndex(db_path=db_path, embedding_client=embedding_client)
    builder = TemplateKnowledgeBuilder(
        fetcher=fetcher,
        parser=parser,
        embedding_client=embedding_client,
    )

    # Clear existing index
    print("\nClearing existing index...")
    index.clear()

    # Build index
    print(f"\nBuilding index (max_templates={max_templates}, embeddings={not no_embeddings})...")
    start_time = datetime.utcnow()

    try:
        stats = await builder.build_full_index(
            index=index,
            status_filter=status_filter or ["published"],
            generate_embeddings=not no_embeddings,
            max_templates=max_templates,
        )
    except Exception as e:
        print(f"\n✗ Build failed: {e}")
        logger.exception("Index build failed")
        return 1

    elapsed = (datetime.utcnow() - start_time).total_seconds()

    # Print results
    print("\n" + "=" * 60)
    print("Build Complete!")
    print("=" * 60)
    print(f"Templates processed: {stats['templates_processed']}")
    print(f"Templates failed:    {stats['templates_failed']}")
    print(f"Fields indexed:      {stats['fields_indexed']}")
    print(f"Patterns created:    {stats['patterns_created']}")
    print(f"Embeddings generated:{stats['embeddings_generated']}")
    print(f"Time elapsed:        {elapsed:.1f}s")
    print(f"Database size:       {db_path.stat().st_size / 1024 / 1024:.1f} MB")

    # Optimize storage
    print("\nOptimizing database...")
    index.vacuum()
    print(f"Optimized size:      {db_path.stat().st_size / 1024 / 1024:.1f} MB")

    await embedding_client.close()
    return 0


async def cmd_status() -> int:
    """Show current index status."""
    db_path = get_index_path()

    if not db_path.exists():
        print("Index not found. Run 'build' first.")
        return 1

    settings = get_settings()
    embedding_client = OllamaEmbeddingClient(base_url=settings.ollama_base_url)
    index = TemplateKnowledgeIndex(db_path=db_path, embedding_client=embedding_client)

    status = await index.get_status()

    print("=" * 60)
    print("Template Knowledge Index Status")
    print("=" * 60)
    print(f"Database path:       {db_path}")
    print(f"Database size:       {db_path.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"Index version:       {status.index_version}")
    print(f"Templates indexed:   {status.templates_indexed}")
    print(f"Fields indexed:      {status.fields_indexed}")
    print(f"Patterns indexed:    {status.patterns_indexed}")
    print(f"Embedding model:     {status.embedding_model}")
    print(f"Ollama available:    {'✓' if status.ollama_available else '✗'}")
    print(f"Last updated:        {status.last_updated or 'Never'}")

    # List templates
    templates = index.list_templates()
    if templates:
        print("\n" + "-" * 60)
        print("Indexed Templates:")
        print("-" * 60)
        for t in templates[:20]:
            print(f"  IDTA-{t.idta_number}: {t.title} ({t.field_count} fields)")
        if len(templates) > 20:
            print(f"  ... and {len(templates) - 20} more")

    await embedding_client.close()
    return 0


async def cmd_search(query: str, top_k: int = 5) -> int:
    """Search for fields similar to query."""
    db_path = get_index_path()

    if not db_path.exists():
        print("Index not found. Run 'build' first.")
        return 1

    settings = get_settings()
    embedding_client = OllamaEmbeddingClient(base_url=settings.ollama_base_url)
    index = TemplateKnowledgeIndex(db_path=db_path, embedding_client=embedding_client)

    print(f"Searching for: '{query}'")
    print("-" * 60)

    results = await index.find_similar_fields_by_text(
        query=query,
        top_k=top_k,
        threshold=0.3,
    )

    if not results:
        print("No matching fields found.")
        return 0

    for i, (field, score) in enumerate(results, 1):
        print(f"\n{i}. [{score:.2f}] {field.path}")
        print(f"   Template: IDTA-{field.template_idta}")
        print(f"   Label:    {field.semantic_label or field.id_short}")
        if field.semantic_id:
            print(f"   IRDI:     {field.semantic_id}")
        if field.definition:
            print(f"   Def:      {field.definition[:100]}...")

    await embedding_client.close()
    return 0


async def cmd_recommend(label: str, value: str | None = None) -> int:
    """Get semantic ID recommendations for a field."""
    db_path = get_index_path()

    if not db_path.exists():
        print("Index not found. Run 'build' first.")
        return 1

    settings = get_settings()
    embedding_client = OllamaEmbeddingClient(base_url=settings.ollama_base_url)
    index = TemplateKnowledgeIndex(db_path=db_path, embedding_client=embedding_client)

    print(f"Recommending semantic IDs for: '{label}'")
    if value:
        print(f"Value: '{value}'")
    print("-" * 60)

    recommendations = await index.recommend_semantic_ids(
        label=label,
        value=value,
        top_k=5,
        threshold=0.3,
    )

    if not recommendations:
        print("No recommendations found.")
        return 0

    for i, rec in enumerate(recommendations, 1):
        print(f"\n{i}. [{rec.confidence:.2f}] {rec.label}")
        print(f"   IRDI:     {rec.irdi}")
        print(f"   Source:   IDTA-{rec.source_template}")
        print(f"   Usage:    {rec.usage_count} template(s)")
        if rec.definition:
            print(f"   Def:      {rec.definition[:100]}...")

    await embedding_client.close()
    return 0


async def cmd_clear() -> int:
    """Clear the index."""
    db_path = get_index_path()

    if not db_path.exists():
        print("Index does not exist.")
        return 0

    index = TemplateKnowledgeIndex(db_path=db_path)
    index.clear()
    print("Index cleared.")
    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manage the Template Knowledge Index",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build the index from scratch")
    build_parser.add_argument(
        "--max-templates",
        type=int,
        default=None,
        help="Maximum templates to index (for testing)",
    )
    build_parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Skip embedding generation (faster but no semantic search)",
    )
    build_parser.add_argument(
        "--include-deprecated",
        action="store_true",
        help="Include deprecated templates",
    )

    # Update command
    subparsers.add_parser("update", help="Update index with new templates")

    # Status command
    subparsers.add_parser("status", help="Show index status")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for similar fields")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--top-k", type=int, default=5, help="Number of results")

    # Recommend command
    rec_parser = subparsers.add_parser("recommend", help="Get semantic ID recommendations")
    rec_parser.add_argument("label", help="Field label")
    rec_parser.add_argument("--value", help="Optional field value")

    # Clear command
    subparsers.add_parser("clear", help="Clear the index")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Run the appropriate command
    if args.command == "build":
        status_filter = ["published"]
        if args.include_deprecated:
            status_filter.append("deprecated")
        return asyncio.run(
            cmd_build(
                max_templates=args.max_templates,
                no_embeddings=args.no_embeddings,
                status_filter=status_filter,
            )
        )
    elif args.command == "update":
        # Update is same as build for now
        return asyncio.run(cmd_build())
    elif args.command == "status":
        return asyncio.run(cmd_status())
    elif args.command == "search":
        return asyncio.run(cmd_search(args.query, args.top_k))
    elif args.command == "recommend":
        return asyncio.run(cmd_recommend(args.label, args.value))
    elif args.command == "clear":
        return asyncio.run(cmd_clear())
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
