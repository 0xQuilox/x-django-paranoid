from x_paranoid.constraints import ParanoidUniqueConstraint
from x_paranoid.models import XParanoidModel
from django.db import models


class MyModel(XParanoidModel):
    field = models.CharField(max_length=20)


# Phase 1.1 demo: uniqueness scoped to active rows only
class Article(XParanoidModel):
    slug = models.SlugField(max_length=50)

    class Meta:
        constraints = [
            ParanoidUniqueConstraint(fields=["slug"], name="uniq_article_slug_active")
        ]


# Phase 2 demo: cascade tracking
class Author(XParanoidModel):
    name = models.CharField(max_length=50)

class Book(XParanoidModel):
    title = models.CharField(max_length=50)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
