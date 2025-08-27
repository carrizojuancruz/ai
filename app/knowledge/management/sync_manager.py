import asyncio
import logging
import sys

from app.knowledge.sources.repository import SourceRepository
from app.knowledge.sync.service import SyncService

logger = logging.getLogger(__name__)

async def sync_all():

    sync_service = SyncService()
    results = await sync_service.sync_sources()
    logger.info(f"Synced {len(results)} sources")

async def sync_source(source_id):


    source_repo = SourceRepository()
    sync_service = SyncService()

    source = source_repo.find_by_id(source_id)
    if not source:
        logger.error(f"Source {source_id} not found")
        return

    result = await sync_service.sync_source(source)
    logger.info(f"Synced {source_id}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Usage: python sync_manager.py sync-all | python sync_manager.py sync-source <source_id>")
        sys.exit(1)

    if sys.argv[1] == "sync-all":
        asyncio.run(sync_all())
    elif sys.argv[1] == "sync-source":
        if len(sys.argv) < 3:
            logger.error("Error: 'sync-source' command requires a source ID argument")
            logger.error("Usage: python sync_manager.py sync-source <source_id>")
            sys.exit(1)
        asyncio.run(sync_source(sys.argv[2]))
