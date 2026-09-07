# x-django-paranoid

Soft-delete for Django that actually works in real projects.

You get `delete()` that doesn't really delete — it just hides the row — plus the fixes that production apps hit within the first month: unique fields, restoring, related objects, admin, and cleanup.

```bash
pip install x-django-paranoid
```

```python
from x_paranoid.models import XParanoidModel

class Article(XParanoidModel):
    slug = models.SlugField(max_length=80)
    title = models.CharField(max_length=200)
```

That's it. `Article.objects` now hides deleted rows. `Article.objects_with_deleted` shows everything. `article.delete()` is reversible.

---

## Why you need soft-delete

Vanilla `Model.delete()` is permanent. In real apps you almost always regret it:

* A customer deletes their account by mistake and support needs to restore it.
* An admin deletes a product that has orders attached — you lose history.
* A user creates a blog post with slug `hello`, deletes it, then can't re-create `hello` because the old row still blocks `unique=True`.
* You delete an author and all their books disappear forever, even the ones that were already deleted separately.

`x-django-paranoid` makes `delete()` reversible and makes those edge cases predictable.

## When to use it

**Pick `x-django-paranoid` if you:**

* **Run a SaaS / marketplace / multi-tenant app** — users, shops, listings get deleted all the time. You need to let them re-create the same `slug`, `username`, or `sku` after deletion, and let support restore without creating duplicates.
* **Keep an audit trail** — orders, invoices, comments, or logs should never be hard-deleted. Soft-delete keeps them for reports while hiding them from the app.
* **Need a trash bin** — admins want to see "Active / Deleted / All", restore one click, and auto-purge old trash after 30/90 days.
* **Build an API with DRF** — `DELETE /articles/1/` should soft-delete, `POST /articles/1/restore/` should restore, and creating a new `slug` after a delete should not fail validation.
* **Don't want to think about related data** — deleting an author should soft-delete their books, but restoring the author should not resurrect a book that was already deleted before the author.

If you just need a simple `is_active` flag and will never restore, you don't need this. If you need soft-delete with any of the above, you do.

---

## Installation

```bash
pip install x-django-paranoid
# for API features
pip install djangorestframework
```

```python
# settings.py
INSTALLED_APPS = [
    "x_paranoid",
    # ...
]
```

No other setup. It works on SQLite and Postgres, Django 3.2+.

---

## 60-second quickstart

```python
from x_paranoid.models import XParanoidModel
from x_paranoid.constraints import ParanoidUniqueConstraint

class Article(XParanoidModel):
    slug = models.SlugField(max_length=80)
    title = models.CharField(max_length=200)

    class Meta:
        constraints = [
            ParanoidUniqueConstraint(fields=["slug"], name="uniq_slug_active")
        ]

# create
a = Article.objects.create(slug="hello", title="Hello")

# soft-delete — row stays in DB, just hidden
a.delete()
Article.objects.count()              # 0
Article.objects_with_deleted.count() # 1
Article.objects_with_deleted.get(id=a.id).deleted_at  # 2025-...

# restore
a = Article.objects_with_deleted.get(id=a.id)
a.restore()
Article.objects.count()              # 1 again

# really delete when you mean it
a.hard_delete()
```

Two managers you will use every day:

* `Article.objects` — only alive rows (what your app sees).
* `Article.objects_with_deleted` — everything, including trash. Use it in admin, scripts, and when you need to restore.

It also works in bulk:

```python
Article.objects.filter(author=user).delete()              # soft
Article.objects_with_deleted.filter(author=user).restore() # restore
Article.objects.filter(slug="old").hard_delete()           # hard
```

---

## Common patterns

### 1. Re-using a unique value after delete

**Problem:** `slug=hello` is `unique=True`. You delete it, then try to create a new `hello` → `IntegrityError` because the old row still exists.

**Fix:** Use `ParanoidUniqueConstraint`. It creates a partial index `WHERE deleted_at IS NULL`, so uniqueness only applies to alive rows.

```python
class Article(XParanoidModel):
    slug = models.SlugField()
    class Meta:
        constraints = [ParanoidUniqueConstraint(fields=["slug"], name="uniq_slug")]
```

Now you can delete `hello` and create a new `hello`. Two `hello` rows can exist at the same time, but only one can be alive.

For tenant-scoped uniqueness:

```python
ParanoidUniqueConstraint(fields=["slug"], condition=Q(tenant_id=1), name="uniq_slug_tenant")
```

### 2. What happens when restore would create a duplicate?

You deleted `hello`, someone created a new `hello`, now you restore the old one — which `hello` wins?

Pick a policy per model:

```python
class Article(XParanoidModel):
    slug = models.SlugField()
    class XParanoidMeta:
        on_restore_conflict = "RAISE_ERROR"      # default — raise, let you handle it
        # "FORK_RENAME"     — rename old to "hello-restored-42" and restore
        # "OVERWRITE_ACTIVE" — delete the new one, restore the old
        rename_template = "{value}-restored-{id}"
```

