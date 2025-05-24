# VCBot API Documentation

## Overview

VCBot provides a comprehensive API for interacting with Virtual Congress operations through Discord. This document describes the available services, their methods, and usage patterns.

## Core Services

### AIService

The AI service integrates with Google Gemini to provide intelligent responses to user queries.

#### Class: `AIService`

```python
from services.ai_service import AIService

ai_service = AIService(
    api_key="your_gemini_api_key",
    model_name="gemini-1.5-pro-002",
    authorized_users=[123456789],
    admin_users=[987654321]
)
```

#### Methods

##### `process_query(query: str, user_id: int, context: Optional[str] = None) -> AIResponse`

Process a user query and return an AI-generated response.

**Parameters:**
- `query` (str): The user's question or request
- `user_id` (int): Discord user ID for permissions checking
- `context` (Optional[str]): Additional context for the query

**Returns:**
- `AIResponse`: Object containing response text and tool calls

**Example:**
```python
response = await ai_service.process_query(
    query="What is the status of HR 4523?",
    user_id=123456789,
    context="Previous discussion about healthcare bills"
)
print(response.text)
```

##### `_build_system_prompt(user_id: int) -> str`

Build a system prompt based on user permissions.

**Parameters:**
- `user_id` (int): Discord user ID

**Returns:**
- `str`: Formatted system prompt

### BillService

Manages congressional bill operations including search and retrieval.

#### Class: `BillService`

```python
from services.bill_service import BillService

bill_service = BillService(
    genai_client=genai_client,
    bill_directories={"bills": "every-vc-bill/txts", "billpdfs": "every-vc-bill/pdfs"}
)
```

#### Methods

##### `search_bills(query: str, top_k: int = 5) -> List[Dict[str, Any]]`

Search for bills using keyword matching through titles, content, and metadata.

**Parameters:**
- `query` (str): Search query
- `top_k` (int): Number of results to return (default: 5)

**Returns:**
- `List[Dict[str, Any]]`: List of matching bills with metadata

**Example:**
```python
results = bill_service.search_bills("healthcare reform", top_k=10)
for bill in results:
    print(f"{bill['title']} - Score: {bill['score']}")
```

##### `get_latest_bill(bill_type: str) -> Dict[str, Any]`

Get the most recent bill of a specific type.

**Parameters:**
- `bill_type` (str): Type of bill (e.g., "hr", "s", "sconres")

**Returns:**
- `Dict[str, Any]`: Bill information

**Example:**
```python
latest_hr = bill_service.get_latest_bill("hr")
print(f"Latest HR: {latest_hr['title']}")
```

### ReferenceService

Manages bill reference numbers with thread-safe operations.

#### Class: `ReferenceService`

```python
from services.reference_service import ReferenceService

ref_service = ReferenceService(
    ref_file="bill_refs.json",
    repository=BillReferenceRepository("bill_refs.json")
)
```

#### Methods

##### `get_next_reference(bill_type: str) -> int`

Get the next available reference number for a bill type.

**Parameters:**
- `bill_type` (str): Type of bill

**Returns:**
- `int`: Next reference number

**Example:**
```python
next_hr_num = ref_service.get_next_reference("hr")
print(f"Next HR number: {next_hr_num}")
```

##### `async get_next_reference_async(bill_type: str) -> int`

Async version of get_next_reference.

**Parameters:**
- `bill_type` (str): Type of bill

**Returns:**
- `int`: Next reference number

**Example:**
```python
next_s_num = await ref_service.get_next_reference_async("s")
print(f"Next S number: {next_s_num}")
```

##### `set_reference(bill_type: str, reference_number: int) -> None`

Set a specific reference number for a bill type.

**Parameters:**
- `bill_type` (str): Type of bill
- `reference_number` (int): Reference number to set

**Example:**
```python
ref_service.set_reference("hr", 4525)
```

## Data Models

### BillType Enum

```python
from models import BillType

class BillType(str, Enum):
    HR = "hr"
    S = "s"
    HRES = "hres"
    SRES = "sres"
    HJRES = "hjres"
    SJRES = "sjres"
    HCONRES = "hconres"
    SCONRES = "sconres"
```

### BillReference Model

```python
from models import BillReference

@dataclass
class BillReference:
    bill_type: BillType
    reference_number: int
    created_at: datetime
    updated_at: datetime
```

### AIResponse Model

```python
from services.ai_service import AIResponse

@dataclass
class AIResponse:
    text: str
    tool_calls: List[Dict[str, Any]]
    error: Optional[str] = None
```

## Repository Pattern

### Base Repository

```python
from repositories.base import Repository

class Repository(ABC, Generic[T]):
    @abstractmethod
    async def save(self, entity: T) -> None:
        pass
    
    @abstractmethod
    async def find_by_id(self, id: str) -> Optional[T]:
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> None:
        pass
```

### BillReferenceRepository

```python
from repositories.bill_reference import BillReferenceRepository

repo = BillReferenceRepository("bill_refs.json")

# Get next reference
next_ref = await repo.get_next_reference(BillType.HR)

# Save reference
ref = BillReference(
    bill_type=BillType.HR,
    reference_number=4525,
    created_at=datetime.now(),
    updated_at=datetime.now()
)
await repo.save(ref)
```

## Error Handling

### Custom Exceptions

```python
from exceptions import (
    ConfigurationError,
    AIServiceError,
    BillNotFoundError,
    ReferenceError
)

try:
    response = await ai_service.process_query(query, user_id)
except AIServiceError as e:
    print(f"AI service error: {e}")
except ConfigurationError as e:
    print(f"Configuration error: {e}")
```

## Async Operations

All I/O operations are async-first:

```python
import asyncio

async def main():
    # Initialize services
    ai_service = AIService(api_key, model_name)
    bill_service = BillService(bill_dir, embeddings_path)
    ref_service = ReferenceService(ref_file)
    
    # Concurrent operations
    results = await asyncio.gather(
        ai_service.process_query("What is HR 4523?", user_id),
        bill_service.search_bills("healthcare"),
        ref_service.get_next_reference_async("hr")
    )
    
    ai_response, bills, next_ref = results

asyncio.run(main())
```

## Rate Limiting

The AI service implements rate limiting:

```python
# Rate limits are configured per user
response = await ai_service.process_query(query, user_id)
# Automatic rate limit handling with exponential backoff
```

## Testing

### Unit Testing Services

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_ai_service():
    mock_client = Mock()
    ai_service = AIService("key", "model")
    ai_service.client = mock_client
    
    response = await ai_service.process_query("test", 123)
    assert response.text == "expected response"
```

### Integration Testing

```python
@pytest.mark.integration
async def test_full_flow():
    # Test complete user interaction flow
    ai_service = AIService(api_key, model_name)
    response = await ai_service.process_query(
        "Search for healthcare bills",
        user_id=123
    )
    assert "healthcare" in response.text.lower()
```

## Performance Considerations

1. **Caching**: Implement caching for frequently accessed data
2. **Connection Pooling**: Reuse API connections
3. **Async I/O**: All file and network operations are non-blocking
4. **Batching**: Batch API requests when possible

## Security

1. **API Key Management**: Store keys in environment variables
2. **User Authorization**: Validate user permissions before operations
3. **Input Validation**: Sanitize all user inputs
4. **Rate Limiting**: Prevent API abuse

## Versioning

API follows semantic versioning:
- Major version: Breaking changes
- Minor version: New features (backward compatible)
- Patch version: Bug fixes

Current version: 1.0.0

---

For more examples and advanced usage, see the examples directory.