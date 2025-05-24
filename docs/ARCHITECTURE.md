# VCBot Architecture Documentation

## Overview

VCBot is designed with a modular, scalable architecture that separates concerns and promotes maintainability. The bot follows Domain-Driven Design (DDD) principles with clear boundaries between layers.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Discord API                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                    Presentation Layer                        │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │   Commands  │  │   Events     │  │  Message Router │   │
│  │  (/helper)  │  │  (on_ready)  │  │                 │   │
│  └──────┬──────┘  └──────┬───────┘  └────────┬────────┘   │
└─────────┼─────────────────┼──────────────────┼─────────────┘
          │                 │                  │
┌─────────▼─────────────────▼──────────────────▼─────────────┐
│                     Service Layer                           │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ AI Service  │  │ Bill Service │  │Reference Service│   │
│  │             │  │              │  │                 │   │
│  └──────┬──────┘  └──────┬───────┘  └────────┬────────┘   │
└─────────┼─────────────────┼──────────────────┼─────────────┘
          │                 │                  │
┌─────────▼─────────────────▼──────────────────▼─────────────┐
│                   Repository Layer                          │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │   Base      │  │     Bill     │  │  BillReference  │   │
│  │ Repository  │  │  Repository  │  │   Repository    │   │
│  └──────┬──────┘  └──────┬───────┘  └────────┬────────┘   │
└─────────┼─────────────────┼──────────────────┼─────────────┘
          │                 │                  │
┌─────────▼─────────────────▼──────────────────▼─────────────┐
│                    Data Storage Layer                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ JSON Files  │  │   PDF Files  │  │    External     │   │
│  │             │  │              │  │      APIs       │   │
│  └─────────────┘  └──────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Presentation Layer

The presentation layer handles all Discord interactions and user-facing functionality.

#### Commands (`main.py`)

```python
@bot.tree.command(name="helper")
async def helper(interaction: discord.Interaction, query: str):
    """Main command handler for AI assistance."""
    # Handles Discord slash commands
    # Routes to appropriate services
    # Manages response formatting
```

**Responsibilities:**
- Parse Discord commands
- Validate user permissions
- Format and send responses
- Handle Discord-specific features (embeds, files, etc.)

#### Message Router (`message_router.py`)

Intelligent routing system for processing different types of messages:

```python
class MessageRouter:
    def __init__(self, services: Dict[str, Any]):
        self.ai_service = services.get('ai_service')
        self.bill_service = services.get('bill_service')
        
    async def route_message(self, message: str) -> Response:
        # Analyzes message intent
        # Routes to appropriate service
        # Handles multi-service coordination
```

### 2. Service Layer

The service layer contains all business logic and orchestrates operations between different components.

#### AI Service (`services/ai_service.py`)

Integrates with Google Gemini for intelligent responses:

```python
class AIService:
    def __init__(self, api_key: str, model_name: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model_name
        
    async def process_query(self, query: str, user_id: int) -> AIResponse:
        # Builds context-aware prompts
        # Manages conversation history
        # Handles tool calls
        # Implements rate limiting
```

**Key Features:**
- Context-aware responses
- Tool integration (search, calculations)
- User permission handling
- Rate limiting and retry logic

#### Bill Service (`services/bill_service.py`)

Manages congressional bill operations:

```python
class BillService:
    def __init__(self, genai_client, bill_directories: Dict[str, str]):
        self.genai_client = genai_client
        self.bill_directories = bill_directories
        
    def search_bills(self, query: str, top_k: int = 5) -> List[Bill]:
        # Keyword search through titles and content
        # Ranking and filtering
        # Metadata enrichment
```

**Key Features:**
- Keyword search capabilities
- Bill metadata management
- Caching for performance
- PDF file attachment handling

#### Reference Service (`services/reference_service.py`)

Manages bill reference numbers with thread safety:

```python
class ReferenceService:
    def __init__(self, ref_file: str, repository: Repository):
        self.repository = repository
        self._lock = threading.Lock()
        
    async def get_next_reference(self, bill_type: str) -> int:
        # Thread-safe reference generation
        # Atomic increment operations
        # Persistence management
```

### 3. Repository Layer

Implements the repository pattern for data persistence abstraction.

#### Base Repository (`repositories/base.py`)

```python
class Repository(ABC, Generic[T]):
    @abstractmethod
    async def save(self, entity: T) -> None:
        """Save an entity."""
        pass
    
    @abstractmethod
    async def find_by_id(self, id: str) -> Optional[T]:
        """Find entity by ID."""
        pass
```

**Benefits:**
- Swappable storage backends
- Consistent interface
- Testability
- Future database migration path

#### Implementation Example (`repositories/bill_reference.py`)

```python
class BillReferenceRepository(Repository[BillReference]):
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()
        
    async def save(self, entity: BillReference) -> None:
        async with self._lock:
            # Atomic file operations
            # JSON serialization
            # Error handling
```

### 4. Data Models

Type-safe data structures using dataclasses and enums.

#### Models (`models.py`)

