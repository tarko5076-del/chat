# Restaurant AI Assistant – AI Agent Development Prompt

You are a Senior AI Engineer, Senior Backend Engineer, and AI Agent Architect.

Your task is to build a production-quality **Restaurant AI Assistant** that behaves like an AI agent rather than a simple chatbot.

## Objective

Develop an AI-powered Restaurant Assistant capable of understanding user goals, making decisions, using tools, and completing tasks autonomously.

The assistant should not simply answer questions—it should determine what action is required, execute the appropriate tool, and return the final result.

Examples:

* Recommend menu items.
* Book restaurant reservations.
* Check table availability.
* Modify or cancel reservations.
* Calculate bills.
* Answer restaurant FAQs.
* Maintain conversational context.

---

# Technology Stack

## Backend

* Python 3.11+
* FastAPI
* Pydantic
* SQLAlchemy ORM
* postgressql (initially)
* Uvicorn

## AI

* OpenAI API
* GPT-5.5 (or configurable model)
* Function/Tool Calling

## Frontend

* React + TypeScript
* Vite
* Tailwind CSS

---

# Architecture

Use a modular and scalable architecture.

```
restaurant-ai/

backend/
    app/
        main.py
        config.py
        database.py

        agent/
            controller.py
            planner.py
            prompts.py
            memory.py

        llm/
            client.py

        tools/
            menu.py
            reservation.py
            order.py
            billing.py
            faq.py

        services/
        models/
        schemas/
        api/

frontend/

README.md
```

Keep each module focused on a single responsibility.

---

# AI Agent Workflow

The assistant must follow this workflow:

1. Receive the user's request.
2. Understand the user's intent.
3. Decide whether a tool is needed.
4. Select the appropriate tool.
5. Execute the tool.
6. Analyze the tool result.
7. Continue using additional tools if necessary.
8. Return a natural-language response.

Never skip directly to an answer if a tool is required.

---

# Core Tools

## Menu Tool

Capabilities:

* List menu items
* Search menu
* Recommend meals
* Filter vegetarian
* Filter vegan
* Filter spicy
* Filter by budget

---

## Reservation Tool

Capabilities:

* Check availability
* Create reservation
* Update reservation
* Cancel reservation

---

## Order Tool

Capabilities:

* Create order
* Add item
* Remove item
* Show current order

---

## Billing Tool

Capabilities:

* Calculate subtotal
* Calculate tax
* Calculate total
* Split bill

---

## FAQ Tool

Answer questions about:

* Opening hours
* Address
* Parking
* Delivery
* Wi-Fi
* Payment methods

---

# Memory

The assistant should remember within the current conversation:

* customer name
* reservation details
* selected menu items
* previous questions
* previous orders

Example:

User:
Reserve a table for 4 tomorrow.

Later:

Change it to 6 people.

The assistant should understand what "it" refers to.

---

# Planning

Before executing a task, the assistant should internally create a plan.

Example:

Goal:
Reserve a table.

Plan:

* Check date
* Check time
* Check availability
* Reserve table
* Confirm reservation

The planning process should be internal and not shown to the user.

---

# Coding Standards

Follow these requirements:

* Use Python type hints.
* Keep functions small and reusable.
* Follow SOLID principles.
* Use dependency injection where appropriate.
* Avoid duplicated logic.
* Organize code into services.
* Write clean, maintainable code.
* Handle errors gracefully.
* Validate all user inputs.
* Never hardcode secrets or API keys.

---

# User Experience

The assistant should:

* Be polite and professional.
* Ask follow-up questions when required.
* Explain errors clearly.
* Confirm successful actions.
* Use natural conversational language.

Example:

User:
Book a table.

Assistant:
Certainly! What date, time, and how many guests?

---

# Frontend

Create a clean chat interface featuring:

* Chat history
* User and assistant messages
* Loading indicator
* Auto-scroll
* Responsive layout
* Error handling
* Modern design

---

# Sample Tasks

The assistant should successfully complete scenarios like:

1. Recommend a vegetarian meal under $15.
2. Reserve a table for 5 people tomorrow at 7 PM.
3. Cancel an existing reservation.
4. Show today's menu.
5. Calculate the bill for an order.
6. Answer restaurant FAQs.
7. Update an existing reservation.
8. Maintain conversation context across multiple messages.

---

# Deliverables

Build the project incrementally.

Phase 1:

* Backend setup
* OpenAI integration
* Chat endpoint

Phase 2:

* Tool framework
* Menu tool
* FAQ tool

Phase 3:

* Reservation tool
* Database models

Phase 4:

* Billing tool
* Order tool

Phase 5:

* Conversation memory
* Planner
* Improved responses

Each phase should be fully functional before moving to the next. Generate complete, well-documented code with clear explanations, ensuring the project is ready for demonstration.
