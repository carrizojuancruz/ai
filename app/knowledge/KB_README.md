# Knowledge Base Module

Advanced web content processing system that converts website content into searchable vector embeddings using AWS Bedrock and S3 Vector Store. This module powers Verde AI's financial advisory knowledge base with intelligent crawling, semantic search, and automated synchronization capabilities.

## Core Features

- **Multi-Strategy Web Crawling**: Adaptive content extraction with recursive, sitemap, single-page, and PDF crawling
- **Vector Storage & Search**: Semantic similarity search using AWS Bedrock embeddings and S3 Vector Store
- **Smart Change Detection**: SHA-256 hash-based content monitoring to minimize reprocessing
- **External Source Synchronization**: Automated sync with external knowledge repositories
- **Content Filtering**: JavaScript detection and content quality validation
- **Batch Processing**: Efficient large-scale document processing with configurable limits

## Architecture

The knowledge base is built around **six core services**:

- **KnowledgeService**: Central orchestrator for document processing and vector operations
- **CrawlerService**: Multi-strategy web content extraction with fallback mechanisms
- **DocumentService**: Text chunking, embedding generation, and content hashing
- **S3VectorStoreService**: AWS S3 Vector Store integration for storage and retrieval
- **SourceRepository**: JSON-based source configuration management
- **KnowledgeBaseSyncService**: External source synchronization and change detection

## Crawling Strategies

The system employs **four adaptive crawling strategies** with intelligent fallbacks:

### 1. Recursive Crawling (Default)
- **Use Case**: Comprehensive site exploration
- **Features**: Configurable depth limits, path filtering, content validation
- **Best For**: Government sites, documentation hubs
- **Fallback**: Single-page crawling for corrupted or JS-heavy content

### 2. Sitemap Crawling
- **Use Case**: Structured site exploration using XML sitemaps
- **Features**: Automatic sitemap discovery, page limit enforcement
- **Best For**: Large corporate sites with well-maintained sitemaps
- **Fallback**: Recursive crawling if sitemap unavailable

### 3. Single-Page Crawling
- **Use Case**: Targeted content extraction from specific URLs
- **Features**: JavaScript rendering support, clean content extraction
- **Best For**: Dynamic content, API documentation, specific resources

### 4. PDF Processing
- **Use Case**: Direct PDF document ingestion
- **Features**: Text extraction, metadata preservation, chunking optimization
- **Best For**: Reports, documentation, regulatory content

### Intelligent Fallback System
- **Corruption Detection**: Binary content filtering and validation
- **JavaScript Detection**: Automatic fallback for JS-heavy sites
- **Error Handling**: Progressive fallback from complex to simple strategies

## Source Configuration

Sources are managed through a flexible configuration system supporting various content types:

```json
{
  "id": "unique_source_identifier", 
  "name": "Human-readable source name",
  "url": "https://example.com",
  "enabled": true,
  "type": "State Government",
  "category": "Financial Services", 
  "description": "Source description for context",
  "include_path_patterns": "/financial/*,/resources/*",
  "exclude_path_patterns": "/admin/*,/internal/*",
  "total_max_pages": 50,
  "recursion_depth": 3,
  "last_sync": "2025-09-11T10:30:00Z",
  "total_chunks": 247,
  "section_urls": ["https://example.com/page1", "https://example.com/page2"]
}
```

### Configuration Options
- **Path Filtering**: Include/exclude patterns for targeted crawling
- **Crawl Limits**: Maximum pages and recursion depth controls
- **Content Metadata**: Type, category, and description for search enhancement
- **Sync Tracking**: Last sync timestamps and chunk counts
- **Section Mapping**: Discovered URLs for granular source attribution

## Document Lifecycle Management

### Document Processing Pipeline
The system processes documents through a sophisticated pipeline ensuring data consistency and optimal search performance:

**1. Content Extraction**
- Multi-strategy crawling with adaptive fallbacks
- Content validation and corruption detection
- Metadata enrichment with source information

**2. Text Chunking**
- Configurable chunk size (default: optimized for embeddings)
- Smart overlap to preserve context across boundaries  
- Source metadata propagation to each chunk

**3. Embedding Generation**
- AWS Bedrock integration for high-quality embeddings
- Batch processing for efficiency
- SHA-256 content hashing for change detection

**4. Vector Storage**
- S3 Vector Store with semantic indexing
- Metadata preservation for attribution and filtering
- Batch operations for scalability

### Document Operations

**Adding Documents:**
1. **Source Registration** → **Content Crawling** → **Chunking & Embedding** → **Vector Storage**

**Updating Documents:**  
1. **Change Detection** (via content hashes) → **Cleanup Old Vectors** → **Process New Content** → **Store Updated Vectors**

**Deleting Documents:**
1. **Source Identification** → **Batch Vector Deletion** (100 vectors per operation) → **Configuration Cleanup**

