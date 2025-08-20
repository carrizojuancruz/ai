# Knowledge Component

A web crawler and document processing system that converts web content into searchable knowledge vectors.

## What it does

The Knowledge component takes websites, crawls them, extracts text content from HTML, splits it into chunks, and creates embeddings for semantic search.

## Core Components

### KnowledgeService
Main orchestration service that coordinates the knowledge pipeline. Handles document processing, vector storage, and semantic search with configurable result limits (default: 3 results).

### SourceService
Manages source definitions and coordinates with the knowledge service to process web content. Acts as the entry point for creating and managing crawl sources.

### CrawlerService  
Handles web crawling with multiple strategies:
- **Single page**: Loads only one specific page
- **Recursive**: Follows internal links within the domain (depth: 3, max pages: 50)
- **Sitemap**: Uses XML sitemaps to discover pages

### WebLoader
Performs web content extraction with HTML cleaning:
- Removes script, style, and noscript tags
- Extracts only visible text content
- Uses BeautifulSoup with html.parser for processing
- Configurable timeouts (30s) and request delays

### DocumentService
Processes raw web content by splitting text into chunks using LangChain's text splitter.

### VectorStoreService
Manages document embeddings in AWS S3 Vector Store, handling vector storage and retrieval operations with configurable search results.

## How it works

```
Source URL → WebLoader (HTML Cleaning) → Documents → Text Splitting → Embeddings → Vector Storage → Semantic Search
```

1. **Source Creation**: Define a website to crawl with configurable parameters
2. **Web Crawling**: Extract content from web pages with HTML cleaning  
3. **Content Cleaning**: Remove HTML tags, scripts, and styling - keep only text
4. **Document Processing**: Split content into chunks
5. **Embedding Generation**: Create vector representations using AWS Bedrock Titan v2
6. **Vector Storage**: Store embeddings in S3 for semantic search
7. **Search & Retrieval**: Return top-k most relevant results (default: 3)

## HTML Content Processing

The system includes HTML cleaning to ensure text extraction:

- **Tag Removal**: Strips HTML tags, attributes, and formatting
- **Script Cleaning**: Removes JavaScript, CSS, and other non-content elements  
- **Text Extraction**: Uses BeautifulSoup to extract text content
- **Parser**: Uses built-in html.parser for cross-platform compatibility
- **Content Quality**: Search results contain text instead of raw HTML

## Crawling Strategies & Configuration

### Single Page
Processes only the specified URL without following any links.

### Recursive  
Follows internal links within the same domain up to 3 levels deep, processing up to 50 pages maximum. Includes request delays to be respectful to target servers.

### Sitemap
Parses XML sitemaps to discover and crawl pages systematically, respecting the same page limits.

## Document Processing

Text content is split into chunks for embedding and retrieval:
- Uses recursive character splitting to maintain context
- Preserves semantic boundaries (paragraphs, sentences)
- Includes overlap between chunks to maintain continuity

## Vector Storage

Documents are converted to embeddings using AWS Bedrock Titan model and stored in S3 Vector Store:
- Generates vector representations
- Enables semantic similarity search
- Maintains metadata for source tracking

## Search Capabilities

Once processed, documents support semantic search with configurable precision:
- Find contextually relevant content using natural language queries
- Filter by source or metadata for targeted searches
- Ranked results by similarity score with top-k selection (default: 3 results)
- Text results without HTML artifacts

## Configuration

### Crawler Settings
- **Max Depth**: 3 levels (recursive crawling)
- **Max Pages**: 50 pages per source
- **Timeout**: 30 seconds per request
- **Request Delay**: 1 second between requests
- **Max Concurrent**: 5 simultaneous requests

### Search Settings  
- **Default Results**: 3 most relevant documents
- **Embedding Model**: AWS Bedrock Titan Text v2
- **Vector Store**: AWS S3 Vector Store

## File Structure

- `source_service.py` - Source management and coordination
- `service.py` - Main knowledge processing orchestration (KnowledgeService)
- `crawler/` - Web crawling components with HTML cleaning
  - `service.py` - Crawling orchestration
  - `loaders.py` - WebLoader with intelligent HTML processing
- `document_service.py` - Text processing and chunking  
- `vector_store/` - Vector storage management with configurable search
- `models.py` - Data models including KBSearchResult
- `repository.py` - Source persistence and management
