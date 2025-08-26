# Knowledge Component

Web crawler and document processing system that converts web content into searchable knowledge vectors using AWS Bedrock embeddings and S3 Vector Store.

## Overview

The Knowledge component ingests website URLs, extracts content through configurable crawling, processes HTML into clean text, splits documents into semantic chunks, generates embeddings via AWS Bedrock, and stores vectors in S3 Vector Store for similarity-based retrieval.

## Core Components

### KnowledgeService
Orchestrates the document processing pipeline:
- Coordinates crawler, embedding generation, and vector storage operations
- Manages document chunking using RecursiveCharacterTextSplitter
- Handles embedding generation through AWS Bedrock integration
- Provides similarity search interface with configurable result limits
- Manages source document lifecycle including deletion

### SourceService  
Entry point for source management and bulk operations:
- Validates URLs and creates source definitions
- Orchestrates crawler and knowledge service integration
- Handles source creation, updates, and deletion
- Manages bulk source processing workflows
- Provides source lookup and listing capabilities

### CrawlerService  
Executes web content extraction strategies:
- **Recursive**: Follows internal links within domain boundaries up to specified depth
- **Single**: Processes only the target URL without link traversal
- **Sitemap**: Parses XML sitemaps for systematic page discovery
- Implements HTML cleaning to remove scripts, styles, and non-content elements
- Enforces page limits, depth constraints, and timeout controls

### S3VectorStoreService
Manages vector operations in AWS S3 Vector Store:
- Stores document embeddings with metadata preservation
- Executes similarity search queries with cosine distance ranking
- Handles vector addition and deletion operations by source
- Maintains document metadata including source URLs and chunk indices
- Generates unique vector keys for document identification

## Processing Pipeline

```
URL Input → Content Crawling → HTML Cleaning → Document Chunking → Embedding Generation → Vector Storage → Search Interface
```

### Workflow Steps:

1. **Source Registration**: URL validation and source creation with duplicate handling
2. **Content Extraction**: Web crawling using selected strategy with domain boundary enforcement
3. **HTML Processing**: Tag removal, script elimination, and text extraction using BeautifulSoup
4. **Document Segmentation**: Text splitting with configurable chunk sizes and overlap preservation
5. **Vector Generation**: Embedding creation using AWS Bedrock Titan Text model
6. **Index Storage**: Vector persistence in S3 with comprehensive metadata
7. **Search Operations**: Similarity queries with ranked result retrieval

## Content Processing

HTML processing pipeline ensures text quality:

- **Tag Filtering**: Removes `script`, `style`, `noscript`, `meta`, `link`, `head`, `nav`, `header`, `footer` elements
- **Parser Integration**: Uses BeautifulSoup with lxml parser for HTML/XML processing
- **Text Extraction**: Extracts visible text content while preserving semantic structure
- **Whitespace Normalization**: Consolidates spacing and removes formatting artifacts

## Crawling Strategies

### Recursive Crawling
- Traverses internal links within same domain
- Respects maximum depth and page count limitations
- Maintains crawl boundary enforcement
- Implements timeout controls for request management

### Single Page Processing
- Extracts content from specified URL only
- No link following or additional page discovery
- Suitable for targeted content extraction

### Sitemap Processing
- Parses XML sitemap files for page enumeration
- Processes discovered URLs within configured limits
- Provides systematic coverage for structured websites

## Document Chunking

Text segmentation maintains semantic coherence:

- **RecursiveCharacterTextSplitter**: Preserves document structure during splitting
- **Overlap Configuration**: Maintains context continuity between adjacent chunks
- **Boundary Respect**: Attempts to split at natural text boundaries
- **Metadata Preservation**: Maintains source attribution for each chunk

## Configuration Management

### Crawler Parameters
- Crawling strategy selection (recursive/single/sitemap)
- Maximum crawl depth for recursive operations
- Page count limits per source
- Request timeout configuration

### Processing Settings
- Document chunk size and overlap configuration
- Search result count limits
- Embedding model selection
- Vector index configuration

### AWS Integration
- S3 Vector Store bucket and index specification
- AWS region configuration
- Bedrock model selection
- Service authentication setup

### Storage Configuration
- Source persistence file location
- Vector metadata storage settings

## Integration Points

- **AWS Bedrock**: Embedding model integration for vector generation
- **S3 Vector Store**: Vector persistence and similarity search operations
- **LangChain**: Document processing and text splitting utilities
- **BeautifulSoup**: HTML parsing and content extraction

## Synchronization System

The Knowledge component includes a robust content synchronization system that efficiently detects and updates changed web content without unnecessary re-processing.

### Key Features

- **Hash-based Change Detection**: Uses SHA-256 content hashing to identify modified chunks
- **Parent-Child Strategy**: Deletes entire source when any chunk changes to maintain consistency
- **Deterministic Source IDs**: URL-based source identification ensures consistent sync cycles
- **Scheduled Execution**: Configurable sync intervals (default: every 3 days)
- **Pagination Support**: Handles sources with unlimited chunks using S3 Vector Store pagination

### SyncService Architecture

The `SyncService` orchestrates synchronization by:
1. Crawling source URLs to get current content and generate new hashes
2. Retrieving existing chunk hashes from S3 Vector Store using pagination
3. Comparing hash sets to determine if content has changed
4. Re-indexing entire source if any chunk differs (parent-child deletion)
5. Tracking sync results with chunks reindexed count and change flags

### Configuration

```python
# Environment variables
SYNC_ENABLED=true  # Enable/disable synchronization 
SYNC_SCHEDULE_DAYS=3  # Sync interval in days
```

### Usage

```python
# Manual sync of specific source
sync_service = SyncService()
result = await sync_service.sync_source(source_id)

# Bulk sync of all sources  
results = await sync_service.sync_sources()
```

The synchronization system ensures your knowledge base stays current with minimal computational overhead by only re-processing sources that have actually changed.