```python
@dataclass
class BillReference:
    bill_type: BillType
    reference_number: int
    created_at: datetime
    updated_at: datetime

class BillType(str, Enum):
    HR = "hr"
    S = "s"
    HRES = "hres"
    # ... other types
```

### 5. Cross-Cutting Concerns

#### Error Handling (`exceptions.py`)

Custom exception hierarchy:

```python
class VCBotError(Exception):
    """Base exception for VCBot."""
    pass

class ConfigurationError(VCBotError):
    """Configuration-related errors."""
    pass

class AIServiceError(VCBotError):
    """AI service errors."""
    pass
```

#### Logging (`logging_config.py`)

Structured logging configuration:

```python
LOGGING_CONFIG = {
    'version': 1,
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/vcbot.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        }
    }
}
```

#### Configuration (`config.py`)

Environment-based configuration:

```python
class Settings(BaseSettings):
    discord_token: str
    gemini_api_key: str
    model_name: str = "gemini-1.5-pro-002"
    
    class Config:
        env_file = ".env"
```

## Design Patterns

### 1. Repository Pattern

Abstracts data persistence:
- Enables testing with mock repositories
- Supports future migration to databases
- Provides consistent data access interface

### 2. Service Layer Pattern

Encapsulates business logic:
- Clear separation from presentation
- Reusable across different interfaces
- Testable in isolation

### 3. Dependency Injection

Services receive dependencies:
```python
def __init__(self, repository: Repository):
    self.repository = repository
```

### 4. Async/Await Pattern

Non-blocking I/O throughout:
```python
async def process_request():
    results = await asyncio.gather(
        service1.operation(),
        service2.operation()
    )
```

## Data Flow

### Command Processing Flow

1. **User Input** → Discord sends slash command
2. **Command Handler** → Validates and parses input
3. **Service Layer** → Processes business logic
4. **Repository Layer** → Persists/retrieves data
5. **Response Formatting** → Prepares Discord response
6. **User Output** → Sends formatted response

### Example: Bill Search

```
User: /search healthcare reform
         ↓
Command Handler: Parse query
         ↓
Bill Service: Keyword search
         ↓
Search: Find matching bills
         ↓
Ranking: Score and sort results
         ↓
Formatter: Create Discord embed + PDF attachments
         ↓
Response: Display results to user
```

## Scalability Considerations

### Horizontal Scaling

- **Stateless Services**: Services don't maintain session state
- **Shared Storage**: File-based storage can be replaced with distributed systems
- **Queue Integration**: Ready for message queue integration

### Vertical Scaling

- **Async Operations**: Efficient resource utilization
- **Caching**: In-memory caching for frequent operations
- **Lazy Loading**: Load resources on demand

## Security Architecture

### Authentication & Authorization

```python
class AIService:
    def __init__(self, authorized_users: List[int], admin_users: List[int]):
        self.authorized_users = set(authorized_users)
        self.admin_users = set(admin_users)
    
    def _is_authorized(self, user_id: int) -> bool:
        return user_id in self.authorized_users
```

### API Key Management

- Environment variables for secrets
- No hardcoded credentials
- Secure configuration loading

### Input Validation

- Pydantic models for type validation
- Sanitization of user inputs
- Rate limiting on API calls

## Testing Strategy

### Unit Tests

Test individual components:
```python
def test_bill_service_search():
    service = BillService(mock_genai_client, mock_directories)
    results = service.search_bills("test query")
    assert len(results) > 0
```

### Integration Tests

Test component interactions:
```python
async def test_ai_service_with_repository():
    repo = MockRepository()
    service = AIService(api_key, model, repository=repo)
    response = await service.process_query("test", user_id)
    assert repo.save.called
```

### End-to-End Tests

Test complete workflows:
```python
async def test_command_flow():
    interaction = MockInteraction()
    await helper(interaction, "What is HR 123?")
    assert "HR 123" in interaction.response
```

## Performance Optimizations

### Caching Strategy

- **In-Memory Cache**: Frequently accessed data
- **TTL Management**: Expire stale data
- **Cache Invalidation**: Update on changes

### Async I/O

- **Concurrent Operations**: `asyncio.gather()` for parallel tasks
- **Non-Blocking File I/O**: `aiofiles` for file operations
- **Connection Pooling**: Reuse API connections

### Resource Management

- **Lazy Loading**: Load bill data on first use
- **Memory Limits**: Bounded caches
- **Graceful Degradation**: Fallback on resource constraints

## Future Enhancements

### Planned Features

1. **Database Migration**
   - PostgreSQL for structured data
   - Redis for caching
   - Full-text search database for improved search

2. **Microservices Architecture**
   - Separate AI service
   - Independent bill service
   - API gateway

3. **Enhanced Monitoring**
   - Prometheus metrics
   - Grafana dashboards
   - Distributed tracing

### Extension Points

- **Plugin System**: Dynamic command loading
- **Webhook Support**: External integrations
- **Multi-Language**: Internationalization support

---

This architecture provides a solid foundation for current needs while maintaining flexibility for future growth and changes.