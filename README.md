# x-django-paranoid

**Production-grade soft-delete for Django** — an improved, actively maintained version of [`django-paranoid`] and ['safe_delete']

`django-paranoid` gives you `deleted_at` + `objects` filtering. `x-django-paranoid` keeps that API but fixes the 5 things that break in production: **unique constraints, restore collisions, cascade tracing, admin trash-bin, and TTL garbage collection**.

> `pip install x-django-paranoid` — `from x_paranoid.models import XParanoidModel`.

---

## Why not `django-paranoid` / `django-safedelete`?

| Problem in vanilla | What x-django-paranoid does |
|---|---|
| `unique=True` blocks re-create after soft-delete (DB row still exists) | `ParanoidUniqueConstraint` → partial index `WHERE deleted_at IS NULL` `x_paranoid/constraints.py:4` |
| `filter(...).delete()` hard-deletes (bypasses `Model.delete()`) | `XParanoidQuerySet.delete()` `x_paranoid/models.py:6` soft-deletes via `UPDATE` |
| `restore()` blindly restores all children, even independently deleted ones | `deletion_batch_id` UUID `x_paranoid/models.py:44` — restore only same batch |
| `restore()` crashes on unique collision | `XParanoidMeta.on_restore_conflict` `x_paranoid/models.py:51` (`RAISE_ERROR`/`FORK_RENAME`/`OVERWRITE_ACTIVE`) |
| DRF `UniqueValidator` rejects valid re-create | `XParanoidSerializerMixin` `x_paranoid/serializers.py:4` re-scopes to `objects.all()` (active only) |
| No admin trash-bin, no purge | `XParanoidAdmin` `x_paranoid/admin.py:15` + `manage.py purge_soft_deleted` `x_paranoid/management/commands/purge_soft_deleted.py:6` |

---

## Installation

```bash
pip install x-django-paranoid
# optional DRF
pip install djangorestframework
```

Add to `INSTALLED_APPS`:
```python
INSTALLED_APPS = ["x_paranoid", ...]
```

---

## Quickstart

```python
# models.py
from x_paranoid.models import XParanoidModel
from x_paranoid.constraints import ParanoidUniqueConstraint
from django.db import models

class Article(XParanoidModel):
    slug = models.SlugField(max_length=50)
    title = models.CharField(max_length=200)

    class Meta:
        constraints = [
            ParanoidUniqueConstraint(fields=["slug"], name="uniq_article_slug_active")
        ]

    class XParanoidMeta:
        on_restore_conflict = "FORK_RENAME"  # or RAISE_ERROR / OVERWRITE_ACTIVE
        rename_template = "{value}-restored-{id}"
        auto_hard_delete_after = None  # timedelta(days=90) to auto-purge

# usage
a = Article.objects.create(slug="hello")
a.delete()                          # soft: sets deleted_at, deletion_batch_id
Article.objects.count()             # 0 (hides deleted)
Article.objects_with_deleted.count()# 1
a.restore()                         # clears deleted_at
a.hard_delete()                     # really DELETE FROM
```

**Managers / QuerySet** `x_paranoid/models.py:28`
```python
Article.objects.all()               # active only
Article.objects_with_deleted.all()  # active + deleted
Article.objects_with_deleted.filter(slug="hello").restore()  # bulk restore
Article.objects.filter(slug="hello").delete(hard=True)       # bulk hard delete
Article.objects.filter(slug="hello").hard_delete()
```

---

## Features

### 1. Active-only uniqueness — `ParanoidUniqueConstraint` `x_paranoid/constraints.py:4`

```python
class Meta:
    constraints = [ParanoidUniqueConstraint(fields=["slug"], name="uniq_slug")]
# injects condition=Q(deleted_at__isnull=True) automatically
# SQL: CREATE UNIQUE INDEX ... WHERE deleted_at IS NULL
# Ands with your own Q: ParanoidUniqueConstraint(fields=["slug"], condition=Q(tenant=1))
```

Without it, `unique=True` + soft-delete = `IntegrityError` on re-create. With it, you can delete `slug=hello` and create a new `hello`.

### 2. Restore collision policies `x_paranoid/models.py:98`

When restoring `hello` but an active `hello` exists:

```python
class XParanoidMeta:
    on_restore_conflict = "RAISE_ERROR"      # default: raise IntegrityError
    # "FORK_RENAME": rename to "hello-restored-42"
    # "OVERWRITE_ACTIVE": hard-delete the active row, then restore
    rename_template = "{value}-restored-{id}"  # for FORK_RENAME
```

