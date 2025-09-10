# Data Stores and Information Lifecycle

This document provides a comprehensive overview of all **actually implemented** data stores in the Verde AI application, their purposes, storage mechanisms, and data lifecycles. This serves as a reference for understanding where information is stored and how it flows through the system.

## Overview

Verde AI uses a **polyglot persistence approach** with multiple specialized storage systems, each optimized for specific data types and access patterns. The system follows a **user-centric architecture** where all data is isolated by `user_id` and follows strict security and privacy guidelines.

## 1. Session Store (In-Memory)

**Purpose**: Temporary conversation state and user session management  
**Technology**: In-memory Python dictionaries with TTL  
**Location**: `app/repositories/session_store.py`

### What it stores:
- **Conversation messages**: Complete chat history (user + assistant messages)
- **User context**: Current user profile data as JSON
- **Thread metadata**: Session timestamps, user mappings
- **Locks**: Per-session async locks for concurrency control

### How it works:
- **TTL-based expiration**: Sessions expire after 30 days (configurable)
- **Automatic cleanup**: Periodic cleanup task removes expired sessions
- **User-thread mapping**: Maintains `user_id` → `thread_id` relationships
- **Thread isolation**: Each conversation thread has its own session

### Data lifecycle:
1. **Creation**: New session created when user starts conversation
2. **Updates**: Messages appended to conversation history
3. **Access tracking**: `last_accessed` timestamp updated on each interaction
4. **Expiration**: Sessions automatically cleaned up after TTL
5. **Cleanup**: Expired sessions removed from memory

### Key methods:
- `set_session()`: Store session data
- `get_session()`: Retrieve session with access tracking
- `get_user_threads()`: Get all threads for a user
- `cleanup_expired()`: Remove expired sessions

---

## 2. PostgreSQL Database (Aurora)

**Purpose**: Persistent user data and application state  
**Technology**: Amazon Aurora PostgreSQL  
**Location**: `app/db/models/`, `app/repositories/postgres/`

### What it stores:

#### User Context Table (`user_contexts`)
- **Core profile**: `user_id`, `email`, `preferred_name`, `pronouns`
- **Financial context**: `income_band`, `rent_mortgage`, `primary_financial_goal`
- **Preferences**: `language`, `tone_preference`, `subscription_tier`
- **Structured data**: JSONB fields for complex nested data
  - `identity`: Personal identity information
  - `safety`: Content safety preferences
  - `style`: Communication style preferences
  - `location`: Geographic and location data
  - `goals`: Financial and personal goals
  - `household`: Family and household information
  - `budget_posture`: Budget-related preferences

### How it works:
- **Repository pattern**: Clean separation between data access and business logic
- **Async operations**: All database operations are async
- **Connection pooling**: Managed by SQLAlchemy async session factory
- **User isolation**: All queries filtered by `user_id`

### Data lifecycle:
1. **Creation**: User context created during onboarding
2. **Updates**: Profile data updated through conversation and external sync
3. **Sync**: External user context synced from FOS service
4. **Querying**: Financial data queried via SQL through finance repository
5. **Persistence**: All changes committed to database

### Key repositories:
- `PostgresUserRepository`: User context CRUD operations
- `FinanceRepository`: Financial data querying with user isolation

---

## 3. Plaid Financial Database (External)

**Purpose**: External financial data access via direct SQL queries  
**Technology**: External PostgreSQL database with Plaid data  
**Location**: `app/repositories/postgres/finance_repository.py`

### What it stores:
- **Accounts**: Plaid account information
- **Transactions**: Transaction history and details
- **Balances**: Account balances and financial data

### How it works:
- **Direct SQL connection**: Connects to external Plaid database
- **User isolation**: All queries filtered by `user_id` parameter
- **Dynamic queries**: SQL queries generated and executed dynamically
- **Read-only access**: Only query operations, no data modification

### Data lifecycle:
1. **Connection**: Connection established to external Plaid database
2. **Query execution**: SQL queries executed with user isolation
3. **Data retrieval**: Financial data returned for analysis
4. **Processing**: Data processed by finance agent for user queries

---

## 4. S3 Vectors Store (Semantic Memory)

**Purpose**: Vector-based semantic memory for conversation context  
**Technology**: Amazon S3 Vectors with Bedrock embeddings  
**Location**: `app/repositories/s3_vectors_store.py`

### What it stores:
- **Semantic memories**: User preferences and profile information
- **Episodic memories**: Turn-by-turn conversation history
- **Vector embeddings**: Text content converted to high-dimensional vectors
- **Metadata**: Timestamps, categories, source information

