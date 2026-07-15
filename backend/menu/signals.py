import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="menu.MenuItem")
def reembed_menu_item_on_change(sender, instance, created, **kwargs):
    """Re-embed a KnowledgeBase entry when its source MenuItem changes."""
    from agent.embeddings import get_embedding
    from agent.models import KnowledgeBase

    kb_title = f"menu_item:{instance.id}"

    try:
        kb_entry = KnowledgeBase.objects.get(title=kb_title)
    except KnowledgeBase.DoesNotExist:
        return

    content = (
        f"{instance.name}: {instance.description}. "
        f"Ingredients: {instance.ingredients or 'unknown'}. "
        f"Category: {instance.category}. "
        f"Price: ${float(instance.price):.2f}."
    )
    kb_entry.content = content
    kb_entry.metadata["price"] = float(instance.price)
    kb_entry.metadata["category"] = instance.category
    kb_entry.metadata["available"] = instance.available
    kb_entry.is_active = instance.available

    embedding = get_embedding(content)
    if embedding:
        kb_entry.embedding = embedding

    kb_entry.save()
    logger.info("Re-embedded KnowledgeBase entry for menu item %s", instance.id)
