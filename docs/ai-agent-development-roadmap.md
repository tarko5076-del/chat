# AI Agent Development Roadmap

**Project:** Restaurant Intelligence Platform

**Document:** Implementation Milestones and Development Plan

**Version:** 1.1

**Status:** Active

**Last Updated:** July 2026

**Completed Milestones:**
- ✅ Milestone 1: AI Agent Foundation (Complete)
- ✅ Milestone 2: Agent Tool Foundation (Complete)
- ✅ Milestone 3: Menu Intelligence Agent (Complete)
- ✅ Milestone 4: Ordering Agent (Complete)
- ✅ Milestone 6: Reservation Agent (Complete)
- ✅ Milestone 7: Customer Memory (Complete)


---

# 1. Purpose

This document defines the development roadmap for building the Restaurant Intelligence Platform AI Agent.

The roadmap transforms the architecture into practical implementation phases.

The development strategy follows:

```
Simple

↓

Reliable

↓

Intelligent

↓

Autonomous

↓

Scalable
```

---

# 2. Development Philosophy


The system should first solve real restaurant problems.

Priority order:


1. Business correctness

2. Reliable workflows

3. AI intelligence

4. Automation

5. Advanced capabilities


---

# 3. Complete Roadmap Overview


```
✅ Milestone 1 — Foundation (Complete)

↓

✅ Milestone 2 — Agent Tool Foundation (Complete)

↓

✅ Milestone 3 — Menu Intelligence (Complete)

↓

✅ Milestone 4 — Ordering Agent

↓

⏳ Milestone 5 — Payment & Delivery

↓

✅ Milestone 6 — Reservation Agent

↓

⏳ Milestone 7 — Memory System

↓

⏳ Milestone 8 — Advanced RAG

↓

⏳ Milestone 9 — Multi-Agent Architecture

↓

⏳ Milestone 10 — Production Optimization

```

---

# ✅ Milestone 1: AI Agent Foundation

**Status: Complete**

## Goal

Create the basic infrastructure for the AI system.


---

## Implemented Features


### Agent Core

```
✅ Agent Controller (controller.py)
  - RestaurantAgent class with run/run_stream methods
  - Tool orchestration via ReAct loop or LocalPlanner fallback
  - Streaming response support
  - Automatic RAG context retrieval per user message

✅ Conversation Manager (memory.py, memory_manager.py)
  - ConversationMemory with message history, tool results, order state
  - MemoryManager for episodic/semantic event recording
  - Profile management with long-term fact extraction
  - State serialization/deserialization for session persistence

✅ LLM Provider (llm.py)
  - LLMClient with OpenAI-compatible API (HuggingFace, OpenRouter, etc.)
  - Tool-calling support (complete_with_tools + streaming)
  - Automatic fallback between providers
  - Configurable model, base URL, and API key

✅ Prompt System (prompts.py)
  - System prompt with waiter persona
  - Session context injection
  - Hard constraints for safety (confirmation gates, human escalation)
```

---

### Database

```
✅ Conversation model
  - ID, title, created_at, updated_at, is_active

✅ Message model
  - role (user/assistant/system), content, metadata (JSON)

✅ AgentExecution model
  - conversation, llm_model, tokens_used, duration_ms, status

✅ ToolExecution model
  - agent_execution, tool_name, tool_args, result, duration_ms, success

✅ StaffNotification model
  - customer_id, reason, priority, status
```

---

### API

```
✅ POST /api/v1/agent/chat/  — Send message, receive AI response
✅ POST /api/v1/agent/chat/stream/ — Streaming response with tool events
✅ GET /api/v1/agent/conversations/ — List conversations
```

---

### Additional Infrastructure

```
✅ ReAct Loop (react.py)
  - Multi-step reasoning with tool calls
  - Streaming tool execution events
  - Goal stack management
  - Reflection prompts between tool iterations
  - Configurable max iterations (default 10)
  - Tool timeout handling (30 second default)

✅ LocalPlanner Fallback (planner.py)
  - Rule-based planning when LLM is unavailable
  - Intent detection and tool routing

✅ RAG System (rag.py, embeddings.py)
  - Vector search with pgvector
  - Multiple embedding providers (OpenAI, HuggingFace)
  - Graceful fallback to zero vectors

✅ Order Workflow (order_workflow.py)
  - Multi-turn ordering flow
  - State management for item collection, quantity, delivery, payment
  - Slot filling and topic switching

✅ Conversation Summarization (summarizer.py)
  - Background fact extraction after each session

✅ Email Confirmation (email_service.py)
  - HTML email templates for order confirmations
```

---

## Success Criteria

The user can:

```
✅ Send message
✅ Receive AI response
✅ Store conversation
✅ Resume conversation across sessions
✅ Receive streaming responses with tool progress
```

