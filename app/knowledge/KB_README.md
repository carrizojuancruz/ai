# Knowledge Base Module

Web content processing system that converts website content into searchable vector embeddings using AWS Bedrock and S3 Vector Store.

## Core Features

- **Web Crawling**: Extract content from websites
- **Vector Storage**: Store embeddings in S3 Vector Store  
- **Change Detection**: Hash-based content monitoring
- **Search**: Semantic similarity search
- **Sync**: External source synchronization

## Architecture

Six core services work together:

- **KnowledgeBaseOrchestrator**: External source sync coordination
- **KnowledgeService**: Document processing and vector operations
- **SourceService**: Source management and validation
- **CrawlerService**: Web content extraction
- **S3VectorStoreService**: Vector storage and search
- **SyncService**: Content synchronization and change detection

## Document Operations

### How Documents Work
All operations use **source IDs** to group related content:

**Adding Documents:**
1. Register source → Crawl content → Generate vectors → Store in S3

**Updating Documents:**  
1. Detect changes via content hashes → Delete old vectors → Store new vectors

**Deleting Documents:**
1. Find all vectors for source ID → Delete in batches of 100 → Remove source config

### Key Points
- Vector keys use format: `doc_{content_hash}`
- Batch processing: 100 vectors per operation
- Two-phase deletion: vectors first, then config
- Change detection prevents unnecessary reprocessing

## Synchronization System

### How Synchronization Works

The system maintains content freshness through two types of synchronization:

**External Source Sync:**
- Fetches source configurations from external repositories
- Compares external sources with local configuration
- Creates, updates, or deletes sources based on differences
- Ensures local knowledge base reflects external changes

**Content Sync:**
- Crawls websites to extract current content
- Generates SHA-256 hashes for each content chunk
- Compares new hashes with stored hashes to detect changes
- Only reprocesses content that has actually changed
- Preserves unchanged vectors to save processing time

### Sync Process Flow

1. **Discovery Phase**: Find all sources that need processing
2. **Change Detection**: Compare current content with stored content using hashes
3. **Cleanup Phase**: Remove vectors for deleted or changed content
4. **Processing Phase**: Generate new vectors for new or modified content
5. **Storage Phase**: Save new vectors and update metadata
6. **Reporting Phase**: Provide detailed results of sync operation

### Sync Types

**Full Sync**: Process all enabled sources regardless of changes
**Selective Sync**: Process only sources with detected changes
**Individual Sync**: Process a specific source by ID
**External Sync**: Synchronize source configurations from external systems

### Change Detection Strategy

The system uses content hashing to minimize unnecessary work:
- Each content chunk generates a unique SHA-256 hash
- Hashes are compared between sync runs
- Only changed content triggers reprocessing
- Unchanged content vectors remain untouched
- Entire source is reindexed if any chunk changes (ensures consistency)

## API Usage

```python
# Sync external sources
result = await orchestrator.sync_external_sources()

# Process individual source  
result = await knowledge_service.sync_source(source_id)

# Search content
results = await knowledge_service.search("query text", limit=10)

# Delete source vectors
result = await vector_store.delete_source_vectors(source_id)
```