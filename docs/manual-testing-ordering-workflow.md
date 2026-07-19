# Manual Testing Guide: Ordering Workflow

**Applies to:** Milestone 4 (ManageCartTool + CheckoutCartTool)

**Last Updated:** July 2026

---

## Overview

This guide covers **three ways** to manually test the ordering workflow:

| Method | When to use |
|--------|-------------|
| **Django shell** — Direct tool calls | Quickest way to test business logic without auth |
| **REST API** — Cart endpoints | Test the underlying REST layer (authenticated) |
| **Chat API** — Agent via planner/LLM | Full end-to-end conversational flow |

---

## Prerequisites

1. **Start the backend:**
   ```bash
   cd backend
   .venv/Scripts/python manage.py migrate
   .venv/Scripts/python manage.py seed_menu    # Populates the menu table
   .venv/Scripts/python manage.py runserver
   ```

2. **Create a test user** (for REST/chat API tests):
   ```bash
   .venv/Scripts/python manage.py shell -c "
   from django.contrib.auth import get_user_model
   User = get_user_model()
   User.objects.create_user(username='testuser', email='test@test.com', password='testpass123')
   print('Created testuser')
   "
   ```

3. **Get a JWT token** (for REST/chat API tests):
   ```bash
   curl -s http://localhost:8000/api/token/ \
     -H "Content-Type: application/json" \
     -d '{"username":"testuser","password":"testpass123"}' \
     | .venv/Scripts/python -c "import sys,json; print(json.load(sys.stdin).get('access',''))"
   ```

   Save the returned token as `TOKEN` for subsequent requests.

---

## Method 1: Django Shell (Fastest — Direct Tool Calls)

Start a Django shell:

```bash
cd backend
.venv/Scripts/python manage.py shell
```

### 1.1 Set Up the Tools

```python
import os
os.environ['USE_SQLITE'] = 'true'

import django
django.setup()

from agent.tools.cart import ManageCartTool
from agent.tools.checkout import CheckoutCartTool
from agent.tools.menu import MenuTool
from menu.models import MenuItem

cart_tool = ManageCartTool()
checkout_tool = CheckoutCartTool()
menu_tool = MenuTool()
```

### 1.2 Browse the Menu

```python
# List all menu items (the simple way)
items = MenuItem.objects.filter(available=True)
for item in items:
    print(f"  #{item.id}  {item.name} — ${float(item.price):.2f}  {'🥗 Vegan' if item.vegan else ''} {'🌶️ Spicy' if item.spicy else ''}")

# Or use the MenuTool
result = menu_tool.execute()
print(result.message)

# Search for specific items
result = menu_tool.execute(query="pizza")
print(result.data)
```

### 1.3 Add Items to Cart

```python
CUSTOMER = "test-customer-manual"

# Add 2 Pizzas (use actual menu_item_id from your database)
result = cart_tool.execute(
    action="add",
    customer_id=CUSTOMER,
    item_name="Pizza Margherita",  # or any item from your menu
    quantity=2,
)
print(result.message)
# Expected: "I've added 2 x Pizza Margherita to your cart. (Cart total: $25.98)"
```

**Expected output:**
```
I've added 2 x Pizza Margherita to your cart. (Cart total: $25.98)
```

### 1.4 Add a Second Item

```python
result = cart_tool.execute(
    action="add",
    customer_id=CUSTOMER,
    item_name="Garden Salad",  # or another item from your menu
    quantity=1,
)
print(result.message)
```

**Expected output:**
```
I've added 1 x Garden Salad to your cart. (Cart total: $34.97)
```

### 1.5 Add Same Item Again (Merge Test)

```python
# Adding the same item should merge quantities
result = cart_tool.execute(
    action="add",
    customer_id=CUSTOMER,
    item_name="Pizza Margherita",
    quantity=3,
)
print(result.message)
# Expected: "I've added 3 x Pizza Margherita to your cart. (Cart total: $60.95)"
print(f"Quantity in cart: {result.data['added_item']['quantity']}")
# Expected: Quantity in cart: 5 (was 2, added 3 more)
```

### 1.6 Show Cart

```python
result = cart_tool.execute(
    action="show",
    customer_id=CUSTOMER,
)
print(result.message)
```