---

# ✅ Milestone 2: Agent Tool Foundation

**Status: Complete**

## Goal

Allow AI to interact with backend capabilities through a secure tool framework.


---

## Build: Tool Framework


```
✅ BaseTool (tools/base.py)
  - Abstract base class with name, description, parameters
  - ToolResult dataclass with success, message, data, missing_fields
  - to_openai_tool() for LLM tool schema generation
  - to_llm_content() for structured tool result serialization

✅ Tool Registry (tools/__init__.py)
  - Central registry of all available tools
  - Imported and registered in controller._build_tools()
  - Tools mapped by name for dynamic lookup

✅ Tool Executor (react.py, controller.py)
  - ReAct loop executes tools asynchronously
  - Timeout handling (30s per tool)
  - Result serialization for LLM consumption
  - Tool tracing with callbacks for observability

✅ Tool Validation
  - JSON Schema parameter definitions on each tool
  - Backend-side validation in tool.execute()
  - Missing field detection with human-readable responses
  - Idempotency keys on money/inventory actions
```

---

## First Tools Implemented


```
✅ MenuTool (SearchMenuTool equivalent)
  - Name: "list_menu_items"
  - Search, filter, and browse menu items
  - Supports: category, vegetarian, vegan, spicy, max_price, search
  - Returns structured item data with prices and descriptions

✅ FAQTool (GetRestaurantInfoTool equivalent)
  - Name: "answer_faq"
  - Answers restaurant FAQ questions
  - Topics: hours, address, parking, delivery, Wi-Fi, payment
  - Greeting/thanks detection with warm responses
```

---

## Additional Tools Built

The tool framework has been extended beyond the first two tools to support complete restaurant operations:

```
✅ OrderTool (manage_order)
  - Actions: create, add, remove, show, cancel, history, last_completed
  - Confirmation gate before order submission
  - Idempotency key support
  - Auto-email confirmation on order placement
  - Menu item alternatives when item not found

✅ PaymentTool (process_payment)
  - Supports: chapa (online), telebirr, cbe_birr, cash
  - Chapa checkout URL generation
  - Confirmation gate before payment processing
  - Duplicate payment prevention via idempotency keys
  - Cash payment recording without external gateway

✅ ReservationTool (manage_reservation)
  - Actions: check, create, confirm, update, cancel, list
  - Availability checking with table capacity
  - Reservation holds with TTL (configurable minutes)
  - Expired hold detection
  - Email notification on creation/confirmation

✅ BillingTool (calculate_bill)
  - Subtotal, tax (8.25%), delivery fee calculation
  - Bill splitting support

✅ EscalationTool (request_human_staff)
  - Priority levels: low, medium, high
  - StaffNotification model with reason tracking
  - Graceful fallback if DB unavailable

✅ SearchKnowledgeTool (search_knowledge)
  - Semantic search over restaurant knowledge base
  - Content type filtering (menu_item, policy, faq, promotion)
  - Configurable top-k results
```

---

## Tool Design Features

```
✅ Confirmation gates before irreversible actions
  - Order submission requires explicit confirmed=True
  - Payment processing requires explicit confirmed=True
  - LLM is instructed to summarize before confirming

✅ Idempotency on money/inventory actions
  - Order creation supports idempotency_key
  - Payment processing supports idempotency_key
  - Duplicate keys return original result

✅ Graceful failure handling
  - ToolNotFound error with clear message
  - Timeout errors with retry suggestion
  - Missing field detection with field names
  - Service-level exceptions mapped to user-friendly messages

✅ Observability
  - Every tool call logged with name, success, duration_ms
  - Tool execution traced with callbacks
  - Memory records tool results per conversation
```

---

## Testing Coverage

```
✅ OrderToolTest
  - Create order with items and confirmation
  - Create order requires confirmation gate
  - Create draft order without items
  - Add item to existing order
  - Show order details
  - Cancel order

✅ PaymentToolTest
  - Missing field validation
  - Invalid payment method error
  - Order not found error
  - Confirmation gate required
  - Successful payment with confirmation
  - Idempotency key prevents duplicate payments

✅ ReservationToolTest
  - Check table availability
  - Create reservation with hold
  - Missing field validation
  - Confirm held reservation
  - Expired hold detection
  - Cancel reservation

✅ EscalationToolTest
  - Successful escalation creation

✅ SearchKnowledgeToolTest
  - Empty query validation

✅ MultiTurnOrderingTest (integration)
  - Full multi-turn ordering flow
  - State persistence across turns
  - Quantity slot filling
  - Delivery method and address collection
  - Cancellation with "never mind"
  - Topic switching preserving state
  - Item change during flow
  - Pickup flow (skips address)
  - Multiple items in cart
```

