from django.core.management.base import BaseCommand

from agent.embeddings import get_embeddings
from agent.models import KnowledgeBase
from menu.models import MenuItem


POLICIES = [
    {
        "title": "Opening Hours",
        "content": "We are open Monday through Sunday, 11:00 AM to 10:00 PM. Kitchen closes at 9:30 PM. Last seating is at 9:00 PM.",
    },
    {
        "title": "Dress Code",
        "content": "Smart casual attire is required. No sandals, tank tops, or offensive clothing. Business casual recommended for dinner service.",
    },
    {
        "title": "Cancellation Policy",
        "content": "Reservations can be cancelled up to 2 hours before the scheduled time at no charge. Late cancellations or no-shows may incur a fee of $15 per person.",
    },
    {
        "title": "Reservation Hold Policy",
        "content": "Tables are held for 15 minutes past the reservation time. After 15 minutes, the hold is released and the table may be given to walk-in guests.",
    },
    {
        "title": "Allergen Information",
        "content": "We take allergies seriously. Please inform your server of any allergies before ordering. Our kitchen handles nuts, dairy, gluten, shellfish, and soy. Cross-contamination is possible despite our best efforts.",
    },
    {
        "title": "Party Size Policy",
        "content": "We accommodate parties of 1 to 12 guests. For parties larger than 8, please call ahead to arrange a custom menu or private dining area.",
    },
    {
        "title": "Delivery Policy",
        "content": "Delivery is available within a 5-mile radius. A $4.99 delivery fee applies. Delivery orders typically take 45-60 minutes. Minimum order for delivery is $20.",
    },
    {
        "title": "Payment Methods",
        "content": "We accept card payments (Visa, Mastercard, Amex) and mobile money. Cash is not accepted. Mobile money payments can be sent to our company number.",
    },
    {
        "title": "Kids Menu",
        "content": "Children under 12 eat free on Sundays with the purchase of an adult entrée. We offer a dedicated kids menu with smaller portions and milder flavors.",
    },
    {
        "title": "Happy Hour",
        "content": "Happy hour is every weekday from 3:00 PM to 6:00 PM. All appetizers are 25% off. Drink specials include half-price house wine and discounted cocktails.",
    },
]

FAQS = [
    {
        "title": "Do you have vegetarian options?",
        "content": "Yes! We have a wide variety of vegetarian dishes including Shiro (chickpea stew), Misir Wot (red lentil stew), Gomen (collard greens), and several vegetarian combination plates. Ask your server for today's specials.",
    },
    {
        "title": "Do you have gluten-free options?",
        "content": "Many of our dishes are naturally gluten-free since injera (our traditional bread) is made from teff flour, which is gluten-free. However, some dishes contain wheat. Please ask your server about specific allergens.",
    },
    {
        "title": "Is the food spicy?",
        "content": "Ethiopian cuisine features various spice levels. Mild options include Doro Wat (chicken stew) and Tibs. Medium spice includes Kitfo and Misir Wot. For authentic heat, try our Awaze Tibs. We can adjust spice levels on request.",
    },
    {
        "title": "What is injera?",
        "content": "Injera is a spongy, sourdough flatbread made from teff flour. It serves as both plate and utensil in Ethiopian dining. Tear off pieces and use them to scoop up stews and vegetables.",
    },
    {
        "title": "Do you offer catering?",
        "content": "Yes, we offer full catering services for events of 10-200 guests. Contact us at least 48 hours in advance. We provide traditional family-style service with platters for the table.",
    },
    {
        "title": "Can I make a reservation?",
        "content": "Absolutely! You can make a reservation through our chat, by calling us, or visiting our website. Reservations are recommended for parties of 4 or more, especially on weekends.",
    },
    {
        "title": "Do you have parking?",
        "content": "Yes, we have a free parking lot with 50 spaces. Street parking is also available. Valet parking is offered on Friday and Saturday evenings.",
    },
    {
        "title": "What is the average meal cost?",
        "content": "Lunch averages $12-18 per person. Dinner averages $20-35 per person. Our combination platters offer great value, feeding 2-3 people for $35-50.",
    },
]

PROMOTIONS = [
    {
        "title": "Sunday Family Special",
        "content": "Every Sunday, kids under 12 eat free with purchase of an adult entrée. Family combination platters feed 4 for just $55 (regular $70).",
    },
    {
        "title": "Happy Hour Deals",
        "content": "Weekdays 3-6 PM: 25% off all appetizers, half-price house wine, and $5 cocktails. Perfect for after-work gatherings.",
    },
    {
        "title": "Lunch Express",
        "content": "Weekday lunch specials: any injera wrap + drink for $12. Available 11 AM - 2 PM. Quick service guaranteed or your meal is free.",
    },
    {
        "title": "Catering Discount",
        "content": "Book catering for 50+ guests and receive 15% off your total. Includes setup, service staff, and traditional coffee ceremony.",
    },
]


class Command(BaseCommand):
    help = "Seed knowledge base with menu items, policies, FAQs, and promotions"

    def handle(self, *args, **options):
        self._seed()

    def _seed(self):
        self.stdout.write("Seeding knowledge base...")

        items = []

        # Menu items from DB
        for menu_item in MenuItem.objects.all():
            items.append(
                {
                    "content_type": "menu_item",
                    "title": menu_item.name,
                    "content": (
                        f"{menu_item.name} - ${float(menu_item.price):.2f}\n"
                        f"{menu_item.description}\n"
                        f"Category: {menu_item.category}\n"
                        f"Available: {'Yes' if menu_item.is_available else 'No'}"
                    ),
                    "metadata": {
                        "price": float(menu_item.price),
                        "category": menu_item.category,
                        "is_available": menu_item.is_available,
                    },
                }
            )

        # Policies
        for p in POLICIES:
            items.append({"content_type": "policy", "title": p["title"], "content": p["content"], "metadata": {}})

        # FAQs
        for f in FAQS:
            items.append({"content_type": "faq", "title": f["title"], "content": f["content"], "metadata": {}})

        # Promotions
        for p in PROMOTIONS:
            items.append({"content_type": "promotion", "title": p["title"], "content": p["content"], "metadata": {}})

        self.stdout.write(f"  Found {len(items)} items to embed")

        # Get embeddings in batches
        texts = [f"{item['title']}: {item['content']}" for item in items]
        batch_size = 20
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            self.stdout.write(f"  Embedding batch {i // batch_size + 1}...")
            embeddings = get_embeddings(batch)
            all_embeddings.extend(embeddings)

        # Clear existing and insert
        KnowledgeBase.objects.all().delete()
        knowledge_objects = []
        for item, embedding in zip(items, all_embeddings):
            knowledge_objects.append(
                KnowledgeBase(
                    content_type=item["content_type"],
                    title=item["title"],
                    content=item["content"],
                    metadata=item["metadata"],
                    embedding=embedding,
                )
            )
        KnowledgeBase.objects.bulk_create(knowledge_objects)

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {len(knowledge_objects)} knowledge items"))