**Expected output (example):**
```
📋 Your Cart:

  • 5 x Pizza Margherita: $64.95
  • 1 x Garden Salad: $8.99

  Subtotal: $73.94
```

### 1.7 Remove an Item

```python
result = cart_tool.execute(
    action="remove",
    customer_id=CUSTOMER,
    item_name="Garden Salad",
)
print(result.message)
# Expected: "I've removed that item from your cart."

# Verify
result = cart_tool.execute(action="show", customer_id=CUSTOMER)
print(result.message)
# Expected: Only Pizza Margherita remains
```

### 1.8 Non-Existent Item

```python
result = cart_tool.execute(
    action="add",
    customer_id=CUSTOMER,
    item_name="Dragon Fruit Delight",  # doesn't exist
    quantity=1,
)
print(result.message)
# Expected: "We don't have 'Dragon Fruit Delight' on our menu."
# If alternates are found, they'll be shown
```

### 1.9 Checkout — Missing Fields (Shows Summary)

```python
result = checkout_tool.execute(
    customer_id=CUSTOMER,
    delivery_method="pickup",
    payment_method="cash",
)
print(result.message)
```

**Expected output:**
```
🧾 **Order Summary**

Items:
  • 5 x Pizza Margherita: $64.95

Subtotal: $64.95
Tax: $5.36
**Total: $70.31**

Delivery: Pickup
Payment: Cash

Shall I place this order? (Reply 'yes' to confirm)
```

### 1.10 Checkout — Delivery Requires Address

```python
result = checkout_tool.execute(
    customer_id=CUSTOMER,
    delivery_method="delivery",
    payment_method="card",
)
print(result.message)
# Expected: includes "delivery_address" in the output, asking for the address
```

### 1.11 Checkout — Complete Order

```python
result = checkout_tool.execute(
    customer_id=CUSTOMER,
    customer_name="Manual Test",
    email="test@example.com",
    phone="+1234567890",
    delivery_method="pickup",
    payment_method="cash",
    confirmed=True,
)
print(result.message)
```

**Expected output:**
```
✅ **Order placed!** Order #1 has been submitted.

Total: $70.31
Delivery: Pickup
Payment: Cash

Your order has been sent to the kitchen. A confirmation email has been sent.
```

### 1.12 Verify Cart is Converted

```python
# The cart should now be converted
result = cart_tool.execute(action="show", customer_id=CUSTOMER)
print(result.message)
# Expected: "Your cart is empty."

# Verify the order exists
from orders.models import Order
order = Order.objects.last()
print(f"Order #{order.id}: status={order.status}, total=${float(order.total):.2f}")
if order.items.exists():
    for item in order.items.all():
        print(f"  - {item.quantity} x {item.item_name}: ${float(item.price):.2f}")
```

### 1.13 Test Full Delivery Flow

Run this as a single block to test the complete delivery flow:

```python
CUSTOMER = "test-delivery-flow"

# Add item
cart_tool.execute(action="add", customer_id=CUSTOMER, item_name="Pizza Margherita", quantity=2)

# Checkout with delivery
result = checkout_tool.execute(
    customer_id=CUSTOMER,
    customer_name="Delivery Test",
    email="delivery@test.com",
    delivery_method="delivery",
    delivery_address="123 Main Street, Addis Ababa",
    payment_method="card",
    confirmed=True,
)
print(result.message)
# Expected: Order with delivery address and fee
```

---

## Method 2: REST API (Authenticated, Per-Customer)

Use the REST API to test the underlying cart endpoints. Requires JWT auth.

### 2.1 Set Token

```bash
TOKEN="<your-jwt-token-from-prerequisites>"
```

### 2.2 Get or Create Active Cart

```bash
curl -s -X POST http://localhost:8000/api/v1/cart/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | python -m json.tool
```

### 2.3 View Active Cart

```bash
curl -s http://localhost:8000/api/v1/cart/active/ \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

### 2.4 Add Item to Cart

Find a menu item ID first:

```bash
curl -s http://localhost:8000/api/v1/menu/ \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

Then add it:

```bash
curl -s -X POST http://localhost:8000/api/v1/cart/add_item/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"menu_item_id": 1, "quantity": 2}' | python -m json.tool
```

### 2.5 Update Item Quantity

First get the cart ID from the previous response, then:

```bash
curl -s -X PATCH http://localhost:8000/api/v1/cart/1/update_item/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"menu_item_id": 1, "quantity": 5}' | python -m json.tool
```

### 2.6 Remove Item from Cart

```bash
curl -s -X POST http://localhost:8000/api/v1/cart/1/remove_item/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"menu_item_id": 1}' | python -m json.tool
```

### 2.7 Clear Cart

```bash
curl -s -X POST http://localhost:8000/api/v1/cart/1/clear/ \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

### 2.8 Checkout Cart

```bash
curl -s -X POST http://localhost:8000/api/v1/cart/1/checkout/ \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

---

## Method 3: Chat API (Full End-to-End)

Test the complete conversational flow through the agent's chat endpoint.

### 3.1 Create a Session and Send Messages

```bash
TOKEN="<your-jwt-token>"
BASE="http://localhost:8000/api/v1/agent"
```

**Turn 1 — Browse the menu:**
```bash
curl -s -X POST $BASE/chat/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is on the menu?"}' | python -m json.tool
```

Save the `session_id` from the response.

**Turn 2 — Order items (planner routes to manage_cart):**
```bash
curl -s -X POST $BASE/chat/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "I want Pizza Margherita", "session_id": "<session-id>"}' | python -m json.tool
```

**Turn 3 — Specify quantity:**
```bash
curl -s -X POST $BASE/chat/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "2", "session_id": "<session-id>"}' | python -m json.tool
```

**Turn 4 — Choose delivery method:**
```bash
curl -s -X POST $BASE/chat/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "pickup", "session_id": "<session-id>"}' | python -m json.tool
```

**Turn 5 — Choose payment:**
```bash
curl -s -X POST $BASE/chat/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "cash", "session_id": "<session-id>"}' | python -m json.tool
```

**Turn 6 — Confirm order:**
```bash
curl -s -X POST $BASE/chat/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "yes confirm", "session_id": "<session-id>"}' | python -m json.tool
```

**Expected final response:** Order created with ID, total, and confirmation message.

### 3.2 Verify via Session History

```bash
curl -s $BASE/sessions/<session-id>/ \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

---

## Test Scenarios Checklist

| Scenario | Method | Steps | Expected Result |
|----------|--------|-------|----------------|
| **Add item** | Shell | `cart_tool.execute(action="add", ...)` | Success, cart has 1 item |
| **Add same item twice** | Shell | Add qty=1, then add qty=3 | Merged quantity: 4 |
| **Add non-existent** | Shell | `item_name="Does Not Exist"` | Error with alternatives |
| **Show cart** | Shell | `action="show"` | Lists all items and subtotal |
| **Remove item** | Shell | `action="remove"` + `item_name` | Item removed |
| **Show empty cart** | Shell | Show after removal | "empty" message |
| **Checkout — missing fields** | Shell | No delivery_method | Asks for pickup/delivery |
| **Checkout — pickup** | Shell | delivery_method="pickup", confirmed=True | Order created, cart converted |
| **Checkout — delivery** | Shell | delivery_method="delivery", with address, confirmed=True | Order with delivery fee |
| **Checkout — no confirmation** | Shell | All fields, no `confirmed=True` | Shows summary, awaiting_confirmation |
| **Full API flow** | REST | Create cart → Add item → Update → Remove → Checkout | All operations succeed |
| **Full chat flow** | Chat API | Browse → Order → Quantity → Delivery → Payment → Confirm | Order created end-to-end |

---

## Common Issues & Troubleshooting

| Issue | Likely Cause | Fix |
|-------|-------------|-----|
| `Tool 'checkout_cart' not available` | Planner not routing correctly | Check that `controller.py` includes `CheckoutCartTool()` in `_build_tools()` |
| `CartServiceError: Menu item #1 not found` | Menu not seeded | Run `python manage.py seed_menu` |
| Item name not found | Name mismatch | Use `menu_tool.execute()` first to see exact names |
| "You don't have an active cart" | Cart was already converted | Use a new `customer_id` |
| `OrderService` import error | Order model schema mismatch | Run `python manage.py migrate orders` |
| Stale cart data | Django prefetch cache | The fix in `get_cart_summary` uses `CartItem.objects.filter(cart=cart)` — verify service layer is using this |