### Memory Categories:
- `Finance`: Financial-related memories
- `Budget`: Budget and spending memories
- `Goals`: Goal-related memories
- `Personal`: Personal information memories
- `Education`: Learning and education memories
- `Conversation_Summary`: Conversation summaries
- `Other`: Miscellaneous memories

### How it works:
- **Vector search**: Semantic similarity search using cosine distance
- **Namespace isolation**: Data organized by `user_id` and memory type
- **Embedding generation**: Text content embedded using Bedrock Titan model
- **Metadata filtering**: Filtering by categories and timestamps

### Data lifecycle:
1. **Creation**: Memories created during conversations
2. **Indexing**: Text content embedded and stored with metadata
3. **Retrieval**: Relevant memories retrieved via semantic search
4. **Context injection**: Retrieved memories injected into conversation context
5. **Cleanup**: Old memories may be archived or deleted

### Key operations:
- `put()`: Store new memory with embedding
- `search()`: Semantic search for relevant memories
- `get()`: Retrieve specific memory by key
- `delete()`: Remove specific memory

---

## 5. External User Context (FOS Service)

**Purpose**: External user profile synchronization  
**Technology**: HTTP API integration  
**Location**: `app/services/external_context/user/`

### What it stores:
- **AI context**: External user profile data from FOS service
- **Mapping data**: Transformed user context for external consumption
- **Sync state**: Synchronization status and metadata

### How it works:
- **Bidirectional sync**: Load from external service, export updates back
- **Mapping functions**: Transform between internal and external formats
- **Fallback handling**: Graceful degradation when external service unavailable
- **Real-time updates**: Context refreshed on each conversation turn

### Data lifecycle:
1. **Loading**: User context loaded from external service on conversation start
2. **Mapping**: External data mapped to internal UserContext format
3. **Updates**: Context updated during conversation
4. **Export**: Updated context exported back to external service
5. **Fallback**: Internal context used if external service unavailable

### Key components:
- `ExternalUserRepository`: HTTP client for external API
- `map_ai_context_to_user_context()`: External → internal mapping
- `map_user_context_to_ai_context()`: Internal → external mapping

---

## 6. SSE Queue Store (In-Memory)

**Purpose**: Real-time streaming for Server-Sent Events  
**Technology**: In-memory asyncio.Queue  
**Location**: `app/core/app_state.py`

### What it stores:
- **Event queues**: Per-thread queues for SSE events
- **Text tracking**: Last emitted text to prevent duplicates
- **Thread metadata**: Queue creation timestamps

### How it works:
- **Per-thread queues**: Each conversation thread has its own event queue
- **Event streaming**: Real-time events pushed to client via SSE
- **Duplicate prevention**: Tracks last emitted text to avoid duplicates
- **Automatic cleanup**: Queues cleaned up when threads expire

### Data lifecycle:
1. **Creation**: Queue created when thread starts
2. **Event pushing**: Events pushed to queue during conversation
3. **Streaming**: Events streamed to client via SSE
4. **Cleanup**: Queue removed when thread expires

### Key operations:
- `get_sse_queue()`: Get or create queue for thread
- `drop_sse_queue()`: Remove queue for thread
- `get_last_emitted_text()`: Get last text to prevent duplicates

---

## 7. Onboarding State Store (In-Memory)

**Purpose**: Temporary onboarding conversation state  
**Technology**: In-memory Python dictionaries  
**Location**: `app/core/app_state.py`

### What it stores:
- **Onboarding state**: Current step, conversation history, user context
- **Thread metadata**: Thread timestamps and access tracking
- **User mappings**: User ID to thread relationships

### How it works:
- **Step tracking**: Current onboarding step stored in state
- **Conversation history**: Complete onboarding conversation history
- **User context**: User profile data collected during onboarding
- **TTL management**: Threads expire after 60 minutes of inactivity

### Data lifecycle:
1. **Creation**: State created when onboarding starts
2. **Updates**: State updated as user progresses through steps
3. **Persistence**: Final state persisted to PostgreSQL when complete
4. **Cleanup**: State removed when thread expires or onboarding completes

---

## 8. Knowledge Sources Store (JSON File)

**Purpose**: Knowledge base sources management  
**Technology**: JSON file storage  
**Location**: `app/knowledge/sources/repository.py`

### What it stores:
- **Source metadata**: URLs, descriptions, categories
- **Crawl configuration**: Depth, page limits, include/exclude patterns
- **Source status**: Enabled/disabled state

### How it works:
- **File-based storage**: Sources stored in JSON file
- **CRUD operations**: Add, update, delete sources
- **Source management**: Find by ID or URL

