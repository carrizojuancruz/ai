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

## TODO: Content Synchronization

### Hash-based Change Detection
- Compute hash for each chunk after content extraction
- Use Set data structures for O(1) lookup of existing chunk hashes
- Compare new content hashes against stored hashes to identify changes
- Skip embedding computation for unchanged content chunks

### Parent-Child Chunking Model
- Generate source identifiers based on source name/URL instead of random UUIDs
- Source is parent, chunks are children
- When any chunk changes, delete entire parent source and reindex all chunks
- Chunk boundary changes affect neighboring chunks

### Synchronization Workflow

```
Cron Job → Crawl Content → Compute Hashes → Compare with DB → Reindex Changed Sources
```

1. Implement cron-based synchronization (runs every 3 days)
2. Crawl content from source URLs
3. Compute hashes for new content chunks
4. Query database for existing chunk hashes using Set operations
5. Identify changed chunks
6. Delete all chunks for changed sources and reprocess

### Implementation Requirements

- Store chunk hashes alongside vector embeddings
- Implement bulk hash lookup operations in vector store
- Atomic deletion and reindexing operations
- Cron job configuration (schedule: every 3 days)
- Synchronization logging
- Error handling and retry logic for failed sync operations
- Monitoring and alerting for sync job status