---

## Success Criteria

```
✅ User: "What food do you have?"
✅ Agent: Uses MenuTool, Returns real menu data from database

✅ User: "What are your hours?"
✅ Agent: Uses FAQTool, Returns accurate restaurant info

✅ User: "I want to order..."
✅ Agent: Uses OrderTool, Guides through multi-turn ordering

✅ User: "Pay with Chapa"
✅ Agent: Uses PaymentTool, Returns secure checkout URL

✅ User: "Book a table"
✅ Agent: Uses ReservationTool, Holds reservation with TTL
```

---

# ✅ Milestone 3: Menu Intelligence Agent

**Status: Complete**

## Goal

Make the AI understand restaurant menus and provide intelligent recommendations using preferences, dietary needs, and customer memory.

---

## Features Implemented

### Enhanced MenuTool (list_menu_items)
```
✅ Natural language query support (query parameter)
  - Auto-detects: vegetarian, vegan, spicy, price hints, category mentions
  - Falls back to free-text search when no structural filter matches

✅ Allergen exclusion support (allergens parameter)
  - Comma-separated allergens to exclude (e.g. "gluten, dairy")
  - Case-insensitive matching against the allergens field

✅ Dietary need filtering (dietary parameter)
  - Supports: vegetarian, vegan, gluten-free, dairy-free keywords
  - Combines dietary flags with allergen exclusion

✅ Removed hardcoded category enum
  - Category is now a free-text field matching actual menu categories
  - Dynamically populated from the database

✅ Structured filters preserved
  - category, vegetarian, vegan, spicy, max_price, search all unchanged
```

---

### New Tool: GetMenuItemDetailsTool (get_menu_item_details)
```
✅ Returns comprehensive item details
  - name, description, price, category
  - dietary flags (vegetarian, vegan, spicy)
  - allergens, availability
  - optional similar_items list

✅ Input validation
  - Missing item_id returns clear error with missing_fields
  - Non-existent ID returns "could not find" message
```

---

### New Tool: RecommendMenuTool (recommend_menu_items)
```
✅ Personalized recommendations using:
  - Dietary preferences (vegetarian, vegan, spicy)
  - Price range (max_price)
  - Category preference
  - Natural language query
  - Customer memory (past orders, favorites, dietary restrictions)

✅ Scoring system:
  - Preference matches: +5-12 points
  - Customer profile matches: +3-20 points
  - Favorites bonus: +20 points
  - Tags with reason explanations for each recommendation

✅ Safe fallback when no strong matches:
  - Returns available items with "popular choice" label
  - Never returns empty unless no menu items exist
```

---

### RecommendationService (agent/recommender.py)
```
✅ Scoring engine
  - Item-level scoring against preferences and customer profile
  - Weighted scoring with configurable priorities
  - Reason generation for explainable recommendations

✅ Customer profile integration
  - Reads dietary_restrictions, spice_tolerance, favorite_items, budget_range
  - Avoids known allergens from profile
  - Ties into SemanticMemory for long-term preferences

✅ Configurable
  - count parameter (default 3, max 10)
  - preferences dict for flexible querying
  - customer_profile dict for personalized results
```

---

### Enhanced MenuService
```
✅ search_natural(query, **filters)
  - Parses natural language for dietary keywords
  - Extracts price hints ("under $15")
  - Detects category mentions
  - Falls back to text search

✅ get_item_with_details(item_id, include_similar)
  - Full item details including allergens and availability
  - Optional similar items via find_alternatives

✅ search_by_allergen(allergen)
  - Excludes items containing given allergen

✅ search_by_dietary(dietary)
  - Matches dietary keywords against flags and allergens

✅ get_categories()
  - Returns distinct categories from available items
```

---

### Enhanced MenuRepository
```
✅ get_categories()
  - Distinct category names from available items

✅ get_items_by_ids(ids)
  - Bulk lookup returning available items only

✅ search_by_allergens(exclude_allergens)
  - Case-insensitive allergen exclusion
  - Supports comma-separated multiple allergens

✅ search_by_dietary_need(dietary)
  - Multi-keyword dietary need detection
  - Combines flag filtering with allergen exclusion
```

---

## Testing Coverage

### MenuRepository Tests
```
✅ get_categories() — returns distinct categories, excludes sold-out
✅ get_items_by_ids() — bulk lookup, excludes unavailable
✅ search_by_allergens() — single and multi-allergen exclusion
✅ search_by_dietary_need() — vegetarian, vegan, gluten-free
```

### MenuService Tests
```
✅ get_item_with_details() — full details, with similar items, not found
✅ search_natural() — spicy detection, price parsing
✅ search_by_allergen() — allergen exclusion
✅ search_by_dietary() — vegan diet matching
```

