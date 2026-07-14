from django.db import models


class MenuItem(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=100)
    vegetarian = models.BooleanField(default=False)
    vegan = models.BooleanField(default=False)
    spicy = models.BooleanField(default=False)
    available = models.BooleanField(default=True)
    allergens = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "price": float(self.price),
            "vegetarian": self.vegetarian,
            "vegan": self.vegan,
            "spicy": self.spicy,
        }
