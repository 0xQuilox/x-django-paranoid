"""x-django-paranoid: production-grade soft-delete.

This is the Step 0 foundation - fixes the critical bulk QuerySet bug
that the original django-paranoid left unhandled.

Learning focus: Manager vs QuerySet layer, why Model.delete() is not
called on bulk ops, and how from_queryset wires them.
"""

from django.db import models
from django.utils.timezone import now


# ---------------------------------------------------------------------------
# QuerySet - the layer that actually handles bulk operations
# ---------------------------------------------------------------------------
class XParanoidQuerySet(models.QuerySet):
    """Adds soft-delete semantics to QuerySet operations.

    Why this exists (the bug it fixes):
      Original code only overrode Model.delete(). But doing
      MyModel.objects.filter(...).delete() calls QuerySet.delete(),
      which bypasses Model.delete() and hard-deletes rows. This
      QuerySet intercepts that path.
    """

    def delete(self, hard=False):
        """Soft-delete by default; pass hard=True to really delete."""
        if hard:
            return super().delete()
        return self.update(deleted_at=now())

    def hard_delete(self):
        """Unconditionally hard-delete (bypass soft-delete)."""
        return super().delete()

    def restore(self):
        """Bulk restore: clear deleted_at on all matched rows."""
        return self.update(deleted_at=None)

    def deleted(self):
        """Only soft-deleted rows."""
        return self.filter(deleted_at__isnull=False)

    def active(self):
        """Only non-deleted rows."""
        return self.filter(deleted_at__isnull=True)


# ---------------------------------------------------------------------------
# Managers - two views over the same table
# ---------------------------------------------------------------------------
class XParanoidManager(models.Manager.from_queryset(XParanoidQuerySet)):
    """Default manager: hides soft-deleted rows."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class XParanoidManagerWithDeleted(models.Manager.from_queryset(XParanoidQuerySet)):
    """Unfiltered manager: sees everything (active + deleted)."""

    pass  # no extra filter - exposes all rows but keeps soft-delete helpers


# Backward-compat aliases (so `from x_paranoid.models import ParanoidModel` still works)
ParanoidModelManager = XParanoidManager
ParanoidQuerySet = XParanoidQuerySet


# ---------------------------------------------------------------------------
# Abstract model
# ---------------------------------------------------------------------------
class XParanoidModel(models.Model):
    """Abstract base adding created_at / updated_at / deleted_at + soft-delete."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True, default=None, db_index=True)

    # The two managers every paranoid model needs:
    objects = XParanoidManager()  # active only (default)
    objects_with_deleted = XParanoidManagerWithDeleted()  # all rows
    # optional convenience - will be added in later phases if needed:
    # deleted_objects = manager that returns only deleted

    class Meta:
        abstract = True

    def delete(self, hard=False, **kwargs):
        """Instance soft-delete. Use hard=True to really remove the row."""
        if hard:
            return super().delete(**kwargs)
        self.deleted_at = now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def hard_delete(self, **kwargs):
        """Instance hard-delete alias."""
        return super().delete(**kwargs)

    def restore(self):
        """Restore a soft-deleted instance."""
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])

    @property
    def is_deleted(self):
        return self.deleted_at is not None


# Backward-compat alias
ParanoidModel = XParanoidModel
