import argparse
import asyncio
import logging
import sys

from app.knowledge.sources.repository import SourceRepository
from app.knowledge.sync.service import SyncService

logger = logging.getLogger(__name__)


class SyncManager:
    """Manages synchronization operations for knowledge sources."""

    def __init__(self):
        self.source_repo = SourceRepository()
        self.sync_service = SyncService()

    async def sync_all(self):
        """Sync all sources."""
        results = await self.sync_service.sync_sources()
        logger.info(f"Synced {len(results)} sources")
        return results

    async def sync_source(self, source_id: str):
        """Sync a specific source by ID."""
        source = self.source_repo.find_by_id(source_id)
        if not source:
            logger.error(f"Source {source_id} not found")
            return None

        result = await self.sync_service.sync_source(source)
        logger.info(f"Synced {source_id}")
        return result


def main():
    """Run as command line entry point."""
    parser = argparse.ArgumentParser(description="Knowledge sync manager")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    subparsers.add_parser('sync-all', help='Sync all sources')

    sync_source = subparsers.add_parser('sync-source', help='Sync specific source')
    sync_source.add_argument('source_id', help='Source ID to sync')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    sync_manager = SyncManager()

    if args.command == "sync-all":
        asyncio.run(sync_manager.sync_all())
    elif args.command == "sync-source":
        asyncio.run(sync_manager.sync_source(args.source_id))


if __name__ == "__main__":
    main()
