from x_paranoid.constraints import ParanoidUniqueConstraint
from x_paranoid.models import XParanoidModel
from x_paranoid.fields import XParanoidForeignKey
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
    author = XParanoidForeignKey(Author, on_delete=models.CASCADE, related_name="books", null=True)

# 6.2 XParanoidMeta inheritance demo
class Base(XParanoidModel):
    class XParanoidMeta:
        on_restore_conflict = "FORK_RENAME"

    class Meta:
        abstract = True


class Child(Base):
    pass


# 6.3 M2M through soft-delete demo
class Category(XParanoidModel):
    name = models.CharField(max_length=50)


class BookCategory(XParanoidModel):
    book = models.ForeignKey("Book2", on_delete=models.CASCADE, related_name="book_categories")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="category_books")

    class Meta:
        constraints = [ParanoidUniqueConstraint(fields=["book", "category"], name="uniq_book_cat")]


class Book2(XParanoidModel):
    title = models.CharField(max_length=50)
    categories = models.ManyToManyField(Category, through=BookCategory, related_name="books2")
