import asyncio
import sys
from app.knowledge.sync.service import SyncService
from app.knowledge.sources.repository import SourceRepository

async def sync_all():
    
    sync_service = SyncService()
    results = await sync_service.sync_sources()
    print(f"Synced {len(results)} sources")

async def sync_source(source_id):
    
    
    source_repo = SourceRepository()
    sync_service = SyncService()
    
    source = source_repo.find_by_id(source_id)
    if not source:
        print(f"Source {source_id} not found")
        return
        
    result = await sync_service.sync_source(source)
    print(f"Synced {source_id}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: sync-all or sync-source <id>")
        sys.exit(1)
    
    if sys.argv[1] == "sync-all":
        asyncio.run(sync_all())
    elif sys.argv[1] == "sync-source":
        asyncio.run(sync_source(sys.argv[2]))
