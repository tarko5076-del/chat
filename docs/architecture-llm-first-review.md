# Architecture Review: LLM-First Migration

**Project:** Restaurant Intelligence Platform

**Document:** Comprehensive Architecture Review & Migration Plan

**Version:** 1.0 — July 2026

---

## 1. Architecture Changes Summary

The Restaurant Intelligence Platform has been documented as transitioning from a **Tool-Centric Architecture** to an **LLM-First Architecture**.

### What Changed

| Before (Tool-Centric) | After (LLM-First) |
|----------------------|-------------------|
| AI Reasoning Engine + Planner + Tools | LLM as the primary reasoning, conversation, and planning layer |
| FAQTool handled greetings, thanks, and knowledge | LLM handles conversation directly; RAG handles knowledge |
| Planner routed FAQ queries to answer_faq tool | LLM decides when to use tools, RAG, or direct response |
| Tools could return static conversational text | Tools return only structured data; LLM formats responses |
| Architecture diagram showed Planner → Memory → Knowledge → Tools | Architecture shows LLM → Tools | RAG | Memory (three parallel capabilities) |

### Documents Updated

| Document | Version | Key Changes |
|----------|---------|-------------|
| `docs/system-arichetecture.md` | 2.0 | New LLM-First diagram, component responsibilities, AI agent development principle |
| `docs/tool-system.md` | 2.0 | Deprecated FAQTool, added tool audit checklist, clarified tool vs conversation rules |
| `docs/agent-prompt-engineering.md` | 2.0 | Strong system prompt design, decision tree for tool/RAG/direct, when-NOT-to-use-tools |
| `docs/rag-knowledge-system.md` | 2.0 | RAG vs Tools decision matrix, FAQTool migration guide, clear separation of concerns |
| `docs/agent-memory-system.md` | 2.0 | Three memory types (short-term, long-term, semantic) with storage/details |
| `docs/planner-and-agent-workflow.md` | 2.0 | LLM-first execution loop with decision tree, LocalPlanner as fallback only |
| `docs/ai-agent-development-roadmap.md` | 2.0 | New Milestone: LLM-First Architecture Refactoring |

---

## 2. LLM-First Architecture Diagram

```
                        Customer
                            │
                            ▼
                 Web / Mobile Application
                            │
                            ▼
                    REST / WebSocket API
                            │
                            ▼
                 AI Agent Orchestrator
                 (Controller + Context Assembly)
                            │
                            ▼
                    ┌───────────────┐
                    │     LLM       │
                    │  (Reasoning,  │
                    │  Conversation,│
                    │  Planning,    │
                    │  Decision)    │
                    └───────┬───────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
        ┌────────┐    ┌──────────┐    ┌──────────┐
        │ Tools  │    │   RAG    │    │  Memory  │
        │(Actions│    │(Restaurant│   │ (Customer│
        │ & Data)│    │Knowledge)│    │Profile)  │
        └───┬────┘    └──────────┘    └──────────┘
            │
    ┌───────┼───────┐
    ▼       ▼       ▼
 Menu   Order   Payment  Reservation  Cart  Billing
Service Service  Service   Service   Service Service
    │       │       │          │        │       │
    └───────┼───────┼──────────┼────────┼───────┘
            ▼
      Repository Layer
            │
            ▼
        PostgreSQL + pgvector
```

---

## 3. Component Responsibility Matrix

| Component | Responsibilities | Does NOT Do |
|-----------|-----------------|-------------|
| **LLM** | Reasoning, conversation, planning, decision making, response generation, greetings, small talk, identity questions, explanations | Modify database directly, call unnecessary tools, invent data not in context |
| **AI Agent Orchestrator** | Context assembly, message routing, streaming, tool execution orchestration, error handling | Business logic, database access, response generation |
| **Tools** | Database CRUD, external system integration, business actions, real-time data retrieval, state changes | Static text generation, conversational responses, knowledge retrieval (that's RAG's job) |
| **RAG** | Retrieve restaurant-specific knowledge (hours, address, policies, ingredients, allergens, promotions) | State changes, business actions, conversational responses |
| **Memory (Short-Term)** | Current conversation context, intent tracking, workflow state | Long-term storage, restaurant knowledge |
| **Memory (Long-Term)** | Customer preferences, order history, favorite items, profile data | Restaurant knowledge, conversation state |
| **Backend Services** | Business rules, validation, transactions, email notifications | AI reasoning, response generation |

