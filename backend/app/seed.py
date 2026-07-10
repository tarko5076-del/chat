from sqlalchemy import inspect, text

from app.database import SessionLocal, engine
from app.models import Base, MenuItem


def seed_menu():
    Base.metadata.create_all(engine)
    ensure_conversation_columns()
    ensure_order_columns()
    db = SessionLocal()
    try:
        if db.query(MenuItem).count() > 0:
            return

        items = [
            MenuItem(name="Bruschetta", description="Toasted bread with tomatoes, basil, and olive oil", price=8.99, category="appetizer", vegetarian=True, vegan=True),
            MenuItem(name="Calamari", description="Crispy fried squid with marinara sauce", price=10.99, category="appetizer"),
            MenuItem(name="Garlic Bread", description="Warm bread with garlic butter and herbs", price=5.99, category="appetizer", vegetarian=True),
            MenuItem(name="Spaghetti Carbonara", description="Classic carbonara with pancetta and parmesan", price=14.99, category="main"),
            MenuItem(name="Margherita Pizza", description="Tomato, mozzarella, and fresh basil", price=12.99, category="main", vegetarian=True),
            MenuItem(name="Grilled Salmon", description="Atlantic salmon with lemon butter sauce", price=18.99, category="main"),
            MenuItem(name="Vegetable Risotto", description="Creamy risotto with seasonal vegetables", price=13.99, category="main", vegetarian=True, vegan=True),
            MenuItem(name="Chicken Parmigiana", description="Breaded chicken with marinara and melted cheese", price=15.99, category="main"),
            MenuItem(name="Spicy Arrabbiata", description="Penne in spicy tomato sauce with chili", price=12.99, category="main", vegetarian=True, spicy=True),
            MenuItem(name="Tiramisu", description="Classic Italian coffee dessert", price=7.99, category="dessert", vegetarian=True),
            MenuItem(name="Gelato", description="Creamy vanilla bean gelato", price=5.99, category="dessert", vegetarian=True),
            MenuItem(name="Chocolate Lava Cake", description="Warm chocolate cake with molten center", price=8.99, category="dessert", vegetarian=True),
            MenuItem(name="Lemonade", description="Fresh squeezed lemonade", price=3.99, category="drink", vegetarian=True, vegan=True),
            MenuItem(name="Espresso", description="Double shot espresso", price=2.99, category="drink", vegetarian=True, vegan=True),
            MenuItem(name="Red Wine", description="Glass of house red wine", price=7.99, category="drink", vegetarian=True, vegan=True),
        ]
        db.add_all(items)
        db.commit()
    finally:
        db.close()


def ensure_conversation_columns() -> None:
    inspector = inspect(engine)
    if "conversations" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("conversations")}
    columns = {
        "customer_id": "VARCHAR(64)",
        "order_state": "TEXT",
        "order_status": "VARCHAR(40)",
        "payment_method": "VARCHAR(40)",
        "payment_status": "VARCHAR(40)",
        "payment_id": "VARCHAR(80)",
    }
    with engine.begin() as connection:
        for name, column_type in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE conversations ADD COLUMN {name} {column_type}"))


def ensure_order_columns() -> None:
    inspector = inspect(engine)
    if "orders" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("orders")}
    columns = {
        "customer_id": "VARCHAR(64)",
        "email": "VARCHAR(120)",
        "phone": "VARCHAR(30)",
        "delivery_method": "VARCHAR(20)",
        "delivery_address": "VARCHAR(255)",
        "payment_method": "VARCHAR(40)",
    }
    with engine.begin() as connection:
        for name, column_type in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE orders ADD COLUMN {name} {column_type}"))


if __name__ == "__main__":
    seed_menu()
