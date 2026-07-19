# Coding Standards and AI Agent Instructions

**Project:** Restaurant Intelligence Platform

**Document:** Engineering Rules for Developers and AI Coding Agents

**Version:** 1.0

**Status:** Draft


---

# 1. Purpose

This document defines the coding standards, engineering principles, and development rules for the Restaurant Intelligence Platform.

Every developer and AI coding agent must follow these rules.

The goal is to produce:

- Clean code
- Maintainable architecture
- Testable systems
- Predictable behavior
- Production-quality software


---

# 2. Core Engineering Philosophy


The project follows:

```
Clean Architecture

+

Domain Driven Design

+

Service Oriented Design

+

Test Driven Development

```

---

# 3. Golden Rules


## Rule 1

Never write code without understanding the architecture.


Before implementation:

Read:

```
Project Vision

System Architecture

Domain Model

API Design

```

---

## Rule 2

Business logic belongs in services.


Wrong:


```
APIView

↓

Business Logic

↓

Database

```


Correct:


```
APIView

↓

Service

↓

Repository

↓

Database

```

---

## Rule 3

AI code must be predictable.


Never:

- Hide logic inside prompts
- Trust LLM output blindly
- Skip validation

---

# 4. Backend Architecture Rules


Technology:


```
Python

Django

Django REST Framework

PostgreSQL

Redis

Celery

```


---

# 5. Django Application Structure


Recommended:


```
app/


models/

services/

repositories/

serializers/

views/

urls/

permissions/

tests/

utils/


```


---

# 6. Model Rules


Models should contain:

Allowed:

```
Fields

Relationships

Simple validation

Model metadata

```


Avoid:

```
Large business workflows

External API calls

AI logic

```


---

# 7. Service Layer Rules

Services contain all business operations.

Every domain app must have a Service class that encapsulates its business logic:

- `OrderService`
- `PaymentService`
- `ReservationService`
- `MenuService`
- `CartService`
- `AddressService`

Responsibilities:

- Business rules
- Transactions
- Workflow execution
- Error handling (domain-specific exception classes)

Example:

```python
class OrderService:

    def create_order(self, ...):
        validate_cart()
        calculate_total()
        create_order()
```

Services raise domain-specific exceptions (e.g. `OrderNotFoundError`, `ItemUnavailableError`).
Services call into Repositories for database access.

---

# 8. Repository Rules

Repositories handle all database access.

Every domain app must have a Repository class:

- `OrderRepository`
- `PaymentRepository`
- `ReservationRepository`
- `MenuRepository`
- `CartRepository`
- `AddressRepository`

Repositories should:
- Contain only queries and persistence commands
- Use Django ORM internally (querysets, filter, create, update, delete)
- Return model instances or lists

Repositories should NOT:
- Contain business rules, validation, or workflow logic
- Call external services or APIs
- Raise HTTP-specific errors

Repository methods are split into two categories:
- **Queries**: methods named `get_*`, `list_*`, `count_*`, `find_*`
- **Commands**: methods named `create_*`, `update_*`, `delete_*`, `mark_*`

---

# 8a. API View Permission Rules

API views must have explicit permission classes. NEVER use `permissions.AllowAny` on data endpoints.

Correct permissions by endpoint type:

| Endpoint | Permission | Reason |
|---|---|---|
| Menu (read-only) | `AllowAny` | Public restaurant information |
| Orders | `IsAuthenticated` + owner filter | Customer's private data |
| Payments | `IsAuthenticated` + owner filter | Financial data |
| Reservations | `IsAuthenticated` + owner filter | Customer's private data |
| Agent Chat | `IsAuthenticated` | Conversation requires auth |
| Users | `AllowAny` for register/login, `IsAuthenticated` for profile | Auth flow |
| Webhooks | `AllowAny` (HMAC-signed) | External payment callbacks |