---

## 4. Deprecated Components

### 4.1 FAQTool (answer_faq) — TO BE REMOVED

**File:** `backend/agent/tools/faq.py`

**Current Behavior:**
- Detects greetings ("hi", "hello", "hey") → returns static welcome message
- Detects thanks/bye → returns "You're welcome!" response
- Matches keywords for hours, address, parking, delivery, Wi-Fi, payment → returns hardcoded answers
- Fallback returns a formatted menu of capabilities

**Why Deprecated:**
1. **Greetings/thanks**: LLM handles these naturally without any tool call — adding a tool creates unnecessary latency
2. **FAQ answers**: Should be stored in RAG KnowledgeBase, not hardcoded in Python — allows restaurant staff to update without code
3. **Static capability menu**: Hardcoded emoji menu is rigid — LLM can explain capabilities dynamically
4. **Violates LLM-First principle**: Every conversational turn should NOT require a tool call

**Migration Strategy:**
1. Create KnowledgeBase entries for each FAQ topic (hours, address, parking, delivery, Wi-Fi, payment)
2. Update system prompt to instruct LLM to handle greetings, identity questions, and thanks directly
3. Remove FAQTool from `tools/__init__.py` and `controller.py`
4. Remove `answer_faq` routing from `planner.py`

### 4.2 LocalPlanner FAQ Routing — TO BE REMOVED

**File:** `backend/agent/planner.py`

**Current Behavior:**
- `_is_faq()` method matches keywords to route to `answer_faq` tool
- Fallback route returns `answer_faq` for any unmatched query

**Why Deprecated:**
- Routes conversational messages through a tool unnecessarily
- Should let the LLM decide when to use RAG vs tools vs direct response
- Creates false dichotomy (everything is either FAQ or action)

**Migration Strategy:**
- Remove `answer_faq` from planner routing
- Keep planner only as a fallback for LLM-unavailable scenarios
- In fallback mode, route knowledge queries directly to `search_knowledge`

### 4.3 Static Conversational Patterns in Tools — REFACTOR

**Affected:** Any tool returning hardcoded conversational text

**Examples found in codebase:**
- FAQTool: `"You're welcome!"`, `"Hi there! Welcome to Resto AI..."`, emoji menu
- (Potential others: check BillingTool for static format strings)

**Why Deprecated:**
- Tools should return structured data, not formatted text
- LLM should format the final response naturally
- Static responses don't adapt to conversation context

---

## 5. Tools That Should Be KEPT (Validated)

| Tool | Purpose | Justification |
|------|---------|---------------|
| **MenuTool** (list_menu_items) | Database query for menu | ✅ Database access, real-time data |
| **GetMenuItemDetailsTool** (get_menu_item_details) | Database query for item details | ✅ Database access |
| **ManageCartTool** (manage_cart) | Cart CRUD operations | ✅ State changes, database access |
| **CheckoutCartTool** (checkout_cart) | Convert cart to order | ✅ Business action, state change |
| **OrderTool** (manage_order) | Order CRUD + history | ✅ Database access, state changes |
| **BillingTool** (calculate_bill) | Price calculation | ✅ Business logic calculation |
| **PaymentTool** (process_payment) | Payment initiation via Chapa | ✅ External system integration |
| **VerifyPaymentTool** (verify_payment) | Payment status verification | ✅ External system integration |
| **RecommendMenuTool** (recommend_menu_items) | ML-based recommendations | ✅ Data retrieval + scoring algorithm |
| **ManagePreferencesTool** (manage_preferences) | Customer preference CRUD | ✅ Database access, state changes |
| **EscalationTool** (request_human_staff) | Staff notification | ✅ State change, business action |
| **SearchKnowledgeTool** (search_knowledge) | RAG retrieval | ✅ Knowledge retrieval |
| **ReservationTool** (manage_reservation) | Reservation CRUD | ✅ Database access, state changes |

All **14 remaining tools** serve legitimate business operations. None should be removed.

---

## 6. Code Components Requiring Migration

### 6.1 `backend/agent/controller.py`
- **Remove:** FAQTool import and registration in `_build_tools()`
- **Update:** System prompt injection to include RAG context for knowledge
- **Verify:** Workflow routing still works without FAQTool