### Key Technical Details
- **Vector Keys**: Format `doc_{source_id}_{content_hash}_{chunk_index}` for unique identification
- **Batch Processing**: 100 vectors per operation for optimal performance
- **Two-Phase Deletion**: Vectors first, then configuration cleanup
- **Change Detection**: Content hashing prevents unnecessary reprocessing
- **Chunk Limits**: Configurable per-source limits to manage storage costs

## Synchronization System

## Synchronization System

The knowledge base maintains content freshness through **intelligent synchronization** with both external sources and content changes.

### Synchronization Types

**1. External Source Sync**
- Fetches source configurations from external repositories via REST API
- Compares external sources with local configuration using URL-based matching
- **CRUD Operations**: Creates new sources, updates existing ones, deletes obsolete sources
- Ensures local knowledge base reflects external knowledge management systems

**2. Content Sync** 
- Crawls websites to extract current content using adaptive strategies
- **Change Detection**: SHA-256 hashing of content chunks for precise change identification
- **Selective Processing**: Only reprocesses content that has actually changed
- **Consistency Guarantee**: Entire source reindexed if any chunk changes

**3. Hybrid Sync Operations**
- **Full Sync**: Process all enabled sources regardless of change status
- **Selective Sync**: Process only sources with detected content changes  
- **Individual Sync**: Process specific source by ID for targeted updates
- **Limited Sync**: Process subset of sources for testing or gradual rollouts

### Advanced Sync Process Flow

**Phase 1: Discovery & Planning**
- Fetch external source configurations
- Compare with local source inventory
- Identify sources requiring creation, updates, or deletion
- Apply processing limits and filtering rules

**Phase 2: Change Detection & Validation** 
- Content crawling with strategy selection
- SHA-256 hash generation for each content chunk
- Hash comparison with stored values
- Validation of content quality and completeness

**Phase 3: Vector Management**
- **Cleanup**: Remove vectors for deleted/changed content
- **Processing**: Generate embeddings for new/modified content
- **Storage**: Batch upload vectors to S3 Vector Store  
- **Metadata Update**: Update source configurations and timestamps

**Phase 4: Reporting & Logging**
- Detailed sync results with metrics and error reporting
- Performance tracking (processing time, chunks per source)
- **Failure Analysis**: Categorized error reporting (SSL, timeout, 403, 404, etc.)
- Crawl logging for operational monitoring

### Smart Change Detection Strategy

**Content Hashing Approach:**
- Each content chunk generates a unique SHA-256 hash from its text content
- Hashes stored as metadata for comparison across sync runs
- **Efficiency**: Only changed content triggers expensive reprocessing operations
- **Consistency**: Unchanged content vectors remain untouched preserving search performance
- **Atomicity**: If any chunk changes, entire source is reindexed ensuring consistency

**Error Handling & Resilience:**
- **Categorized Failures**: SSL errors, timeouts, access forbidden, page not found
- **Progressive Fallbacks**: Multiple crawling strategies attempted per source
- **Graceful Degradation**: Partial failures don't block overall sync operations
- **External Source Resilience**: Local operations continue if external API unavailable

## API Interface

### Knowledge Base Operations

```python
from app.knowledge.service import KnowledgeService
from app.knowledge.sync_service import KnowledgeBaseSyncService
from app.knowledge.management.sync_manager import KbSyncManager

# Initialize services
knowledge_service = KnowledgeService()
sync_service = KnowledgeBaseSyncService()
sync_manager = KbSyncManager()

# Search operations
results = await knowledge_service.search(
    query="financial planning tips",
    limit=10
)

# Source management
sources = knowledge_service.get_sources()
source_details = knowledge_service.get_source_details(source_id)

# Sync operations  
sync_result = await sync_service.sync_all(limit=50)  # Limit to 50 sources
individual_result = await sync_manager.upsert_source_by_url(
    url="https://example.com",
    name="Example Financial Site",
    source_type="Information Service",
    category="Financial Planning",
    max_pages=100
)

# Bulk operations
delete_result = knowledge_service.delete_all_vectors()
source_deletion = knowledge_service.delete_source(source)
```

### REST API Endpoints

**Search Knowledge Base**
```http
POST /knowledge/search
Content-Type: application/json

{
  "query": "retirement planning strategies"
}
```

**Get Sources**
```http
GET /knowledge/sources
```

**Get Source Details**
```http
GET /knowledge/sources/{source_id}
```

**Delete All Vectors**
```http
DELETE /knowledge/vectors/all
```

### Command Line Interface

**Sync Management CLI**
```bash
# Full synchronization
docker compose exec app poetry run python -m app.knowledge.management.sync_manager

# Individual source management  
docker compose exec app poetry run python -c "
from app.knowledge.management.sync_manager import KbSyncManager
import asyncio
manager = KbSyncManager()
asyncio.run(manager.upsert_source_by_url('https://example.com', 'Example Site'))
"
```

### Configuration Management