Owner-scoped filtering must be applied in `get_queryset()`:
```python
def get_queryset(self):
    user = self.request.user
    if user.role in ("staff", "admin"):
        return super().get_queryset()  # Staff see all
    return super().get_queryset().filter(customer_id=str(user.id))
```

---

# 9. API View Rules


Views should be thin.


Allowed:


```
Receive request

Validate serializer

Call service

Return response

```


Not allowed:


```
Complex calculations

Database workflows

AI decisions

```


---

# 10. AI Agent Coding Rules


The AI subsystem follows:


```
Agent

↓

Planner

↓

Tools

↓

Services

```


---

# 11. LLM Rules


The LLM must never:


- Directly access database
- Modify records
- Execute SQL
- Bypass permissions


---

# 12. Tool Development Rules


Every tool must:


Have:

```
name

description

input schema

output schema

validation

error handling

```


Example:


```python
class SearchMenuTool:

    name = "search_menu"

    description = "Search available menu items"

```

---

# 13. Prompt Engineering Rules


Prompts must be:


- Version controlled
- Documented
- Tested


Never put:


- Business rules
- Security rules
- Database logic


inside prompts.

---

# 14. RAG Coding Rules


Knowledge retrieval must:


- Filter tenant
- Validate sources
- Return metadata
- Handle missing results


Never:

```
Answer from memory when knowledge exists.

```

---

# 15. Memory Rules


Memory must:


Store:

```
Preferences

Favorites

Useful habits

```


Never store:

```
Passwords

Secrets

Payment information

```

---

# 16. Frontend Standards


Technology:


```
React

TypeScript

Tailwind CSS

RTK Query

```


---

# 17. React Structure


Recommended:


```
src/


components/

features/

hooks/

services/

pages/

types/

utils/

```

---

# 18. Frontend Rules


Components should:

- Be reusable
- Have clear responsibility
- Avoid duplicated logic


---

# 19. TypeScript Rules


Avoid:


```typescript
any
```


Prefer:


```typescript
interface

type

generics

```

---

# 20. Error Handling


Every system failure must be handled.


Backend:


```
Exception

↓

Logger

↓

User-friendly response

```


Frontend:


```
API Error

↓

State Update

↓

User Message

```

---

# 21. Testing Requirements


Every feature requires:


Unit tests:

```
Services

Utilities

Agent logic

```


Integration tests:

```
API

Database

Tools

```


---

# 22. AI Agent Testing


Test:


```
Intent accuracy

Tool selection

Planning

Memory extraction

RAG retrieval

Failure recovery

```


---

# 23. Git Standards


Branch naming:


```
feature/

bugfix/

hotfix/

```


Examples:


```
feature/order-agent

feature/payment-system

bugfix/payment-timeout

```


---

# 24. Commit Messages


Use:


```
type: description

```


Examples:


```
feat: add reservation tool

fix: resolve payment validation

docs: update agent architecture

```


---

# 25. Code Review Checklist


Before merging:


Architecture:

✓ Correct layer?


Security:

✓ Permissions checked?


Testing:

✓ Tests included?


AI:

✓ Tool validated?


Database:

✓ Migration included?


---

# 26. AI Coding Agent Workflow


Before writing code:


1.

Read relevant documentation.


2.

Understand existing code.


3.

Identify correct layer.


4.

Implement minimal change.


5.

Write tests.


6.

Review against architecture.


---

# 27. Forbidden Practices


Never:


- Duplicate business logic
- Modify database directly from AI tools
- Skip tests
- Ignore permissions
- Hard-code secrets
- Create unnecessary abstractions
- Mix frontend and backend responsibility


---

# 28. Code Quality Goals


The codebase should optimize for:


```
Readability

Maintainability

Testability

Security

Scalability

```


---

# 29. Conclusion


This document defines how humans and AI coding agents should contribute to the Restaurant Intelligence Platform.

The goal is not only to create working software.

The goal is to create production-quality software that can evolve for many years.