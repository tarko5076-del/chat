# Data Flow Architecture

**Project:** Restaurant Intelligence Platform

**Document:** Data Flow Specification

**Version:** 1.0

**Status:** Draft

---

# 1. Purpose

This document defines the movement of data through the Restaurant Intelligence Platform.

It describes:

- User request lifecycle
- AI Agent execution flow
- Memory flow
- RAG retrieval flow
- Tool execution flow
- Order processing flow
- Reservation flow
- Payment flow
- Failure handling

The goal is to make every system interaction predictable and observable.

---

# 2. Core Data Flow Principle

The system follows this pattern:

```
Input

↓

Understand

↓

Collect Context

↓

Reason

↓

Plan

↓

Execute

↓

Validate

↓

Persist

↓

Respond
```

The AI Agent does not directly modify application data.

All changes happen through controlled services.

---

# 3. Complete System Data Flow

```
Customer

↓

Frontend Application

↓

API Gateway

↓

Conversation Manager

↓

Context Builder

↓

AI Orchestrator

↓

Planner

↓

Memory Retrieval

↓

Knowledge Retrieval

↓

Decision Engine

↓

Policy Validation

↓

Tool Execution

↓

Business Services

↓

Database

↓

Response Generator

↓

Customer
```

---

# 4. User Message Lifecycle

Example:

Customer:

> "I want two chicken burgers delivered."

---

## Step 1: Message Reception

Frontend sends:

```json
{
  "message": "I want two chicken burgers delivered",
  "conversation_id": "123"
}
```

API receives the request.

Responsibilities:

- Authentication
- Tenant identification
- Rate limiting
- Request validation

---

# Step 2: Conversation Context Loading

Conversation Manager loads:

```
Current conversation

+

Customer profile

+

Previous messages

+

Active cart

+

Restaurant information
```

Example:

```
Customer:

John

Previous favorite:

Chicken Burger

Preferred payment:

Telebirr

Default address:

Bole
```

---

# Step 3: Intent Detection

Intent Engine analyzes:

Input:

```
"I want two chicken burgers delivered"
```

Output:

```json
{
 "intent": "create_order",
 "entities": {
   "item": "chicken burger",
   "quantity": 2,
   "delivery": true
 }
}
```

---

# Step 4: Context Enrichment

The system collects missing information.

Checks:

```
Do we know customer?

Yes

Do we know restaurant?

Yes

Do we know menu item?

Need search
```

---

# Step 5: Knowledge Retrieval (RAG)

The Knowledge Engine searches:

```
Vector Database

↓

Menu Documents

↓

Relevant Results
```

Example:

Retrieved:

```
Chicken Burger

Price: 250 ETB

Available: Yes

Ingredients:

Chicken
Bread
Sauce
```

---

# Step 6: Planning

Planner creates:

```
Goal:

Create customer order


Tasks:

1.
Find menu item


2.
Add item to cart


3.
Calculate total


4.
Ask delivery details


5.
Ask payment method


6.
Confirm order

```

---

# Step 7: Policy Validation

Before executing:

Checks:

```
Is user authenticated?

Yes


Does item exist?

Yes


Is item available?

Yes


Can user create order?

Yes
```

---

# Step 8: Tool Execution

Agent calls:

```
CreateCartItemTool
```

Tool sends request:

```
Order Service
```

Service executes:

```
Validate Item

↓

Calculate Price

↓

Save Cart Item
```

---

# Step 9: Database Persistence

Database updates:

```
Cart

+

Cart Item

+

Conversation State
```

---

# Step 10: Response Generation

AI receives:

```
Tool Result:

Added 2 Chicken Burgers

Total:

500 ETB
```

Generates:

```
"I added two chicken burgers.
Your total is 500 ETB.
Would you like delivery or pickup?"
```

---

# 5. Complete Order Flow

```
Customer

↓

Select Food

↓

Create Cart

↓

Add Items

↓

Review Cart

↓

Choose Delivery/Pickup

↓

Choose Payment

↓

Payment Processing

↓

Payment Confirmation

↓

Create Order

↓

Notify Kitchen

↓

Update Customer

```

---

# 6. Payment Data Flow

```
Customer

↓

Choose Payment Method

↓

Payment Service

↓

External Gateway

↓

Payment Confirmation

↓

Payment Record Updated

↓

Order Confirmed
```

---

## Important Rule

The AI never says:

"Your payment succeeded"

until Payment Service confirms it.

---

# 7. Reservation Flow

```
Customer Request

↓

Reservation Intent

↓

Check Availability

↓

Generate Options

↓

Customer Confirmation

↓

Create Reservation

↓

Send Reminder
```

---

# 8. Memory Data Flow

Memory has two stages.

---

## Reading Memory

Before response:

```
Customer

↓

Memory Service

↓

Retrieve Relevant Memories

↓

Context

↓

LLM
```

Example:

```
Customer likes spicy food.

Customer prefers delivery.
```

---

## Writing Memory

After conversation:

```
Conversation

↓

Memory Extraction

↓

Validation

↓

Memory Storage
```

Example:

User:

"I always order Ethiopian coffee."

Memory:

```
Favorite:

Ethiopian Coffee
```

---

# 9. RAG Data Flow

Knowledge ingestion:

```
Document

↓

Cleaning

↓

Chunking

↓

Embedding

↓

Vector Storage
```

Runtime:

```
User Question

↓

Embedding

↓

Similarity Search

↓

Relevant Context

↓

LLM
```

---

# 10. Error Flow

Errors must never disappear.

Example:

Payment failure.

```
Tool

↓

Service Error

↓

Agent Receives Error

↓

Reflection Engine

↓

Retry or Explain

↓

Customer Response
```

---

# 11. Observability Flow

Every important action creates logs.

Example:

```
User Message

↓

Intent

↓

Plan

↓

Tool Calls

↓

Execution Time

↓

Errors

↓

Final Response
```

Used for:

- Debugging
- Analytics
- Improvement
- Monitoring

---

# 12. Data Ownership Rules

Each layer owns specific data.

```
AI Layer

Conversation Context


Memory Layer

Customer Preferences


Service Layer

Business Data


Database Layer

Persistent Storage
```

---

# 13. Important Architecture Rules

## Rule 1

AI does not directly access database.

---

## Rule 2

Services are the source of truth.

---

## Rule 3

Every external action requires validation.

---

## Rule 4

Every tool execution must be observable.

---

## Rule 5

Every important customer preference should become memory.

---

# 14. Future Data Flows

Future agents will follow the same pattern:

```
Kitchen Agent

↓

Kitchen Service


Inventory Agent

↓

Inventory Service


Marketing Agent

↓

Campaign Service
```

---

# 15. Conclusion

The Restaurant Intelligence Platform follows a controlled data flow where the AI Agent provides intelligence and orchestration while backend services provide reliability and business execution.

This architecture allows the platform to grow from a simple ordering assistant into a complete restaurant intelligence ecosystem.