### 3. Deleting a parent and its children

```python
author = Author.objects.create(name="Asimov")
book1 = Book.objects.create(title="Foundation", author=author)
book2 = Book.objects.create(title="I Robot", author=author)

book2.delete()   # deleted separately, before the author
author.delete()  # soft-deletes author + only book1 (same batch)
author.restore() # restores author + book1, book2 stays deleted
```

We stamp a `deletion_batch_id` (UUID) on every row deleted together. Restoring only brings back rows from that same batch. Other soft-deleted rows are left alone — this is the bug that plain `django-safedelete` gets wrong.

For deep trees (`Author → Article → Comment`) it recurses automatically — same batch flows to grandchildren.

### 4. Safe foreign keys

```python
from x_paranoid.fields import XParanoidForeignKey

class Book(XParanoidModel):
    author = XParanoidForeignKey(Author, on_delete=models.CASCADE, null=True)
```

Now `book.author` after the author is soft-deleted returns `None` instead of a ghost object. Add `raise_on_deleted=True` if you prefer an exception (`ObjectSoftDeleted`) instead of `None`.

### 5. Many-to-many that keeps history

Plain `ManyToManyField` hard-deletes the junction row on `.remove()`. To keep history:

```python
class Category(XParanoidModel):
    name = models.CharField(max_length=50)

class BookCategory(XParanoidModel):
    book = models.ForeignKey(Book2, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

class Book2(XParanoidModel):
    title = models.CharField(max_length=50)
    categories = models.ManyToManyField(Category, through=BookCategory)

# don't use .add/.remove
BookCategory.objects.create(book=book, category=cat)
BookCategory.objects.filter(book=book, category=cat).delete()  # soft
```

The `XParanoidManyToManyField` marker will warn you (`W001`) if your `through` model doesn't inherit `XParanoidModel`.

---

## Admin trash bin

```python
# admin.py
from x_paranoid.admin import XParanoidAdmin
admin.site.register(Article, XParanoidAdmin)
```

You get:

* Filters: **Active / Soft Deleted / All**
* A **Deleted** badge in the list
* A bulk action **Restore selected**

Under the hood it uses `objects_with_deleted` so you actually see the trash.

## API (Django REST Framework)

**Serializer** — so creating `hello` after a soft-delete doesn't fail validation:

```python
from x_paranoid.serializers import XParanoidSerializerMixin

class ArticleSerializer(XParanoidSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ["id", "slug", "title"]
```

**ViewSet** — trash-bin endpoints out of the box:

```python
from x_paranoid.drf import SoftDeleteModelMixin, RestoreModelMixin, DeletedListModelMixin

class ArticleViewSet(SoftDeleteModelMixin, RestoreModelMixin, DeletedListModelMixin, viewsets.ModelViewSet):
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer
```

* `DELETE /articles/1/` → soft-delete
* `DELETE /articles/1/?hard=true` → hard-delete
* `POST /articles/1/restore/` → restore
* `GET /articles/deleted/` → list trash

## Automatic cleanup

Keep trash from growing forever:

```python
class Article(XParanoidModel):
    class XParanoidMeta:
        auto_hard_delete_after = timedelta(days=90)
```

```bash
# dry run
python manage.py purge_soft_deleted --dry-run

# actually hard-delete rows soft-deleted >90 days ago (or 30 days if you pass --days)
python manage.py purge_soft_deleted
python manage.py purge_soft_deleted --days 30

# add to cron / celery beat
```

---

## Migrating from `django-paranoid`

```python
# before
from django_paranoid.models import ParanoidModel
# after
from x_paranoid.models import XParanoidModel
```

1. Find `unique=True` that will be soft-deleted → replace with `ParanoidUniqueConstraint`.
2. Add `XParanoidMeta` only where you need custom restore or TTL.
3. Add `XParanoidSerializerMixin` to serializers that hit `unique` errors.
4. `python manage.py makemigrations && python manage.py migrate`

---

## How it compares

* **vs `django-paranoid`:** keeps the same `delete()/restore()` idea but fixes `filter().delete()` hard-delete, `unique` after delete, restore collisions, cascade batch, DRF/Admin/TTL. Use `XParanoidModel` only (no `ParanoidModel` alias).
* **vs `django-safedelete`:** `safedelete` has more policies (`HARD_DELETE`, `NO_DELETE`) and a bigger test suite, but its `SOFT_DELETE_CASCADE` restores *all* children; `x-django-paranoid` restores only the batch that was deleted together. Simpler, partial-index first.

For full trade-offs and edge cases (deep cascade, `XParanoidMeta` inheritance, auto M2M) see `PROject.md`.

---

## Development

```bash
python manage.py test tests --verbosity=2
python manage.py check
python -m build && twine check dist/*
```

Requires Python 3.9+, Django 3.2+. Partial indexes need Postgres 9.5+ or SQLite 3.8+.

## License

MIT — preserves original `django-paranoid` MIT (Carlos Ganoza). See `LICENSE`.
