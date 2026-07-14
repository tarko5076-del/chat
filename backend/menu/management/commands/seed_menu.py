from decimal import Decimal

from django.core.management.base import BaseCommand

from menu.models import MenuItem


MENU_ITEMS = [
    {
        "name": "Bruschetta",
        "description": "Grilled bread rubbed with garlic and topped with diced tomatoes, fresh basil, and extra virgin olive oil.",
        "price": Decimal("7.50"),
        "category": "Appetizers",
        "vegetarian": True,
        "vegan": True,
        "spicy": False,
        "allergens": "gluten",
    },
    {
        "name": "Calamari Fritti",
        "description": "Lightly battered and fried squid rings served with marinara sauce and lemon wedges.",
        "price": Decimal("12.00"),
        "category": "Appetizers",
        "vegetarian": False,
        "vegan": False,
        "spicy": False,
        "allergens": "gluten, shellfish",
    },
    {
        "name": "Caprese Salad",
        "description": "Sliced fresh mozzarella, ripe tomatoes, and basil drizzled with balsamic glaze.",
        "price": Decimal("9.00"),
        "category": "Appetizers",
        "vegetarian": True,
        "vegan": False,
        "spicy": False,
        "allergens": "dairy",
    },
    {
        "name": "Arancini",
        "description": "Crispy fried risotto balls stuffed with mozzarella and peas, served with arrabbiata sauce.",
        "price": Decimal("10.50"),
        "category": "Appetizers",
        "vegetarian": True,
        "vegan": False,
        "spicy": False,
        "allergens": "gluten, dairy",
    },
    {
        "name": "Spaghetti Carbonara",
        "description": "Classic Roman pasta with crispy pancetta, egg yolk, pecorino romano, and black pepper.",
        "price": Decimal("16.00"),
        "category": "Pasta",
        "vegetarian": False,
        "vegan": False,
        "spicy": False,
        "allergens": "gluten, dairy, eggs",
    },
    {
        "name": "Penne Arrabbiata",
        "description": "Penne tossed in a fiery tomato and garlic sauce with dried chili flakes.",
        "price": Decimal("13.50"),
        "category": "Pasta",
        "vegetarian": True,
        "vegan": True,
        "spicy": True,
        "allergens": "gluten",
    },
    {
        "name": "Fettuccine Alfredo",
        "description": "Silky fettuccine tossed in a rich butter and parmesan cream sauce.",
        "price": Decimal("15.00"),
        "category": "Pasta",
        "vegetarian": True,
        "vegan": False,
        "spicy": False,
        "allergens": "gluten, dairy",
    },
    {
        "name": "Rigatoni Bolognese",
        "description": "Rigatoni served with a slow-simmered ragu of beef, pork, tomatoes, and aromatic vegetables.",
        "price": Decimal("17.00"),
        "category": "Pasta",
        "vegetarian": False,
        "vegan": False,
        "spicy": False,
        "allergens": "gluten, dairy",
    },
    {
        "name": "Margherita Pizza",
        "description": "San Marzano tomato sauce, fresh mozzarella, and basil on a thin, crispy crust.",
        "price": Decimal("14.00"),
        "category": "Pizza",
        "vegetarian": True,
        "vegan": False,
        "spicy": False,
        "allergens": "gluten, dairy",
    },
    {
        "name": "Quattro Formaggi Pizza",
        "description": "A blend of mozzarella, gorgonzola, fontina, and parmesan on a white base with honey drizzle.",
        "price": Decimal("16.50"),
        "category": "Pizza",
        "vegetarian": True,
        "vegan": False,
        "spicy": False,
        "allergens": "gluten, dairy",
    },
    {
        "name": "Diavola Pizza",
        "description": "Tomato sauce, mozzarella, spicy salami, and roasted chili oil.",
        "price": Decimal("15.50"),
        "category": "Pizza",
        "vegetarian": False,
        "vegan": False,
        "spicy": True,
        "allergens": "gluten, dairy",
    },
    {
        "name": "Chicken Parmigiana",
        "description": "Breaded chicken breast topped with marinara sauce and melted mozzarella, served with spaghetti.",
        "price": Decimal("18.00"),
        "category": "Main Courses",
        "vegetarian": False,
        "vegan": False,
        "spicy": False,
        "allergens": "gluten, dairy, eggs",
    },
    {
        "name": "Osso Buco",
        "description": "Braised veal shanks in white wine, broth, and vegetables, served over saffron risotto.",
        "price": Decimal("24.00"),
        "category": "Main Courses",
        "vegetarian": False,
        "vegan": False,
        "spicy": False,
        "allergens": "dairy, celery",
    },
    {
        "name": "Eggplant Parmigiana",
        "description": "Layers of breaded eggplant, marinara sauce, mozzarella, and parmesan, baked until golden.",
        "price": Decimal("15.00"),
        "category": "Main Courses",
        "vegetarian": True,
        "vegan": False,
        "spicy": False,
        "allergens": "gluten, dairy, eggs",
    },
    {
        "name": "Tiramisu",
        "description": "Classic Italian dessert of espresso-soaked ladyfingers layered with mascarpone cream and cocoa.",
        "price": Decimal("9.00"),
        "category": "Desserts",
        "vegetarian": True,
        "vegan": False,
        "spicy": False,
        "allergens": "gluten, dairy, eggs",
    },
]


class Command(BaseCommand):
    help = "Seeds the menu with Italian dishes if the table is empty."

    def handle(self, *args, **options):
        if MenuItem.objects.exists():
            self.stdout.write(self.style.WARNING("Menu already seeded. Skipping."))
            return

        items = [MenuItem(**item) for item in MENU_ITEMS]
        MenuItem.objects.bulk_create(items)
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(items)} menu items."))