### MenuTool Tests (enhanced)
```
✅ query parameter — natural language search
✅ allergens parameter — gluten-free results
✅ dietary parameter — vegan filtering
✅ vegetarian flag — dietary preference filtering
✅ empty results — graceful handling
```

### GetMenuItemDetailsTool Tests
```
✅ existing item — returns all fields including allergens
✅ with similar items — returns similar_items list
✅ non-existent item — "not found" error
✅ missing item_id — field validation error
```

### RecommendMenuTool Tests
```
✅ no preferences — returns fallback recommendations
✅ vegetarian preference — filters correctly
✅ vegan preference — excludes non-vegan
✅ spicy preference — fallback when none match
✅ with customer_id — handles unknown customer gracefully
✅ max_price — filters by budget
```

### RecommendationService Tests
```
✅ preference-based scoring — spicy + max_price
✅ vegan preference — single correct result
✅ customer profile — favorites + dietary bonus
✅ no available items — empty results
✅ count limiting — respects max count
✅ reasons included — every recommendation has explanations
```

---

## Success Criteria

```
✅ Customer: "Recommend something spicy under $20"
✅ Agent: Uses recommend_menu_items tool
✅ Agent: Returns personalized recommendations with reasons

✅ Customer: "What's on the menu that's gluten-free?"
✅ Agent: Uses list_menu_items with allergens="gluten"
✅ Agent: Returns only items without gluten

✅ Customer: "Tell me about item 42"
✅ Agent: Uses get_menu_item_details
✅ Agent: Returns full details with allergens and similar items

✅ Customer: "I'm vegetarian, what do you suggest?"
✅ Agent: Checks customer memory for preferences
✅ Agent: Returns personalized recommendations
```

---

## Files Changed

### New Files
```
- backend/agent/recommender.py — RecommendationService
- backend/agent/tools/recommend.py — RecommendMenuTool
```

### Modified Files
```
- backend/menu/repositories.py — added get_categories, get_items_by_ids, search_by_allergens, search_by_dietary_need
- backend/menu/services.py — added search_natural, get_item_with_details, search_by_allergen, search_by_dietary, get_categories
- backend/agent/tools/menu.py — enhanced list_menu_items, added GetMenuItemDetailsTool
- backend/agent/tools/__init__.py — registered GetMenuItemDetailsTool, RecommendMenuTool
- backend/agent/controller.py — imported and registered new tools
- backend/agent/models.py — added SemanticMemory.to_dict()
- backend/agent/tests.py — added MenuToolEnhancedTest, GetMenuItemDetailsToolTest, RecommendMenuToolTest, RecommendationServiceTest
- backend/menu/tests.py — added MenuRepositoryTest, MenuServiceTest
- docs/ai-agent-development-roadmap.md — marked Milestone 3 complete
```

---

# ✅ Milestone 4: Ordering Agent

**Status: Complete**

## Goal

Empower the AI agent to manage the full ordering workflow: browse menu via Milestone 3 tools, add items to cart, modify quantities, remove items, view cart, and checkout with delivery/payment details — all through natural conversation.

---

## Architecture

The Ordering Agent follows the same layered architecture as Milestone 3:

```
Agent → ManageCartTool / CheckoutCartTool → CartService → CartRepository → Cart/CartItem
                                        ↘ OrderService → OrderRepository → Order
```

Two new tools:

| Tool | Purpose | Actions |
|------|---------|--------|
| `ManageCartTool` (manage_cart) | Full cart management | `add`, `update`, `remove`, `show` |
| `CheckoutCartTool` (checkout_cart) | Checkout with confirmation gate | Summary → `awaiting_confirmation` → `confirmed=True` → creates order |

---

## Cart-to-Order Flow

```
Customer: "I want 2 pizzas"
                 ↓
ManageCartTool (action=add, item_name=..., quantity=2)
                 ↓
         Cart created (or reused)
         Item added to CartItem
                 ↓
Customer: "checkout"
                 ↓
CheckoutCartTool → Shows order summary (items, total, tax, delivery fee)
                 ↓
Customer: "delivery, 123 Main St, card"
                 ↓
CheckoutCartTool → Requires confirmation
                 ↓
Customer: "yes, confirm"
                 ↓
CheckoutCartTool (confirmed=True) → Creates Order, marks Cart converted
                 ↓
         Order created, email confirmation sent
```

---

## Key Design Decisions

1. **Cart → Order separation**: Cart is a temporary, editable session. Checkout converts cart to an Order (locked, sent to kitchen). This mirrors real restaurant workflow where orders are immutable once submitted.