### 6.2 `backend/agent/tools/__init__.py`
- **Remove:** FAQTool import from `__all__`

### 6.3 `backend/agent/planner.py`
- **Remove:** `_is_faq()` method and `answer_faq` routing
- **Replace:** Fallback routing with `search_knowledge` for restaurant queries
- **Simplify:** Focus only on business action routing (menu, order, reservation, payment)

### 6.4 `backend/agent/tools/faq.py`
- **Delete entire file** after migration is complete

### 6.5 KnowledgeBase seeding
- **Add:** Seed data for all FAQ topics currently in FAQTool.answers
- **Use:** `management/commands/seed_knowledge.py`

---

## 7. System Prompt Updates Required

The current system prompt (`backend/agent/prompts.py`) needs these additions:

### Add: Direct Response Rules
```
## When to respond WITHOUT tools

You should respond directly (NO tool call) for:

- **Greetings:** "Hi", "Hello", "Good morning", "Hey"
- **Farewells:** "Bye", "Goodbye", "See you"
- **Thanks:** "Thank you", "Thanks!", "Appreciate it"
- **Identity questions:** "Who are you?", "What can you do?"
- **Small talk:** "How are you?", "Nice weather"
- **Simple explanations:** Explaining something already in context

When you receive these, just respond naturally. Do NOT call a tool.
```

### Add: RAG vs Tool Decision Rules
```
## Using restaurant knowledge

Restaurant information (hours, address, parking, policies, ingredients) is provided
through <retrieved_knowledge> tags. Use this information to answer questions naturally.

You do NOT need a tool to answer questions about information already in your context.
Only use tools for actions (orders, reservations, payments) or dynamic data (menu search).
```

---

## 8. Recommended Implementation Steps

### Step 1: Seed KnowledgeBase with FAQ Data
- Create KnowledgeBase records for all topics: hours, address, parking, delivery, Wi-Fi, payment methods
- Verify RAG retrieval works for these queries
- **File:** `backend/agent/management/commands/seed_knowledge.py`

### Step 2: Update System Prompt
- Add direct response rules (greetings, thanks, identity → no tool)
- Add RAG vs Tool decision rules
- **File:** `backend/agent/prompts.py`

### Step 3: Remove FAQTool from Registry
- Remove import from `tools/__init__.py`
- Remove registration from `controller.py`
- **Files:** `backend/agent/tools/__init__.py`, `backend/agent/controller.py`

### Step 4: Remove answer_faq from Planner
- Remove `_is_faq()` method
- Remove fallback to `answer_faq`
- Add `search_knowledge` routing for fallback mode
- **File:** `backend/agent/planner.py`

### Step 5: Delete FAQTool File
- Delete `backend/agent/tools/faq.py`

### Step 6: Update Tests
- Remove FAQTool tests
- Add tests verifying LLM handles conversation without tools
- Add tests verifying RAG provides restaurant knowledge

### Step 7: Verify All Business Flows
- Manual testing: greetings, orders, reservations, payments, knowledge queries
- Automated test pass

### Step 8: Monitoring
- Track zero-tool-call ratio (should increase after migration)
- Verify no regression in business workflows

---

## 9. Expected Benefits

| Metric | Before | After (Expected) |
|--------|--------|------------------|
| Avg tools per conversation | High (FAQ + every turn) | Low (only business actions) |
| Latency for simple turns | High (tool call overhead) | Low (LLM responds directly) |
| FAQ update difficulty | Code change required | Database entry via API |
| Natural conversation quality | Tool responses feel robotic | LLM adapts naturally |
| Code maintainability | Static strings in tool code | RAG knowledge base is editable |

---

## 10. Risk Assessment

| Risk | Mitigation |
|------|------------|
| LLM may hallucinate FAQs without tool | RAG context is injected into every message — LLM has the facts |
| LLM may call tools unnecessarily | Strong system prompt instructions + monitoring |
| LocalPlanner fallback breaks without FAQTool | Route to search_knowledge instead |
| RAG retrieval may fail | Graceful fallback: LLM says "I don't have that information" |
| Greeting responses may be inconsistent | System prompt defines greeting style expectations |

---

*Document generated as part of LLM-First Architecture Review — July 2026*