**Environment Variables**
- `CRAWL_TYPE`: Default crawling strategy (`recursive`, `sitemap`, `single`)
- `CHUNK_SIZE`: Text chunk size for embeddings (default: optimized)
- `CHUNK_OVERLAP`: Overlap between chunks for context preservation
- `MAX_CHUNKS_PER_SOURCE`: Limit chunks per source to control costs
- `EMBEDDINGS_MODEL_ID`: AWS Bedrock embedding model
- `S3V_BUCKET`: S3 Vector Store bucket name
- `S3V_INDEX_KB`: Knowledge base index name

**Source Configuration File**
- **Location**: `app/knowledge/sources/sources.json`
- **Format**: JSON array of source objects
- **Management**: Automatic via sync operations or manual editing

## Module Structure

```
app/knowledge/
├── __init__.py                 # Module initialization
├── models.py                   # Source data models (Pydantic)
├── service.py                  # Core KnowledgeService 
├── document_service.py         # Text processing & embeddings
├── sync_service.py             # KnowledgeBaseSyncService
├── crawl_logger.py             # Operational logging
│
├── crawler/                    # Web crawling engine
│   ├── service.py              # CrawlerService with strategy selection
│   ├── content_utils.py        # JavaScript detection & URL filtering
│   └── loaders/                # Crawling strategy implementations
│       ├── base_loader.py      # Abstract base loader
│       ├── recursive_loader.py # Recursive site crawling
│       ├── sitemap_loader.py   # XML sitemap-based crawling
│       ├── single_page_loader.py # Single URL processing
│       └── pdf_loader.py       # PDF document processing
│
├── vector_store/               # AWS S3 Vector Store integration
│   └── service.py              # S3VectorStoreService
│
├── sources/                    # Source configuration management
│   ├── base_repository.py      # Repository interface
│   ├── repository.py           # JSON file-based implementation
│   └── sources.json            # Source configurations (data file)
│
└── management/                 # Administrative tools
    └── sync_manager.py         # Command-line sync utilities
```

## Dependencies & Integration

### Core Dependencies
- **LangChain**: Document processing, text splitting, content loading
- **AWS Bedrock**: Embedding generation using latest models
- **boto3**: S3 Vector Store client integration
- **BeautifulSoup4**: HTML parsing and content extraction
- **requests**: HTTP client for web crawling
- **Pydantic**: Data validation and configuration management

### External Integrations
- **External Sources API**: REST API for source configuration management
- **S3 Vector Store**: AWS managed vector database for semantic search
- **Verde AI Memory System**: Integration with user memory and context systems
- **FastAPI**: REST API endpoints for knowledge operations

### Related Verde AI Services
- **Memory Service**: Semantic and episodic memory integration
- **Agent System**: Knowledge retrieval for LangGraph agents
- **User Context**: Personalized knowledge filtering and retrieval

## Deployment & Operations

### Docker Deployment
```yaml
# docker-compose.yml integration
services:
  app:
    environment:
      - AWS_REGION=us-east-1
      - S3V_BUCKET=verde-vectors
      - S3V_INDEX_KB=knowledge-base
      - CRAWL_TYPE=recursive
      - CHUNK_SIZE=1000
      - CHUNK_OVERLAP=200
      - MAX_CHUNKS_PER_SOURCE=500
```

### Monitoring & Observability
- **Crawl Logging**: Detailed operation logs with success/failure tracking
- **Performance Metrics**: Processing time, chunks per source, error rates
- **Error Categorization**: SSL, timeout, access, and content-specific errors
- **Sync Reporting**: Comprehensive results with source-level details

### Operational Considerations

**Performance Optimization**
- Batch processing for vector operations (100 vectors per batch)
- Intelligent change detection to minimize reprocessing
- Configurable chunk limits to control storage costs
- Adaptive crawling strategies for optimal content extraction

**Reliability & Error Handling**
- Progressive fallback strategies for failed crawls
- Graceful degradation when external APIs unavailable
- Comprehensive error logging and categorization
- Atomic operations ensuring data consistency

**Scalability Features**
- Configurable processing limits for large-scale operations
- Efficient hash-based change detection
- Batch vector storage and deletion operations
- Asynchronous processing for non-blocking operations

**Security Considerations**
- SSL certificate validation with fallback handling
- URL filtering to prevent malicious content ingestion
- Content validation and corruption detection
- AWS IAM integration for secure vector store access

## Future Enhancements

### Planned Improvements
- **Advanced Content Filtering**: Machine learning-based content quality scoring
- **Multi-language Support**: Enhanced text processing for international sources  
- **Real-time Sync**: WebSocket-based real-time content updates
- **Advanced Analytics**: Source performance metrics and content insights
- **Federated Search**: Cross-knowledge base search capabilities

### Integration Opportunities  
- **AI-Powered Source Discovery**: Automated discovery of relevant financial sources
- **Content Summarization**: AI-generated summaries for large documents
- **Semantic Clustering**: Automatic categorization and tagging of content
- **Personalized Ranking**: User context-aware search result ranking