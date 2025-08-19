# Knowledge Component

A web crawler and document processing system that converts web content into searchable knowledge vectors.

## What it does

The Knowledge component takes websites, crawls them, extracts content, splits it into chunks, and creates embeddings for semantic search.

## Core Components

### SourceService
Main entry point that orchestrates the entire knowledge pipeline. Manages sources and coordinates crawling and document processing.

### CrawlerService  
Handles web crawling with different strategies:
- **Single page**: Loads only one specific page
- **Recursive**: Follows internal links within the domain
- **Sitemap**: Uses XML sitemaps to discover pages

### DocumentService
Processes raw web content by splitting text into optimized chunks using LangChain's text splitter.

### VectorStoreService
Manages document embeddings in AWS S3 Vector Store, handling vector storage and retrieval operations.

## How it works

```
Source URL → Crawler → Documents → Text Splitting → Embeddings → Vector Storage
```

1. **Source Creation**: Define a website to crawl
2. **Web Crawling**: Extract content from web pages  
3. **Document Processing**: Split content into manageable chunks
4. **Embedding Generation**: Create vector representations using AWS Bedrock
5. **Vector Storage**: Store embeddings in S3 for semantic search

## Crawling Strategies

### Single Page
Processes only the specified URL without following any links.

### Recursive  
Follows internal links within the same domain up to a specified depth. Respects domain boundaries and page limits.

### Sitemap
Parses XML sitemaps to discover and crawl pages systematically.

## Document Processing

Text content is split into chunks for optimal embedding and retrieval:
- Uses recursive character splitting to maintain context
- Preserves semantic boundaries (paragraphs, sentences)
- Includes overlap between chunks to maintain continuity

## Vector Storage

Documents are converted to embeddings using AWS Bedrock Titan model and stored in S3 Vector Store:
- Generates high-dimensional vector representations
- Enables semantic similarity search
- Maintains metadata for source tracking

## Search Capabilities

Once processed, documents support semantic search:
- Find contextually relevant content
- Filter by source or metadata
- Ranked results by similarity score

## File Structure

- `source_service.py` - Main orchestration service
- `crawler/` - Web crawling components
- `document_service.py` - Text processing and chunking  
- `vector_store/` - Vector storage management
- `service.py` - Knowledge processing orchestration
- `models.py` - Data models and schemas
- `repository.py` - Source persistence
