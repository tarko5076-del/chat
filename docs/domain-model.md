# Domain Model

**Project:** Restaurant Intelligence Platform

**Version:** 1.0

**Status:** Draft

---

# 1. Purpose

This document defines the core business entities, relationships, and rules of the Restaurant Intelligence Platform.

The domain model represents the real-world restaurant ecosystem and provides the foundation for:

- Database design
- API design
- AI Agent tools
- Business services
- Validation rules
- Future AI capabilities

---

# 2. Domain Philosophy

The platform follows Domain-Driven Design principles.

The system is organized around business capabilities rather than technical components.

The main idea:

```
Customer Intent

↓

Domain Understanding

↓

Business Operation

↓

Data Persistence
```

The AI Agent understands customer requests, but domain services control business execution.

---

# 3. Core Domain Overview

The restaurant domain consists of:

```
Restaurant

├── Customer

├── Menu

├── Ordering

├── Payment

├── Delivery

├── Reservation

├── Memory

├── Conversation

├── Recommendation

└── Notification
```

---

# 4. Entity Relationship Overview


```
                     Restaurant
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
      Menu            Customer        Reservation
        │                │
        ▼                ▼
   Menu Item          Orders
                         │
                         ▼
                    Order Items
                         │
                         ▼
                      Payment


Customer

    │

    ├── Conversation History

    ├── Memory

    ├── Favorites

    ├── Addresses

    └── Preferences

```

---

# 5. Restaurant Entity

## Purpose

Represents a restaurant tenant inside the platform.

A restaurant is the owner of all restaurant-related data.

---

## Attributes

```
id

name

description

address

phone

email

opening_hours

status

created_at

updated_at
```

---

## Business Rules

- Every restaurant is isolated from other restaurants.
- All customer data belongs to a restaurant context.
- Menu items belong to exactly one restaurant.
- Orders cannot cross restaurants.

---

# 6. Customer Entity

## Purpose

Represents a restaurant customer.

The customer is the main user interacting with the AI Agent.

---

## Attributes

```
id

name

phone

email

account_status

created_at

updated_at
```

---

## Relationships

Customer has:

```
Many Orders

Many Reservations

Many Conversations

Many Memories

Many Favorite Items

Many Addresses
```

---

## Business Rules

- A customer can only access their own information.
- Customer history improves personalization.
- Customer identity must be verified before sensitive actions.

---

# 7. Menu Entity

## Purpose

Represents restaurant food categories and available products.

---

## Structure

```
Menu

    |

    └── Categories

            |

            └── Menu Items
```

---

# 8. Menu Item Entity

## Purpose

Represents a food or beverage product.

---

## Attributes

```
id

name

description

category

price

ingredients

availability

image

created_at
```

---

## Business Rules

- Only available items can be ordered.
- Prices are controlled by the backend.
- AI cannot invent menu items.
- Recommendations must come from available products.

---

# 9. Cart Entity

## Purpose

Temporary collection of customer selections before checkout.

---

## Attributes

```
id

customer

restaurant

status

created_at
```

---

## Cart Item

```
menu_item

quantity

special_instruction
```

---

## Business Rules

- Cart belongs to one customer.
- Cart belongs to one restaurant.
- Cart must be validated before order creation.

---

# 10. Order Entity

## Purpose

Represents a confirmed purchase.

---

## Lifecycle

```
Created

↓

Pending Payment

↓

Paid

↓

Preparing

↓

Ready

↓

Completed

↓

Cancelled
```

---

## Attributes

```
id

customer

restaurant

status

total_amount

order_type

created_at
```

---

## Order Types

```
Pickup

Delivery
```

---

## Business Rules

- Order must belong to a customer.
- Order must contain at least one item.
- Completed orders cannot be modified.
- Payment status controls order confirmation.

---

# 11. Order Item Entity

## Purpose

Represents individual products inside an order.

---

## Attributes

```
order

menu_item

quantity

price_at_purchase

notes
```

---

## Business Rules

The purchased price must be stored.

Reason:

Menu prices can change later.

---

# 12. Payment Entity

## Purpose

Tracks financial transactions.

---

## Attributes

```
id

order

method

amount

status

transaction_reference

created_at
```

---

## Payment Status

```
Pending

Processing

Completed

Failed

Refunded
```

---

## Business Rules

- Payment verification is external.
- AI cannot mark payment as successful.
- Only payment services update payment state.

---

# 13. Reservation Entity

## Purpose

Represents a customer's table booking.

---

## Attributes

```
id

customer

restaurant

date

time

guest_count

status
```

---

## Lifecycle

```
Requested

↓

Confirmed

↓

Completed

↓

Cancelled
```

---

## Business Rules

- Reservation availability must be checked.
- Double booking is prohibited.
- Cancellation rules must be enforced.

---

# 14. Address Entity

## Purpose

Stores customer delivery locations.

---

## Attributes

```
customer

label

address

latitude

longitude

is_default
```

---

## Business Rules

Customers may have multiple addresses.

One address may be marked default.

---

# 15. Favorite Entity

## Purpose

Stores customer's favorite food.

---

## Sources

Favorites can come from:

```
Explicit user action

Example:

"Save this as my favorite"


AI inference

Example:

Customer orders same item frequently
```

---

## Attributes

```
customer

menu_item

created_at

source
```

---

# 16. Conversation Entity

## Purpose

Stores interaction history.

---

## Attributes

```
customer

messages

summary

created_at
```

---

## Rules

The system should not depend only on raw messages.

Important information should become memory.

---

# 17. Memory Entity

## Purpose

Stores useful long-term customer information.

---

## Examples

```
Favorite food

Food preference

Delivery preference

Payment preference

Important customer notes
```

---

## Memory Types

```
Explicit Memory

Customer directly requested.


Implicit Memory

Learned from behavior.
```

---

# 18. Knowledge Entity

## Purpose

Represents information available to the RAG system.

---

## Examples

```
Menu documents

Restaurant policies

FAQs

Ingredients

Promotions
```

---

## Flow

```
Document

↓

Chunk

↓

Embedding

↓

Vector Database

↓

Retrieval

↓

LLM Context
```

---

# 19. Notification Entity

## Purpose

Tracks communication events.

---

## Examples

```
Order confirmation

Payment notification

Reservation reminder

Delivery update
```

---

# 20. Domain Rules Summary

The following rules apply everywhere:

## Ownership

Every entity must have clear ownership.

---

## Security

Users can only access their own resources.

---

## Validation

Business rules must be enforced by backend services.

---

## AI Limitation

The AI can request actions.

The backend decides whether actions are allowed.

---

# 21. Future Domain Extensions

The architecture supports:

```
Inventory

Supplier

Kitchen Workflow

Staff Management

Loyalty Program

Reviews

Marketing Campaigns

Analytics

Voice Interaction

Multi-Agent Operations
```

---

# 22. Conclusion

The domain model defines the language of the Restaurant Intelligence Platform.

Every AI capability, API endpoint, database table, and business service should be built around these domain concepts.

A stable domain model allows the AI Agent to grow without creating complexity.