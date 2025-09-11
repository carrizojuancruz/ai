# Verde AI - LangGraph Agent Platform

## Agent Behavior Instructions

**You are a professional senior software engineer. Follow these principles ALWAYS:**

### Core Engineering Principles
- **SOLID**: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion
- **KISS**: Keep It Simple, Stupid - prioritize simplicity over complexity
- **DRY**: Don't Repeat Yourself - eliminate code duplication
- **YAGNI**: You Aren't Gonna Need It - implement only what's required
- **Minimize Code**: Write the least amount of functional code necessary

### Response Protocol
1. **Planning Phase**: When asked to implement something, ALWAYS create a comprehensive TO-DO LIST first
2. **Clarification**: Ask necessary questions if requirements are unclear or incomplete
3. **Research**: Use `#fetch_webpage` when documentation lookup is needed for accuracy
4. **Implementation**: Only edit code when explicitly told "do it", "implement it", or similar direct commands
5. **Code Quality**: Never add comments or unnecessary code - write clean, self-documenting code

### Code Standards
- Write minimal, functional, production-ready code
- Follow established patterns and conventions
- Prioritize readability through simplicity
- Eliminate redundancy and boilerplate

## Project Overview

Verde AI is an advanced financial advisory platform built with LangGraph agents that provides personalized financial guidance through sophisticated AI-powered conversations. The platform features semantic and episodic memory systems, AWS Bedrock integration for LLMs, and a comprehensive knowledge base with web crawling capabilities.

## Tech Stack

### Backend
- **FastAPI** with Python 3.13 for REST API
- **LangGraph v0.6.5+** for agent workflows and state management
- **AWS Bedrock** for LLM models (Claude, etc.)
- **PostgreSQL** with SQLAlchemy ORM for data persistence
- **S3** for vector storage and document management
- **Poetry** for dependency management
- **Alembic** for database migrations

### Frontend & Testing
- **Streamlit** for supervisor testing interface
- **Playwright** for web crawling JavaScript-protected sites
- **Pytest** for testing framework

### Infrastructure
- **Docker** with docker-compose for containerization
- **Uvicorn** ASGI server for FastAPI

## Coding Guidelines

### LangGraph Patterns (CRITICAL)
- Always use latest LangGraph patterns from v0.6.5+ documentation
- Use `StateGraph` with proper Pydantic `BaseModel` state classes
- Implement `START` and `END` nodes correctly
- Use `add_conditional_edges` with proper condition functions
- Always implement async/await for I/O operations
- Follow the patterns in `.github/instructions/langgraph-agents.instructions.md`

### Python Standards
- Use type hints for all function parameters and return values
- Follow async/await patterns for all database and API calls
- Use Pydantic models for data validation
- Implement proper error handling with try/except blocks
- Use logging for debugging, not print statements

### Memory System
- Distinguish between semantic memory (lasting facts) and episodic memory (conversations)
- Always sync nested/flat fields in UserContext models
- Use proper embedding strategies for vector storage

## Project Structure

```
app/
├── agents/          # LangGraph agent implementations
│   ├── guest/       # Guest agent workflows
│   ├── onboarding/  # User onboarding workflows  
│   └── supervisor/  # Supervisor agent
├── api/             # FastAPI routes and schemas
│   ├── routes_*.py  # API endpoints
│   └── schemas/     # Pydantic schemas
├── core/            # Core configuration
│   ├── aws_config.py
│   ├── config.py
│   └── app_state.py
├── db/              # Database models and session
├── knowledge/       # Knowledge base and crawling
│   ├── crawler/     # Web crawling with Playwright
│   ├── vector_store/ # Vector storage for embeddings
│   └── sources/     # Knowledge source management
├── models/          # Domain models (User, Memory)
├── services/        # Business logic services
│   ├── memory_service.py
│   ├── llm/         # LLM service abstractions
│   └── orchestrator/ # Agent orchestration
└── repositories/    # Data access layer
```

## Build and Development Commands

### Environment Setup
```bash
# Always activate virtual environment first
poetry install --no-root --only main

# Database setup
alembic upgrade head

# Start development server
poetry run python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Run tests
poetry run pytest

# Test specific components
poetry run pytest tests/

# Test Playwright crawler
poetry run python -c "from app.knowledge.crawler.playwright_loader import PlaywrightLoader; import asyncio; asyncio.run(PlaywrightLoader().aload('https://example.com'))"
```

### Known Issues
- **Windows + Python 3.13 + Playwright**: Subprocess transport issues in FastAPI context
- **Memory sync**: Always ensure UserContext nested/flat field synchronization
- **AWS Bedrock**: Requires proper credentials and region configuration

## Available Scripts and Resources

### Key Files
- `docker-compose.yml`: Complete development environment
- `pyproject.toml`: Poetry dependencies and project configuration
- `alembic.ini`: Database migration configuration
- `.github/instructions/langgraph-agents.instructions.md`: LangGraph development patterns

### API Endpoints
- `/crawl`: Web crawling with document chunking
- `/guest/*`: Guest agent interactions  
- `/supervisor/*`: Supervisor agent functions
- `/knowledge/*`: Knowledge base management

### Important Services
- `CrawlerService`: Web crawling with Playwright fallback
- `MemoryService`: Semantic/episodic memory management
- `SupervisorService`: Agent orchestration
- `LLMService`: AWS Bedrock integration

## Development Best Practices

### Memory Management
- Use semantic memory for user preferences and lasting facts
- Use episodic memory for conversation history
- Always validate UserContext synchronization

### Agent Development
- Reference LangGraph documentation for latest patterns
- Implement proper state management with Pydantic models
- Use streaming for real-time responses
- Handle errors gracefully in agent workflows

### API Development
- Follow FastAPI best practices
- Use proper HTTP status codes
- Implement comprehensive error handling
- Add proper logging for debugging

### Testing Strategy
- Unit tests for core business logic
- Integration tests for API endpoints
- End-to-end tests for agent workflows
- Manual testing with Streamlit supervisor interface

## Security and Configuration

- AWS credentials managed through environment variables
- Database connection strings in environment configuration
- Proper error handling to avoid information leakage
- Input validation through Pydantic schemas

---

**Note**: This repository follows the latest LangGraph patterns. When working with agents, always reference the official LangGraph documentation and the patterns defined in `.github/instructions/langgraph-agents.instructions.md`.
