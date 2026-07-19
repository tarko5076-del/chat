# Generated manually — makes KnowledgeBase.embedding dimension configurable.
# Dimension value captured at migration-creation time (384 = sentence-transformers/all-MiniLM-L6-v2).
# If you change EMBEDDING_DIMENSIONS in .env, run `python manage.py makemigrations` to generate a new migration.
#
# Modified: uses SeparateDatabaseAndState so SQLite tests don't fail on the IvfflatIndex
# during table rebuild.

from django.conf import settings
from django.db import migrations
from pgvector.django import VectorField


def _is_pg():
    return "postgresql" in settings.DATABASES["default"]["ENGINE"]


class Migration(migrations.Migration):

    dependencies = [
        ("agent", "0003_agent_session"),
    ]

    if _is_pg():
        # PostgreSQL: alter the column normally
        operations = [
            migrations.AlterField(
                model_name="knowledgebase",
                name="embedding",
                field=VectorField(dimensions=384),
            ),
        ]
    else:
        # SQLite: only update Django's state, skip actual DDL
        # (the VectorField column stores vectors as blobs regardless of dimension)
        operations = [
            migrations.SeparateDatabaseAndState(
                state_operations=[
                    migrations.AlterField(
                        model_name="knowledgebase",
                        name="embedding",
                        field=VectorField(dimensions=384),
                    ),
                ],
                database_operations=[],
            ),
        ]
