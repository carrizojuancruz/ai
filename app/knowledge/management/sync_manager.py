import argparse
import asyncio
import hashlib
import logging
import sys

from app.knowledge.models import Source
from app.knowledge.service import KnowledgeService

logger = logging.getLogger(__name__)


class KbSyncManager:
    """Manages knowledge base sync."""

    def __init__(self):
        self.knowledge_service = KnowledgeService()
        self._sync_service = None

    @property
    def sync_service(self):
        """Lazy initialization of sync service."""
        if self._sync_service is None:
            from app.knowledge.sync_service import KnowledgeBaseSyncService
            self._sync_service = KnowledgeBaseSyncService()
        return self._sync_service

    async def sync_all(self):
        """Sync all sources."""
        results = await self.sync_service.sync_all()
        logger.info(f"Synced {len(results)} sources")
        return results

    async def upsert_source_by_url(self, url: str, name: str = None, source_type: str = None,
                                   category: str = None, description: str = None,
                                   max_pages: int = None, recursion_depth: int = None):
        """Upsert a source by URL."""
        # Generate deterministic ID based on URL (same as sync service)
        source_id = hashlib.sha256(url.encode()).hexdigest()[:16]

        if not name:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            name = parsed.netloc or "Unknown Source"

        source = Source(
            id=source_id,
            name=name,
            url=url,
            enabled=True,
            type=source_type,
            category=category,
            description=description,
            total_max_pages=max_pages,
            recursion_depth=recursion_depth,
            last_sync=None
        )

        logger.info(f"Upserting source: {name} ({url})")

        try:
            result = await self.knowledge_service.upsert_source(source)

            if result.get("success"):
                logger.info(f"Successfully upserted source: {name}")
                logger.info(f"Documents added: {result.get('documents_added', 0)}")
                logger.info(f"Message: {result.get('message', '')}")
            else:
                logger.error(f"Failed to upsert source: {result.get('message', 'Unknown error')}")

            return result

        except Exception as e:
            logger.error(f"Error upserting source {url}: {e}")
            return {"success": False, "error": str(e)}


def main():
    """Run as command line entry point."""
    parser = argparse.ArgumentParser(description="Knowledge sync manager")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Sync all sources command
    subparsers.add_parser('sync-all', help='Sync all sources')

    # Upsert source by URL command
    upsert_parser = subparsers.add_parser('upsert-url', help='Upsert a source by URL')
    upsert_parser.add_argument('url', help='Source URL to upsert')
    upsert_parser.add_argument('--name', help='Source name (auto-generated from URL if not provided)')
    upsert_parser.add_argument('--type', dest='source_type', help='Source type')
    upsert_parser.add_argument('--category', help='Source category')
    upsert_parser.add_argument('--description', help='Source description')
    upsert_parser.add_argument('--max-pages', type=int, help='Maximum pages to crawl')
    upsert_parser.add_argument('--recursion-depth', type=int, help='Recursion depth for crawling')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    kb_manager = KbSyncManager()

    if args.command == "sync-all":
        asyncio.run(kb_manager.sync_all())
    elif args.command == "upsert-url":
        asyncio.run(kb_manager.upsert_source_by_url(
            url=args.url,
            name=args.name,
            source_type=args.source_type,
            category=args.category,
            description=args.description,
            max_pages=args.max_pages,
            recursion_depth=args.recursion_depth
        ))

if __name__ == "__main__":
    main()
