import argparse
import asyncio
import logging
import sys

from app.knowledge.sync_service import KnowledgeBaseSyncService

logger = logging.getLogger(__name__)


class KbSyncManager:
    """Manages knowledge base sync."""

    def __init__(self):
        self.sync_service = KnowledgeBaseSyncService()

    async def sync_all(self):
        """Sync all sources."""
        results = await self.sync_service.sync_all()
        logger.info(f"Synced {len(results)} sources")
        return results


def main():
    """Run as command line entry point."""
    parser = argparse.ArgumentParser(description="Knowledge sync manager")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    subparsers.add_parser('sync-all', help='Sync all sources')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    kb_manager = KbSyncManager()

    if args.command == "sync-all":
        asyncio.run(kb_manager.sync_all())

if __name__ == "__main__":
    main()