2. **Confirmation gate**: `CheckoutCartTool` requires explicit `confirmed=True` before creating the order, matching the existing pattern from `OrderTool`/`PaymentTool`.

3. **Cart persistence**: Cart is persisted in its own DB table (`Cart` + `CartItem`), surviving across conversation turns and server restarts.

4. **Delivery address requirement**: Delivery method `"delivery"` requires a delivery address; `"pickup"` skips address collection.

5. **Prefetch cache fix**: Discovered that Django's `prefetch_related` caches related objects, causing stale data after item updates. Fixed `CartService.get_cart_summary` to use a fresh query (`CartItem.objects.filter`) instead of the related manager.

---

## Planner Integration

The `LocalPlanner` routes:

- "checkout" / "place order" / "confirm order" → `checkout_cart` tool
- "order" / "add" / "remove" / "cart" → `manage_cart` if no existing order_id; otherwise `manage_order`
- `_cart_args` extracts `action` (show/add/remove), `item_name`, `quantity`, `customer_id` from natural language

---

## Testing Coverage

### CartToolTest (7 tests)
| Test | Scenario |
|------|----------|
| `test_add_item_to_cart` | Add item by name, verify success and cart data |
| `test_add_item_twice_quantity_increases` | Add same item twice (1 + 3), verify merge |
| `test_add_item_not_found` | Non-existent item name, verify error + alternatives |
| `test_show_cart_with_items` | Add item then show, verify message contains item and total |
| `test_show_empty_cart` | Show cart for new customer, verify "empty" message |
| `test_remove_item` | Add then remove, verify "removed" message |
| `test_unknown_action` | Unknown action, verify error message |

### CheckoutCartToolTest (6 tests)
| Test | Scenario |
|------|----------|
| `test_checkout_requires_missing_fields` | Checkout without delivery/payment method, verify missing field detected |
| `test_checkout_without_items` | Checkout for empty cart, verify "empty" message |
| `test_checkout_without_confirmation` | All fields present but not confirmed, verify awaiting_confirmation |
| `test_checkout_with_confirmation_creates_order` | Full checkout with confirmation, verify Order created |
| `test_checkout_delivery_requires_address` | Delivery without address, verify delivery_address in data |
| `test_checkout_delivery_with_address_and_confirmation` | Full delivery flow, verify order created |

---

## Success Criteria

```
✅ Customer: "I want 2 pizzas"
✅ Agent: Uses ManageCartTool, creates cart, adds items

✅ Customer: "Show my cart"
✅ Agent: Uses ManageCartTool (action=show), Returns cart summary with items and total

✅ Customer: "Remove the soda"
✅ Agent: Uses ManageCartTool (action=remove), Removes item from cart

✅ Customer: "Checkout with delivery to 123 Main St, pay with card"
✅ Agent: Uses CheckoutCartTool, Shows order summary, Waits for confirmation

✅ Customer: "Yes, confirm"
✅ Agent: Places order, sends confirmation email, marks cart as converted
```

---

# Milestone 5: Payment and Delivery Agent


## Goal


Complete real transactions.


---

## Features


Payment:


```
Payment Methods

Payment Request

Payment Verification

```


Delivery:


```
Address Selection

Delivery Calculation

Delivery Tracking

```

---

## Success Criteria


Customer can:


```
Order

↓

Pay

↓

Receive confirmation

```

---

# ✅ Milestone 6: Reservation Agent

**Status: Complete**

## Goal

Guide customers through a multi-turn reservation flow: date → time → party size → name → phone → email → confirmation — with slot availability checking, nearby alternative suggestions, and email confirmation.

---

## Architecture

The Reservation Agent uses the same **state machine pattern** as the Order Workflow from Milestone 4:

```
Customer Message → Agent Controller → ReservationWorkflow (new)
                                            ↓
                                manages ConversationMemory state
                                (reservation_status field for persistence)
                                            ↓
                                delegates to ReservationTool (enhanced)
                                            ↓
                                delegates to ReservationService (existing)
                                            ↓
                                delegates to ReservationRepository (existing)
                                            ↓
                                    Reservation model (existing)
```

---

## Workflow States

```
START → AWAITING_DATE → AWAITING_TIME → AWAITING_PARTY_SIZE
     → AWAITING_CUSTOMER_NAME → AWAITING_PHONE → AWAITING_EMAIL
     → AWAITING_CONFIRMATION → DONE (reservation created)

At any state:
  - "cancel" / "never mind" → resets flow
  - Multiple fields extracted together (e.g., "table for 4 tomorrow at 7pm" → skips 3 states)
```

---

## Key Enhancements

### 1. Slot Availability Suggestions
When a time slot is full, the enhanced `ReservationTool` now suggests nearby alternatives (30/60 min before/after):
```
"Sorry, no tables at 7pm. Would 6:30pm or 7:30pm work instead?"
```

