from decimal import Decimal

from django.core.management.base import BaseCommand

from menu.models import MenuItem


MENU_ITEMS = [
    # --- Wot (Stews) ---
    {
        "name": "Doro Wat",
        "description": "Spicy chicken stew slow-cooked with berbere spice, caramelized onions, and hard-boiled eggs. Served with injera.",
        "price": Decimal("18.00"),
        "category": "Wot (Stews)",
        "vegetarian": False,
        "vegan": False,
        "spicy": True,
        "allergens": "eggs",
    },
    {
        "name": "Siga Wat",
        "description": "Rich and spicy beef stew simmered with berbere, garlic, ginger, and onions. A classic Ethiopian favorite.",
        "price": Decimal("19.00"),
        "category": "Wot (Stews)",
        "vegetarian": False,
        "vegan": False,
        "spicy": True,
        "allergens": "",
    },
    {
        "name": "Misir Wot",
        "description": "Red lentil stew cooked in berbere sauce with onions, garlic, and ginger. High-protein and naturally vegan.",
        "price": Decimal("12.00"),
        "category": "Wot (Stews)",
        "vegetarian": True,
        "vegan": True,
        "spicy": True,
        "allergens": "",
    },
    {
        "name": "Shiro Wat",
        "description": "Smooth chickpea and lentil stew simmered with garlic, onions, and mild spices. A comforting vegan staple.",
        "price": Decimal("11.00"),
        "category": "Wot (Stews)",
        "vegetarian": True,
        "vegan": True,
        "spicy": False,
        "allergens": "",
    },
    {
        "name": "Atkilt Wat",
        "description": "Mildly spiced cabbage, carrots, and potatoes sautéed with turmeric and garlic. Light and healthy.",
        "price": Decimal("10.00"),
        "category": "Wot (Stews)",
        "vegetarian": True,
        "vegan": True,
        "spicy": False,
        "allergens": "",
    },
    # --- Tibs (Sautéed Meats) ---
    {
        "name": "Tibs",
        "description": "Tender beef or lamb cubes sautéed with onions, jalapeños, rosemary, and niter kibbeh (spiced butter).",
        "price": Decimal("20.00"),
        "category": "Tibs (Sautéed)",
        "vegetarian": False,
        "vegan": False,
        "spicy": False,
        "allergens": "dairy",
    },
    {
        "name": "Awaze Tibs",
        "description": "Spicy sautéed beef in awaze sauce — a bold blend of berbere, mustard, and Ethiopian spices.",
        "price": Decimal("21.00"),
        "category": "Tibs (Sautéed)",
        "vegetarian": False,
        "vegan": False,
        "spicy": True,
        "allergens": "mustard",
    },
    {
        "name": "Chicken Tibs",
        "description": "Grilled chicken breast strips tossed with onions, bell peppers, and mild spices.",
        "price": Decimal("18.00"),
        "category": "Tibs (Sautéed)",
        "vegetarian": False,
        "vegan": False,
        "spicy": False,
        "allergens": "",
    },
    {
        "name": "Firfir",
        "description": "Shredded injera pan-fried with berbere-spiced clarified butter, often served as a hearty breakfast.",
        "price": Decimal("11.00"),
        "category": "Tibs (Sautéed)",
        "vegetarian": True,
        "vegan": False,
        "spicy": True,
        "allergens": "gluten, dairy",
    },
    # --- Kitfo & Specialties ---
    {
        "name": "Kitfo",
        "description": "Finely minced raw beef seasoned with niter kibbeh, mitmita, and cardamom. Served with fresh cheese and greens.",
        "price": Decimal("22.00"),
        "category": "Specialties",
        "vegetarian": False,
        "vegan": False,
        "spicy": True,
        "allergens": "dairy",
    },
    {
        "name": "Kitfo Leb Leb",
        "description": "Lightly cooked version of kitfo — minced beef quickly seared but still rare inside, seasoned with spiced butter.",
        "price": Decimal("22.00"),
        "category": "Specialties",
        "vegetarian": False,
        "vegan": False,
        "spicy": True,
        "allergens": "dairy",
    },
    {
        "name": "Gored Gored",
        "description": "Cubes of raw beef served with mitmita spice blend and awaze dipping sauce. A true Ethiopian carnivore experience.",
        "price": Decimal("23.00"),
        "category": "Specialties",
        "vegetarian": False,
        "vegan": False,
        "spicy": True,
        "allergens": "",
    },
    {
        "name": "Dulet",
        "description": "Finely chopped tripe, liver, and lean beef mixed with mitmita, niter kibbeh, and fresh herbs.",
        "price": Decimal("18.00"),
        "category": "Specialties",
        "vegetarian": False,
        "vegan": False,
        "spicy": True,
        "allergens": "dairy",
    },
    # --- Vegetarian / Vegan Combination ---
    {
        "name": "Vegetarian Combination",
        "description": "A sampler platter of misir wot, shiro wat, atkilt wat, gomen (collard greens), and salad — served on injera.",
        "price": Decimal("15.00"),
        "category": "Vegetarian & Vegan",
        "vegetarian": True,
        "vegan": True,
        "spicy": False,
        "allergens": "gluten",
    },
    {
        "name": "Vegan Delight",
        "description": "A rotating selection of four seasonal vegan wots and fresh salad on injera. Ask your server for today's picks.",
        "price": Decimal("14.00"),
        "category": "Vegetarian & Vegan",
        "vegetarian": True,
        "vegan": True,
        "spicy": False,
        "allergens": "",
    },
    {
        "name": "Gomen",
        "description": "Collard greens slowly cooked with onions, garlic, and jalapeños until tender. Simple and nutritious.",
        "price": Decimal("9.00"),
        "category": "Vegetarian & Vegan",
        "vegetarian": True,
        "vegan": True,
        "spicy": False,
        "allergens": "",
    },
    {
        "name": "Buticha",
        "description": "Ethiopian-style chickpea salad with lemon, onions, green peppers, and mustard — served cold.",
        "price": Decimal("8.00"),
        "category": "Vegetarian & Vegan",
        "vegetarian": True,
        "vegan": True,
        "spicy": False,
        "allergens": "mustard",
    },
    # --- Appetizers & Sides ---
    {
        "name": "Sambusa",
        "description": "Crispy fried pastry triangles stuffed with spiced lentils or minced beef. Served with awaze sauce.",
        "price": Decimal("6.00"),
        "category": "Appetizers & Sides",
        "vegetarian": True,
        "vegan": True,
        "spicy": False,
        "allergens": "gluten",
    },
    {
        "name": "Kicha",
        "description": "Ethiopian flatbread made from wheat flour, lightly grilled, and served with honey and yogurt.",
        "price": Decimal("5.00"),
        "category": "Appetizers & Sides",
        "vegetarian": True,
        "vegan": False,
        "spicy": False,
        "allergens": "gluten, dairy",
    },
    {
        "name": "Injera",
        "description": "Extra injera on the side — our spongy, tangy teff flatbread that serves as the base of any Ethiopian meal.",
        "price": Decimal("3.00"),
        "category": "Appetizers & Sides",
        "vegetarian": True,
        "vegan": True,
        "spicy": False,
        "allergens": "",
    },
    # --- Drinks ---
    {
        "name": "Ethiopian Coffee",
        "description": "Traditional Ethiopian coffee ceremony style — fresh-roasted, hand-ground, and brewed at your table. Served with popcorn.",
        "price": Decimal("5.00"),
        "category": "Drinks",
        "vegetarian": True,
        "vegan": True,
        "spicy": False,
        "allergens": "",
    },
    {
        "name": "Tej",
        "description": "Traditional Ethiopian honey wine — sweet, aromatic, and mildly alcoholic. Served chilled.",
        "price": Decimal("8.00"),
        "category": "Drinks",
        "vegetarian": True,
        "vegan": True,
        "spicy": False,
        "allergens": "",
    },
    {
        "name": "Ethiopian Tea",
        "description": "Black tea brewed with cardamom, cinnamon, and cloves — sweetened to taste.",
        "price": Decimal("3.50"),
        "category": "Drinks",
        "vegetarian": True,
        "vegan": True,
        "spicy": False,
        "allergens": "",
    },
    {
        "name": "T'ella",
        "description": "Traditional Ethiopian barley beer — home-brewed, slightly sour, and refreshing.",
        "price": Decimal("4.50"),
        "category": "Drinks",
        "vegetarian": True,
        "vegan": True,
        "spicy": False,
        "allergens": "gluten",
    },
]


class Command(BaseCommand):
    help = "Seeds the menu with Ethiopian dishes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Clear existing menu items and re-seed",
        )

    def handle(self, *args, **options):
        if options["force"]:
            deleted, _ = MenuItem.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing menu items."))

        if MenuItem.objects.exists():
            self.stdout.write(self.style.WARNING("Menu already seeded. Use --force to re-seed."))
            return

        items = [MenuItem(**item) for item in MENU_ITEMS]
        MenuItem.objects.bulk_create(items)
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(items)} menu items."))
