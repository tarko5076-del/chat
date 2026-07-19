# Database Architecture

**Project:** Restaurant Intelligence Platform

**Document:** Database Design Specification

**Version:** 1.0

**Status:** Draft


---

# 1. Purpose

This document defines the database architecture for the Restaurant Intelligence Platform.

It describes:

- Database technology
- Data organization
- Core tables
- Relationships
- AI-related storage
- Vector database design
- Restaurant data strategy
- **Future:** Multi-tenant strategy
- Indexing strategy
- Data lifecycle


---

# 2. Database Philosophy

The database follows these principles:

## Source of Truth

The database contains the official state of the system.

Examples:

- Order status
- Payment status
- Reservation status
- Menu availability


The AI cannot override database state.


---

## Separation of Data Types

The system separates:


Business Data

```
Customers

Orders

Payments

Reservations

Menu

```

AI Data

```
Conversations

Memories

Embeddings

Agent Logs

```


---

# 3. Database Technology


Primary Database:

```
PostgreSQL
```


Extensions:


```
pgvector

UUID

Full Text Search

JSONB

```

---

Purpose:


PostgreSQL stores:

- Transactional data
- Customer data
- Restaurant data
- AI data


pgvector stores:

- Knowledge embeddings
- Semantic search vectors


---

# 4. Database Architecture


The platform is designed for a single restaurant.

**Future Enhancement:** Multi-tenant architecture will support multiple restaurants.


Architecture (Future Multi-Tenant):


```
                 Platform

                    |

        ┌───────────┼───────────┐

        ▼           ▼           ▼

   Restaurant A Restaurant B Restaurant C

        |

        ▼

    Restaurant Data

```


---

**Future Multi-Tenant:** Every tenant-owned table will contain:


```
restaurant_id
```


Example:


**Future Multi-Tenant Example:**

Orders:

```
id

restaurant_id

customer_id

status

total

```


---

# 5. Core Entity Groups


Database is divided into:


```
Restaurant Domain

├── Restaurant

├── Customer

├── Menu

├── Cart

├── Order

├── Payment

├── Reservation


AI Domain

├── Conversation

├── Message

├── Memory

├── Knowledge

├── Embedding


System Domain

├── User

├── Role

├── Permission

├── Audit Log

```

---

# 6. Restaurant Tables


## Restaurant


Purpose:

Stores restaurant tenants.


Fields:


```
id

name

description

address

phone

email

status

created_at

updated_at

```


---

# 7. Customer Tables


## Customer


```
id

name

phone

email

status

created_at

updated_at

```

**Future Multi-Tenant:** Will include `restaurant_id` field.


Relationships:


```
Customer

 |

 ├── Orders

 ├── Reservations

 ├── Conversations

 ├── Memories

 └── Favorites

```


---

# 8. Menu Tables


## MenuCategory


```
id

name

description

```

**Future Multi-Tenant:** Will include `restaurant_id` field.



## MenuItem


```
id

category_id

name

description

price

availability

ingredients

image

created_at

```

**Future Multi-Tenant:** Will include `restaurant_id` field.


Rules:


- Menu belongs to restaurant.
- Price controlled by backend.
- Availability is authoritative.


---

# 9. Cart Tables


## Cart


```
id

customer_id

status

created_at

updated_at

```

**Future Multi-Tenant:** Will include `restaurant_id` field.


## CartItem


```
id

cart_id

menu_item_id

quantity

notes

```


---

# 10. Order Tables


## Order


```
id

customer_id

status

order_type

total_amount

created_at

updated_at

```

**Future Multi-Tenant:** Will include `restaurant_id` field.


Status:


```
Created

Pending Payment

Paid

Preparing

Ready

Completed

Cancelled

```


---

## OrderItem


```
id

order_id

menu_item_id

quantity

price_at_purchase

notes

```


Important:


Store price at purchase time.


Reason:


Menu prices change.


---

# 11. Payment Tables


## Payment


```
id

order_id

method

amount

status

transaction_id

created_at

```


Payment status:


```
Pending

Processing

Completed

Failed

Refunded

```


---

# 12. Reservation Tables


## Reservation


```
id

customer_id

date

time

guest_count

status

created_at

```


---

# 13. Customer Memory Tables


Memory is separate from business data.


## Memory


```
id

customer_id

type

content

confidence

source

created_at

updated_at

```

**Future Multi-Tenant:** Will include `restaurant_id` field.


Example:


```
type:

favorite_food


content:

Chicken Burger


confidence:

0.95

```


---

# 14. Conversation Tables


## Conversation


```
id

customer_id

status

summary

created_at

updated_at

```

**Future Multi-Tenant:** Will include `restaurant_id` field.



## Message


```
id

conversation_id

role

content

metadata

created_at

```


Roles:


```
user

assistant

tool

system

```


---

# 15. Knowledge Base Tables


Used for RAG.


## KnowledgeDocument


```
id

title

content

source

created_at

```

**Future Multi-Tenant:** Will include `restaurant_id` field.


---

## KnowledgeChunk


```
id

document_id

content

embedding

metadata

created_at

```

**Future Multi-Tenant:** Will include `restaurant_id` field.


Embedding:


```
vector(1536)

```


---

# 16. Vector Search Design


Example query:


Customer:


```
Do you have spicy food?
```


Flow:


```
Question

↓

Embedding

↓

pgvector similarity search

↓

Relevant chunks

↓

LLM context

```


---

# 17. Agent Execution Tables


For debugging.


## AgentExecution


```
id

conversation_id

task

status

created_at

```


---

## ToolExecution


```
id

agent_execution_id

tool_name

input

output

success

execution_time

created_at

```


---

# 18. Indexing Strategy


Important indexes:


Customer:

```
restaurant_id

phone

```


Orders:


```
restaurant_id

customer_id

status

created_at

```


Menu:


```
restaurant_id

category_id

availability

```


Knowledge:


```
restaurant_id

embedding vector index

```


---

# 19. Database Constraints


Important rules:


## Orders


Must have:

```
customer

restaurant

items

```


---

## Payments


Must belong to:

```
existing order

```


---

## Reservations


Cannot:

```
overlap same table/time

```


---

## Restaurant Data

**Future Multi-Tenant:** Must always include:


```
restaurant_id

```


---

# 20. Transaction Rules


Critical operations use database transactions.


Example:


Order creation:


```
Create Order

+

Create Order Items

+

Update Cart

+

Create Payment Request


```

All succeed together.


---

# 21. Data Retention


Conversation:


Short-term:

Active sessions


Long-term:

Summaries


Memory:


Long-term until:

- User deletes
- Expired
- Invalid


Logs:


Based on retention policy.


---

# 22. Future Database Extensions


Future tables:


```
Inventory

KitchenOrder

DeliveryTracking

Reviews

Loyalty

RecommendationHistory

AgentFeedback

```


---

# 23. Conclusion


The database architecture provides a reliable foundation for the Restaurant Intelligence Platform.

It separates:

Business Truth

from

AI Intelligence


PostgreSQL manages the operational state.

AI systems use memory, knowledge, and execution logs to provide intelligence.

This separation allows the platform to scale safely as more restaurants, customers, and AI capabilities are added.