### 2. Email Confirmation on Confirm
When a reservation is confirmed, an email confirmation is sent via `django.core.mail.send_mail`.

### 3. Memory Persistence
- `ConversationMemory.reservation_status` added as a proper dataclass field
- Persisted via `to_state()`/`from_state()` so multi-turn state survives across API requests
- Memory includes `customer_name`, `phone`, `email` for future personalization

### 4. Planner FAQ Detection Fix
Fixed `planner.py` to not treat reservation-related time mentions ("table at 7") as FAQ queries.

---

## Files Created

| File | Purpose |
|------|---------|
| `backend/agent/reservation_workflow.py` | Multi-turn state machine for reservation creation — 7 states with smart batch parsing and cancellation |

## Files Modified

| File | Changes |
|------|---------|
| `backend/agent/tools/reservation.py` | Added `_find_nearby_slots()` for alternative time suggestions; added email confirmation on confirm; added `customer_name`/`email`/`phone` memory updates |
| `backend/agent/controller.py` | Imported and initialized `ReservationWorkflow`; routed reservation intents to workflow before order workflow |
| `backend/agent/planner.py` | Fixed `_is_faq()` to skip reservation-related time mentions |
| `backend/agent/memory.py` | Added `reservation_status` field to `ConversationMemory` dataclass; included in `to_state()`/`from_state()` for persistence |
| `backend/agent/tests.py` | Added `ReservationWorkflowTest` (11 tests) and `ReservationToolSlotSuggestTest` (2 tests) |
| `docs/ai-agent-development-roadmap.md` | Marked Milestone 6 complete |

---

## Testing Coverage

### ReservationWorkflowTest (11 tests)
| Test | Scenario |
|------|----------|
| `test_returns_none_without_reservation_context` | Non-reservation messages return None |
| `test_starts_reservation_flow_with_keyword` | "book a table" starts flow, asks for date |
| `test_collects_date_then_time` | Date → time → party_size progression |
| `test_collects_time_then_party_size` | Sequential collection |
| `test_collects_party_size_then_name` | Party size → customer name |
| `test_collects_name_then_phone` | Name → phone number |
| `test_collects_phone_then_email` | Phone → email address |
| `test_shows_summary_before_confirmation` | Full summary before final confirm |
| `test_cancel_during_flow` | "never mind" cancels and resets all state |
| `test_creates_reservation_on_confirmation` | Full flow with "yes" creates reservation |
| `test_extracts_multiple_fields_at_once` | "table for 4 tomorrow at 7pm" extracts 3 fields in one message |

### ReservationToolSlotSuggestTest (2 tests)
| Test | Scenario |
|------|----------|
| `test_availability_shows_nearby_slots_when_full` | Full slot suggests nearby alternatives |
| `test_confirm_includes_customer_memory` | Confirm adds customer_name/email to memory_updates |

---

## Success Criteria

```
✅ Customer: "I'd like to book a table"
✅ Agent: Starts reservation workflow, asks for date

✅ Customer: "Tomorrow at 7pm"
✅ Agent: Extracts both fields, checks availability, asks for party size

✅ Customer: "A table for 4"
✅ Agent: Saves party size, asks for name

✅ Customer: "My name is John"
✅ Agent: Saves name, asks for phone & email

✅ Customer: "+1234567890" → "john@test.com"
✅ Agent: Shows summary, asks for confirmation

✅ Customer: "Yes"
✅ Agent: Creates reservation, sends email confirmation

✅ Customer: "Is Friday at 8pm available?" → full slot
✅ Agent: Suggests nearby times: "Would 7:30pm or 8:30pm work?"
```

---# ✅ Milestone 7: Customer Memory

**Status: Complete**

## Goal

Make AI personalized by actively extracting customer preferences, detecting "usual" orders, and injecting personalized context into conversations.

---

## What Was Already in Place

- `SemanticMemory` model for long-term fact storage with confidence tracking
- `CustomerProfile` model with display_name, dietary_restrictions, favorite_items, total_orders
- `MemoryManager` for episodic event recording and fact learning
- `Summarizer` for post-conversation fact extraction
- `RecommendationService` that uses memory for menu recommendations
- Frontend Memory Panel with profile, facts, and event display
- "Returning guests" section in system prompt

---

## What Was Added / Enhanced

