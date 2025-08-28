# Knowledge Module

Web content processing system that converts website content into searchable vector embeddings using AWS Bedrock and S3 Vector Store.

## Architecture

The Knowledge module consists of five core services that work together to crawl, process, and synchronize web content:

- **KnowledgeService**: Document processing and vector operations
- **SourceService**: Source management and validation
- **CrawlerService**: Web content extraction with multiple strategies
- **S3VectorStoreService**: Vector storage and similarity search
- **SyncService**: Content synchronization and change detection

## Data Models

### Source
```python
{
  "id": "source_identifier",
  "name": "Source Name", 
  "url": "https://example.com",
  "enabled": true
}
```

### SyncResult
```python
{
  "source_id": "source_identifier",
  "success": true,
  "message": "Status message",
  "chunks_reindexed": 42,
  "has_changes": true,
  "execution_time_seconds": 12.5,
  "timestamp": "2025-08-27T10:00:00Z"
}
```

## Processing Pipeline

```
URL → Crawl → Clean HTML → Split Text → Generate Embeddings → Store Vectors → Search
```

### Workflow
1. **Source Registration**: URL validation and duplicate prevention
2. **Content Crawling**: Web scraping using selected strategy
3. **HTML Cleaning**: Remove scripts, styles, and non-content elements
4. **Text Chunking**: Split content with configurable size and overlap
5. **Embedding Generation**: Create vectors using AWS Bedrock Titan model
6. **Vector Storage**: Persist embeddings in S3 Vector Store with metadata
7. **Search Operations**: Similarity queries with ranked results

## Crawling Strategies

### Recursive
- Follows internal links within domain boundaries
- Configurable maximum depth and page limits
- Timeout controls for request management

### Single Page
- Processes only the specified URL
- No link following or discovery

### Sitemap
- Parses XML sitemap files
- Processes discovered URLs within limits

## Synchronization System

The sync system maintains current content by detecting changes and re-indexing only when necessary.

### Change Detection Method

**Hash-Based Comparison**: Each document chunk generates a SHA-256 hash from its content. The system compares current hashes against stored hashes to identify changes.

### Parent-Child Strategy

When any chunk in a source changes, the entire source gets re-indexed:

1. **Detection**: Compare hash sets between current and stored content
2. **Deletion**: Remove all existing vectors for the source
3. **Re-indexing**: Process and store all current content
4. **Result**: Track chunks reindexed and change status

This approach ensures consistency and handles cases where chunk boundaries may shift due to content modifications.

### Manual Sync Commands

```bash
# Sync all sources
poetry run python -m app.knowledge.management.sync_manager sync-all

# Sync specific source
poetry run python -m app.knowledge.management.sync_manager sync-source <source_name>
```

### Sources Configuration
Sources are managed in `app/knowledge/sources/sources.json`:

```json
{
  "sources": [
    {
      "id": "example_source",
      "name": "Example Website",
      "url": "https://example.com",
      "enabled": true
    }
  ]
}
```

## Content Processing

### HTML Cleaning
- Remove non-content elements: `script`, `style`, `nav`, `header`, `footer`
- Use BeautifulSoup with lxml parser for HTML/XML processing
- Extract visible text while preserving structure
- Normalize whitespace and remove artifacts

### Text Chunking
- **RecursiveCharacterTextSplitter**: Maintains document structure
- **Overlap**: Preserves context between adjacent chunks
- **Boundary Respect**: Splits at natural text boundaries when possible
- **Metadata**: Maintains source attribution and content hashes

### Embedding Generation
- AWS Bedrock Titan Text model integration
- Consistent vector dimensions across all content
- Metadata preservation with embeddings

## Search Operations

### Similarity Search
```python
results = knowledge_service.search("query text")
```

Returns ranked results with:
- **text**: Chunk content
- **source**: Source URL
- **score**: Similarity score (0-1)
- **metadata**: Additional context

### Search Configuration
- Configurable result limits via `TOP_K_SEARCH`
- Cosine similarity ranking
- Source filtering capabilities

## Integration Points

- **AWS Bedrock**: Text embedding generation
- **S3 Vector Store**: Vector persistence and search
- **LangChain**: Document processing utilities
- **BeautifulSoup**: HTML parsing and content extraction