### Data lifecycle:
1. **Loading**: Sources loaded from JSON file on startup
2. **Updates**: Sources added/updated/removed via repository methods
3. **Persistence**: Changes saved back to JSON file
4. **Usage**: Sources used for knowledge retrieval

---

## 9. Knowledge Vector Store (S3 Vectors)

**Purpose**: Vector storage for knowledge base documents  
**Technology**: Amazon S3 Vectors  
**Location**: `app/knowledge/vector_store/service.py`

### What it stores:
- **Document chunks**: Text chunks from knowledge sources
- **Vector embeddings**: Document content converted to vectors
- **Metadata**: Source information, chunk indices, content hashes

### How it works:
- **Document indexing**: Documents chunked and embedded
- **Similarity search**: Vector similarity search for relevant content
- **Source management**: Delete documents by source ID
- **Batch operations**: Efficient batch processing for large datasets

### Data lifecycle:
1. **Indexing**: Documents chunked and embedded into vectors
2. **Storage**: Vectors stored in S3 Vectors with metadata
3. **Retrieval**: Similarity search for relevant content
4. **Cleanup**: Documents deleted by source ID when needed

---

## 10. Finance Agent Cache (In-Memory)

**Purpose**: Per-user caching for finance agent prompts  
**Technology**: In-memory dictionaries with TTL  
**Location**: `app/agents/supervisor/finance_agent/agent.py`

### What it stores:
- **Sample data**: Transaction and account samples for prompt grounding
- **Cache metadata**: Timestamps, TTL information
- **User isolation**: Separate cache per user

### How it works:
- **TTL-based expiration**: Cache expires after 10 minutes
- **User isolation**: Each user has separate cache
- **Sample generation**: Fresh samples generated when cache expires
- **Prompt grounding**: Cached samples used to ground finance prompts

### Data lifecycle:
1. **Creation**: Cache created on first finance query
2. **Population**: Sample data fetched and cached
3. **Usage**: Cached data used for prompt grounding
4. **Expiration**: Cache expires after TTL
5. **Refresh**: New samples fetched when cache expires

---

## Data Flow and Lifecycle

### Conversation Flow:
1. **Session Creation**: New session created in session store
2. **Context Loading**: User context loaded from PostgreSQL and external service
3. **Memory Retrieval**: Relevant memories retrieved from S3 Vectors
4. **Conversation Processing**: Messages processed and stored in session
5. **Context Updates**: User context updated based on conversation
6. **Memory Storage**: New memories stored in S3 Vectors
7. **Context Persistence**: Updated context persisted to PostgreSQL and external service

### User Onboarding Flow:
1. **State Creation**: Onboarding state created in memory
2. **Step Progression**: State updated as user progresses through steps
3. **Context Collection**: User context collected and stored in state
4. **Final Persistence**: Complete context persisted to PostgreSQL
5. **State Cleanup**: Onboarding state removed from memory

### Memory Management:
1. **Memory Creation**: New memories created during conversations
2. **Vector Embedding**: Text content embedded using Bedrock
3. **Storage**: Memories stored in S3 Vectors with metadata
4. **Retrieval**: Relevant memories retrieved via semantic search
5. **Context Injection**: Memories injected into conversation context
6. **Archival**: Old memories may be archived or deleted

## Security and Privacy

### Data Isolation:
- **User isolation**: All data filtered by `user_id`
- **Thread isolation**: Each conversation thread has separate storage
- **Namespace isolation**: Vector data organized by user and type

### Encryption:
- **At rest**: All persistent data encrypted with KMS-managed keys
- **In transit**: All data encrypted using TLS
- **PII handling**: Sensitive data redacted in logs and traces

### Access Control:
- **Repository pattern**: Clean separation of data access
- **Async operations**: Non-blocking database operations
- **Connection pooling**: Efficient database connection management

## Performance Considerations

### Caching Strategy:
- **Session cache**: In-memory for fast access
- **Finance cache**: Per-user TTL-based caching
- **Memory cache**: Vector search results cached

### Scalability:
- **Horizontal scaling**: Stateless services can scale horizontally
- **Database scaling**: Aurora PostgreSQL auto-scaling
- **Vector scaling**: S3 Vectors handles high-dimensional data efficiently

### Monitoring:
- **TTL tracking**: Automatic cleanup of expired data
- **Size limits**: Maximum thread and queue limits
- **Error handling**: Graceful degradation when services unavailable

This architecture ensures that Verde AI can efficiently manage user data while maintaining security, privacy, and performance across all storage systems.