### 1. MemoryEngine (`backend/agent/memory_engine.py`) — New
Real-time preference extraction on every user message:
- **Inline extraction**: Detects "my favorite is X", "I love X", "I don't like X", "the usual", "I usually order X", dietary restrictions, and spice preferences
- **Topic inference**: Automatically detects conversation topic (ordering, menu, reservation, preference, info, complaint) for short-term memory
- **Usual-order detection**: Queries completed/paid orders to find the customer's most frequently ordered item
- **Proactive suggestions**: Generates structured data for the LLM (welcome-back context, favorites list, dietary info)
- **Personalized greeting**: Builds a plain-text string like "Welcome back, John! Would John like their usual Ethiopian Coffee?" for prompt injection
- **Async wrappers**: `inline_extract()`, `get_suggestions()`, `get_greeting()` for use in async controller methods

### 2. ManagePreferencesTool (`backend/agent/tools/memory_tool.py`) — New
Explicit customer-facing memory management tool:
- **set_favorite**: Save a favorite item (e.g., "Ethiopian coffee")
- **set_preference**: Save key-value preferences (spice_tolerance, preferred_cuisine, etc.)
- **get_my_profile**: Returns the customer's full profile as natural language
- **get_usual_order**: Shows the customer's most-ordered item from order history

### 3. Enhanced ConversationMemory (`backend/agent/memory.py`)
- Added `discussed_topics: list[str]` — tracks topics discussed this session
- Added `conversation_summary: str | None` — stores running conversation notes
- Both are serialized via `to_state()`/`from_state()` for cross-request persistence

### 4. Controller Integration (`backend/agent/controller.py`)
- Inline extraction runs on every user message (before workflows)
- Proactive memory suggestions injected into ReAct context for both `_run_with_react()` and `_run_with_react_stream()`
- `ManagePreferencesTool` registered in tool registry

### 5. Enhanced Prompts (`backend/agent/prompts.py`)
- New "Preference management" section: handles "my favorite is...", "what do you know about me?", "I'd like the usual"
- Instructions for using `manage_preferences` tool

---

## Files Created / Modified

| File | Status | Changes |
|------|--------|---------|
| `backend/agent/memory_engine.py` | **New** | MemoryEngine: inline extraction, topic inference, usual-order detection, proactive suggestions |
| `backend/agent/tools/memory_tool.py` | **New** | ManagePreferencesTool: set_favorite, set_preference, get_my_profile, get_usual_order |
| `backend/agent/memory.py` | Modified | Added discussed_topics + conversation_summary fields |
| `backend/agent/controller.py` | Modified | Inline extraction on every message, memory suggestions in ReAct context, new tool registration |
| `backend/agent/prompts.py` | Modified | Added "Preference management" section |
| `backend/agent/tools/__init__.py` | Modified | Added ManagePreferencesTool import/export |
| `backend/agent/tests.py` | Modified | Added 41 new tests across 5 test classes |
| `docs/ai-agent-development-roadmap.md` | Modified | Marked Milestone 7 complete |

---

## Testing Coverage (41 new tests)

### ExtractionPatternTest (14 tests)
| Test | Scenario |
|------|----------|
| `test_extract_favorite_pattern` | "my favorite is X" extracts X |
| `test_extract_favorite_alt_pattern` | "X is my favorite" extracts X |
| `test_extract_favorite_with_punctuation` | Handles trailing punctuation |
| `test_extract_favorite_no_match` | No match returns None |
| `test_extract_like_pattern` | "I love X" extracts X |
| `test_extract_like_with_really` | "I really like X" extracts X |
| `test_extract_dislike_pattern` | "I don't like X" extracts X |
| `test_extract_dislike_hate` | "I hate X" extracts X |
| `test_extract_usual_indicator` | "the usual" returns True |
| `test_extract_usual_order_pattern` | "I usually order X" extracts X |
| `test_extract_dietary_pattern` | "I'm allergic to X" extracts X |
| `test_extract_spice_pattern` | "I like spicy" extracts spicy |
| `test_infer_topic_ordering` | Topic inference for ordering |
| `test_infer_topic_preference` | Topic inference for preferences |

### MemoryEngineTest (12 tests)
| Test | Scenario |
|------|----------|
| `test_extract_favorite_inline` | Inline extraction persists to SemanticMemory |
| `test_extract_like_inline` | Like extraction persists |
| `test_extract_dislike_inline` | Dislike extraction persists |
| `test_extract_dietary_inline` | Dietary extraction persists |
| `test_extract_spice_inline` | Spice extraction persists |
| `test_topic_tracking` | Topics tracked in memory.discussed_topics |
| `test_multiple_topics` | Multiple messages add multiple topics |
| `test_get_usual_order` | Usual order detection from order history |
| `test_get_usual_order_no_orders` | No orders returns None |
| `test_get_proactive_suggestions_with_history` | Profile generates suggestions |
| `test_get_personalized_greeting` | Greeting includes name and usual order |
| `test_no_extraction_for_anonymous` | Anonymous still extracts values (no persist) |

