# RAG Knowledge System

**Project:** Restaurant Intelligence Platform

**Document:** Retrieval-Augmented Generation Architecture

**Version:** 1.0

**Status:** Draft

---

# 1. Purpose

This document defines the Retrieval-Augmented Generation (RAG) architecture used by the Restaurant Intelligence Platform.

The RAG system provides the AI Agent with accurate restaurant-specific knowledge by retrieving relevant information from a controlled knowledge base.

The system allows the AI Agent to answer questions using verified information instead of relying only on the language model's general knowledge.

---

# 2. RAG Philosophy

The LLM is intelligent but does not know restaurant-specific information.

Examples:

The LLM does not automatically know:

- Current menu items
- Restaurant prices
- Available meals
- Ingredients
- Restaurant policies
- Promotions
- Opening hours
- Delivery rules

The knowledge system provides this information dynamically.

---

# 3. RAG Architecture Overview

```
                    Restaurant Data

                           │

                           ▼

                 Knowledge Ingestion

                           │

                           ▼

                    Document Processing

                           │

                           ▼

                      Chunking

                           │

                           ▼

                    Embedding Generation

                           │

                           ▼

                    Vector Database

                           │

                           ▼

                    Semantic Retrieval

                           │

                           ▼

                    Context Injection

                           │

                           ▼

                         LLM

                           │

                           ▼

                    AI Response

```

---

# 4. Knowledge Sources

The knowledge system receives information from multiple sources.

---

## Menu Knowledge

Examples:

```
Menu items

Categories

Prices

Ingredients

Availability

Nutrition information
```

---

## Restaurant Information

Examples:

```
Restaurant name

Location

Opening hours

Contact information

Services
```

---

## Policy Knowledge

Examples:

```
Refund policy

Cancellation policy

Delivery rules

Payment rules
```

---

## FAQ Knowledge

Examples:

```
Do you deliver?

What payment methods exist?

Do you support reservations?
```

---

## Promotion Knowledge

Examples:

```
Discounts

Seasonal offers

Special meals
```

---

# 5. Knowledge Pipeline

The ingestion process:

```
Raw Information

↓

Cleaning

↓

Document Creation

↓

Chunking

↓

Embedding

↓

Metadata Generation

↓

Vector Storage

```

---

# 6. Document Processing

Before storing knowledge:

The system cleans and structures information.

Example:

Raw:

```
Burger available today.
Price 250.
Contains chicken.
```

Converted:

```
Menu Item:

Chicken Burger

Price:

250 ETB

Ingredients:

Chicken, Bread, Sauce

Availability:

Available
```

---

# 7. Chunking Strategy

Large documents must be divided into smaller pieces.

Example:

Large document:

```
Restaurant Menu
500 pages
```

becomes:

```
Chunk 1

Burger Category


Chunk 2

Pizza Category


Chunk 3

Drinks Category
```

---

# 8. Chunk Rules

Chunks should:

- Contain complete meaning
- Avoid unnecessary duplication
- Preserve important context

Each chunk should include metadata.

---

# 9. Metadata Design

Every knowledge chunk should contain:

Example:

```
{
 type:

 menu,

 category:

 food,

 language:

 en,

 source:

 admin_upload,

 created_at:

 date
}

**Future Multi-Tenant:** Will include `restaurant_id` field.

```

---

# 10. Embedding System

Embeddings convert text into numerical vectors.

Example:

Text:

```
Chicken Burger
```

becomes:

```
[0.231, 0.532, ...]
```

Similar meanings produce similar vectors.

---

# 11. Vector Database

The platform uses vector search.

Current option:

```
PostgreSQL

+

pgvector extension
```

Benefits:

- Existing database infrastructure
- Transaction consistency
- Simple deployment

**Future Multi-Tenant:** Will support tenant isolation.

---

# 12. Retrieval Flow

Example:

Customer:

```
What spicy meals do you have?
```

Flow:

```
Question

↓

Create Query Embedding

↓

Search Vector Database

↓

Retrieve Relevant Documents

↓

Filter Results

↓

Rank Results

↓

Send Context To LLM

```

---

# 13. Restaurant Security

**Future Multi-Tenant:** Critical rule.

A restaurant must never access another restaurant's knowledge.

Every vector query must include:

```
restaurant_id
```

**Future Multi-Tenant Example:**

Wrong:

```
Search:

"burger"
```

Correct:

```
Search:

"burger"

WHERE

restaurant_id = current_restaurant
```

---

# 14. Retrieval Strategy

The system uses:

## Semantic Search

Finds similar meaning.

Example:

Question:

```
healthy food
```

Can find:

```
salad

vegetable meals

low calorie dishes
```

---

## Metadata Filtering

Filters:

```
restaurant

category

availability

language
```

---

## Ranking

Retrieved results are ranked by:

```
Similarity score

+

Business relevance

+

Availability

```

---

# 15. Context Injection

Retrieved knowledge is added to the LLM context.

Example:

```
SYSTEM:

You are a restaurant assistant.


Knowledge:

Chicken Burger:

250 ETB

Available:

Yes


User:

I want chicken burger.
```

---

# 16. Hallucination Prevention

Rules:

The AI must:

- Use retrieved information.
- Say when information is unavailable.
- Never invent menu items.
- Never invent prices.
- Never invent policies.

Example:

Bad:

```
Yes, we have sushi.
```

when no sushi exists.

Good:

```
I could not find sushi on our current menu.
```

---

# 17. RAG and Agent Interaction

The agent decides when to use RAG.

Examples:

Question:

```
What is my order status?
```

Needs:

Order Service

---

Question:

```
Does this meal contain nuts?
```

Needs:

RAG Knowledge

---

Question:

```
Recommend something.
```

Needs:

Memory + RAG + Recommendation Engine

---

# 18. Knowledge Updating

When restaurant data changes:

Example:

New menu item.

Flow:

```
Admin Update

↓

Knowledge Update Event

↓

Regenerate Embedding

↓

Update Vector Database

↓

Agent Uses New Knowledge

```

---

# 19. RAG Monitoring

Track:

- Retrieval accuracy
- Missing information
- Wrong answers
- Search latency
- Failed queries

---

# 20. Future Improvements

Future versions:

- Hybrid search
- Keyword + semantic search
- Re-ranking models
- Multi-language embeddings
- Image knowledge
- Voice knowledge
- Automatic knowledge extraction

---

# 21. Conclusion

The RAG Knowledge System provides the AI Agent with accurate restaurant knowledge.

By separating customer memory from restaurant knowledge, the platform achieves:

- Better accuracy
- Lower hallucination
- Easier updates
- Scalable knowledge management

**Future Multi-Tenant:** Will support tenant isolation.

The AI Agent becomes intelligent because it can combine:

Customer Memory

+

Restaurant Knowledge

+

Business Tools

+

LLM Reasoning

into a complete experience.