### 3. Cascade batch tracing `x_paranoid/models.py:56`

```python
author = Author.objects.create(name="Asimov")
Book.objects.create(title="Foundation", author=author)
Book.objects.create(title="I Robot", author=author)  # independently deleted first
author.delete()   # stamps same deletion_batch_id on author + cascade children
author.restore()  # restores only cascade children, leaves independently deleted I Robot deleted
```

FK cascade is `PARANOID_CASCADE` via `XParanoidModel` children; `deletion_batch_id` `x_paranoid/models.py:44` is a UUID set inside `transaction.atomic`.

### 4. DRF support `x_paranoid/serializers.py:4` `x_paranoid/drf.py:5`

**Serializer:**
```python
from rest_framework import serializers
from x_paranoid.serializers import XParanoidSerializerMixin

class ArticleSerializer(XParanoidSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ["id","slug"]
# re-scopes UniqueValidator to model.objects (active) so re-create after soft-delete validates
```

**ViewSet:**
```python
from rest_framework import viewsets
from x_paranoid.drf import SoftDeleteModelMixin, RestoreModelMixin, DeletedListModelMixin

class ArticleViewSet(SoftDeleteModelMixin, RestoreModelMixin, DeletedListModelMixin, viewsets.ModelViewSet):
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer
# DELETE /articles/1/          -> soft delete
# DELETE /articles/1/?hard=true -> hard delete
# POST   /articles/1/restore/  -> restore
# GET    /articles/deleted/    -> trash bin list
```

### 5. Admin `x_paranoid/admin.py:15`

```python
from x_paranoid.admin import XParanoidAdmin
admin.site.register(Article, XParanoidAdmin)
# - get_queryset uses objects_with_deleted (shows trash)
# - list_filter: Active / Soft Deleted / All (SoftDeletedListFilter)
# - list_display badge is_deleted_badge
# - action restore_selected
```

### 6. TTL Garbage Collection `x_paranoid/management/commands/purge_soft_deleted.py:6`

```python
# per-model TTL
class Article(XParanoidModel):
    class XParanoidMeta:
        auto_hard_delete_after = timedelta(days=90)
```
```bash
python manage.py purge_soft_deleted --dry-run        # shows would purge
python manage.py purge_soft_deleted                  # hard-deletes expired
python manage.py purge_soft_deleted --days 30        # override TTL
# hook to cron / celery beat
```

---

## API Reference

| Symbol | File | Purpose |
|---|---|---|
| `XParanoidModel` | `x_paranoid/models.py:40` | Abstract model with `created_at`, `updated_at`, `deleted_at`, `deletion_batch_id` |
| `XParanoidQuerySet` | `x_paranoid/models.py:6` | `delete(hard)`, `hard_delete()`, `restore()`, `deleted()`, `active()` |
| `XParanoidManager` | `x_paranoid/models.py:28` | `objects` (active) |
| `XParanoidManagerWithDeleted` | `x_paranoid/models.py:32` | `objects_with_deleted` (all) |
| `ParanoidUniqueConstraint` | `x_paranoid/constraints.py:4` | Partial unique index helper |
| `XParanoidSerializerMixin` | `x_paranoid/serializers.py:4` | DRF active-only UniqueValidator |
| `XParanoidAdmin` | `x_paranoid/admin.py:15` | Admin trash-bin |
| `SoftDelete/Restore/DeletedListModelMixin` | `x_paranoid/drf.py:5` | DRF viewset actions |
| `purge_soft_deleted` | `x_paranoid/management/commands/purge_soft_deleted.py:6` | TTL purge command |

---

## Migration from `django-paranoid`

```python
# before
from django_paranoid.models import ParanoidModel
# after — use only XParanoidModel
from x_paranoid.models import XParanoidModel
```
1. Replace `unique=True` with `ParanoidUniqueConstraint` where soft-delete applies.
2. Add `XParanoidMeta` if you need restore policies or TTL.
3. Add `XParanoidSerializerMixin` to DRF serializers that had `unique` errors.
4. Run `makemigrations && migrate` — new `deletion_batch_id` field + partial indexes are added.

---

## Development

```bash
python manage.py test tests --verbosity=2
python manage.py purge_soft_deleted --dry-run
python -m build && twine check dist/*
```

**Requirements:** Python ≥3.9, Django ≥3.2 (tested 3.2/4.2/5/6), SQLite/Postgres (partial indexes need PG 9.5+ or SQLite 3.8+).

---

## License

MIT — fork preserves original `django-paranoid` MIT (Carlos Ganoza Plasencia). See `LICENSE`.