### ManagePreferencesToolTest (8 tests)
| Test | Scenario |
|------|----------|
| `test_set_favorite` | Saves and confirms favorite |
| `test_set_favorite_missing_item` | Missing item returns error |
| `test_set_preference` | Saves key/value |
| `test_set_preference_missing_fields` | Missing key/value returns error |
| `test_get_profile_no_data` | New customer returns helpful message |
| `test_get_profile_with_data` | Customer with data sees their profile |
| `test_get_usual_order_with_data` | Customer with history sees usual order |
| `test_unknown_action` | Unknown action returns error |

### TopicTrackingTest (6 tests)
| Test | Scenario |
|------|----------|
| `test_discussed_topics_default_empty` | New memory has empty topics |
| `test_add_topic` | Topics can be added |
| `test_no_duplicate_topics` | Same topic not added twice |
| `test_conversation_summary_default_none` | Default is None |
| `test_conversation_summary_set_and_get` | Can be set and retrieved |
| `test_state_persistence_includes_topics` | Survives to_state/from_state round-trip |

### MemoryDataFlowTest (1 test)
| Test | Scenario |
|------|----------|
| `test_preference_extraction_then_state_round_trip` | Full flow: extract → persist → save → restore → verify |

---

## Example Flow

```
Customer: "My favorite is Ethiopian coffee"
    ↓ MemoryEngine.extract_inline() extracts "Ethiopian coffee" as favorite
    ↓ MemoryManager.learn_fact(category="favorite", value="Ethiopian coffee")
    ↓ CustomerProfile.favorite_items updated
    ↓ discussed_topics: ["preference"]

Next visit:
Customer: "Hi, I'm back!"
    ↓ MemoryEngine.get_proactive_suggestions() loads: usual=Ethiopian Coffee, favorites
    ↓ Injected into ReAct context: "Welcome back, John! Would John like their usual Ethiopian Coffee?"
    ↓ Agent (LLM): "Welcome back, John! Would you like your usual Ethiopian coffee tonight?"
```

---

## Success Criteria

```
✅ Customer: "My favorite is Ethiopian coffee"
✅ MemoryEngine: Extracts and saves to long-term memory

✅ Customer: "I don't like spicy food"
✅ MemoryEngine: Saves dislike, updates profile

✅ Customer: "I'd like the usual"
✅ Agent: Retrieves usual order from memory
✅ Agent: Starts ordering flow with usual item

✅ Customer: "What do you know about me?"
✅ Agent: Uses manage_preferences tool to show profile

✅ Customer: (Returns after previous visit)
✅ Agent: Greets by name, references past orders naturally

✅ Short-term memory: Topics persist across conversation turns
✅ Long-term memory: Preferences persist across sessions
```

---

# Milestone 8: Advanced RAG System


## Goal


Improve knowledge accuracy.


---

## Features


Add:


```
Hybrid Search

Metadata Filtering

Re-ranking

Knowledge Management

Admin Upload

```

---

## Sources:


```
Menu

Policies

FAQ

Promotions

Restaurant documents

```

---

# Milestone 9: Multi-Agent System


## Goal


Split responsibilities into specialized agents.


---

## Agents:


```
Customer Agent


Order Agent


Reservation Agent


Kitchen Agent


Delivery Agent


Analytics Agent

```

---

## Architecture:


```
Customer

↓

Supervisor Agent

↓

Specialized Agents

```

---

# Milestone 10: Production Intelligence


## Goal


Create enterprise-level AI.


---

## Features:


Advanced:


```
Voice ordering

Recommendation engine

Predictive ordering

Customer analytics

AI restaurant manager

```

---

# 4. Development Priority


Build order:


```
1.
Conversation


2.
Tools


3.
Menu


4.
Orders


5.
Payments


6.
Reservations


7.
Memory


8.
Advanced AI

```

---

# 5. Things NOT To Build Early


Avoid:


```
Multi-agent

Voice

Complex autonomy

Fine tuning

Custom models

```

until the core workflow works.

---

# 6. Definition of Done


A milestone is complete when:


```
Feature implemented

Tests written

Documentation updated

Security reviewed

Monitoring added

```

---

# 7. Engineering Rule


Every new AI capability must answer:


Question:


"Does this improve customer or restaurant operation?"


If no:

Do not build it.

---

# 8. Final Goal


The final system should become:


```
A complete AI restaurant employee


that can:

Understand customers

Remember preferences

Recommend food

Create orders

Process workflows

Manage reservations

Assist restaurant staff

Improve over time

```

---

# 9. Conclusion


This roadmap provides a controlled path from a simple AI assistant into a complete autonomous restaurant intelligence platform.

The system grows gradually while maintaining reliability, security, and business value.