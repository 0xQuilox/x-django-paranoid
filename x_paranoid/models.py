from django.db import models
from django.db import transaction
from django.db.models import ProtectedError
from django.utils.timezone import now
from x_paranoid.signals import pre_soft_delete, post_soft_delete, pre_restore, post_restore
import uuid


class XParanoidQuerySet(models.QuerySet):


    def delete(self, hard=False, batch_id=None):
        if hard:
            return super().delete()
        batch = batch_id or uuid.uuid4()
        with transaction.atomic():
            objs = list(self)
            for obj in objs:
                obj.delete(batch_id=batch)
            return len(objs)

    def hard_delete(self):
        return super().delete()

    def restore(self):
        with transaction.atomic():
            objs = list(self)
            for obj in objs:
                obj.restore()
            return len(objs)
    
    def deleted(self):
        return self.filter(deleted_at__isnull=False)

    def active(self):
        return self.filter(deleted_at__isnull=True)


class XParanoidManager(models.Manager.from_queryset(XParanoidQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class XParanoidManagerWithDeleted(models.Manager.from_queryset(XParanoidQuerySet)):
    pass


class XParanoidModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True, default=None, db_index=True)
    deletion_batch_id = models.UUIDField(null=True, blank=True, db_index=True)
    objects = XParanoidManager()
    objects_with_deleted = XParanoidManagerWithDeleted()

    class Meta:
        abstract = True

    class XParanoidMeta:
        on_restore_conflict = 'RAISE_ERROR'
        rename_template = "{value}-restored-{id}"
        auto_hard_delete_after = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        parent_opts = getattr(XParanoidModel.XParanoidMeta, '__dict__', {})
        child_meta = getattr(cls, 'XParanoidMeta', None)
        if child_meta is XParanoidModel.XParanoidMeta:
            return
        if not hasattr(cls, 'XParanoidMeta') or child_meta is None:
            cls.XParanoidMeta = type('XParanoidMeta', (), dict(parent_opts))
        else:
            for k, v in parent_opts.items():
                if k.startswith('_'):
                    continue
                if not hasattr(child_meta, k):
                    setattr(child_meta, k, v)

    def delete(self, hard=False, batch_id=None, **kwargs):
        pre_soft_delete.send(sender=self.__class__, instance=self, batch_id=batch_id)
        if hard:
            return super().delete(**kwargs)
        if self.deleted_at is not None:
            return
        batch_id = batch_id or uuid.uuid4()
        with transaction.atomic():
            self.deleted_at = now()
            self.deletion_batch_id = batch_id
            self.save(update_fields=["deleted_at", "updated_at", "deletion_batch_id"])
            for rel in self._meta.related_objects:
                related_model = rel.related_model
                if not issubclass(related_model, XParanoidModel):
                    continue
                fk_name = rel.field.name
                policy = getattr(rel.field, "paranoid_on_delete", "CASCADE")
                fk_name = rel.field.name
                if policy == "PROTECT":
                    if related_model.objects.filter(**{fk_name: self.pk}).exists():
                        raise models.ProtectedError(f"Cannot soft-delete {self} because {related_model.__name__} still refers to it.", related_model.objects.filter(**{fk_name: self.pk}),)
                elif policy == "SET_NULL":
                    related_model.objects.filter(**{fk_name: self.pk}).update(**{fk_name: None})
                else:
                    for child in related_model.objects.filter(**{fk_name: self.pk}):
                        child.delete(batch_id=batch_id)
        post_soft_delete.send(sender=self.__class__, instance=self, batch_id=batch_id)

    def hard_delete(self, **kwargs):
        return super().delete(**kwargs)

    def _get_unique_conflict_qs(self):
        q = models.Q()
        has_unique = False
        for field in self._meta.get_fields():
            if getattr(field, 'unique', False) and hasattr(field, 'name'):
                if getattr(self, field.name) is not None:
                    q |= models.Q(**{field.name: getattr(self, field.name)})
                    has_unique = True
        for const in self._meta.constraints:
            if isinstance(const, models.UniqueConstraint) and const.fields:
                sub_q = models.Q()
                for fname in const.fields:
                    sub_q &= models.Q(**{fname: getattr(self, fname)})
                q |= sub_q
                has_unique = True
        if not has_unique:
            return self.__class__.objects.none()
        return self.__class__.objects.filter(q).exclude(pk=self.pk)

    def restore(self):
        if self.deleted_at is None:
            return
        batch_id = self.deletion_batch_id
        pre_restore.send(sender=self.__class__, instance=self, batch_id=batch_id)
        qs = self._get_unique_conflict_qs()
        renamed_fields = []
        if qs.exists():
            policy = getattr(getattr(self, 'XParanoidMeta', None), 'on_restore_conflict', 'RAISE_ERROR')
            tmpl = getattr(getattr(self, 'XParanoidMeta', None), 'rename_template', "{value}-restored-{id}")
            if policy == 'RAISE_ERROR':
                from django.db import IntegrityError
                raise IntegrityError(f"Restore conflict: active {self.__class__.__name__} with same unique value exists.")
            elif policy == 'FORK_RENAME':
                for field in self._meta.get_fields():
                    if getattr(field, 'unique', False) and hasattr(field, 'name') and not getattr(field, 'primary_key', False):
                        if getattr(field, 'auto_created', False):
                            continue
                        val = getattr(self, field.name)
                        if val is not None and qs.filter(**{field.name: val}).exists():
                            setattr(self, field.name, tmpl.format(value=val, id=self.pk))
                            renamed_fields.append(field.name)
                for const in self._meta.constraints:
                    if isinstance(const, models.UniqueConstraint) and const.fields:
                        for fname in const.fields:
                            if fname in renamed_fields:
                                continue
                            val = getattr(self, fname)
                            if val is not None and qs.filter(**{fname: val}).exists():
                                if getattr(self, fname) == val:
                                    setattr(self, fname, tmpl.format(value=val, id=self.pk))
                                    renamed_fields.append(fname)
            elif policy == 'OVERWRITE_ACTIVE':
                qs.hard_delete()
        self.deleted_at = None
        self.deletion_batch_id = None
        update_fields = ["deleted_at", "updated_at", "deletion_batch_id"] + renamed_fields
        self.save(update_fields=update_fields)
        if batch_id:
            with transaction.atomic():
                for rel in self._meta.related_objects:
                    related_model = rel.related_model
                    if not issubclass(related_model, XParanoidModel):
                        continue
                    fk_name = rel.field.name
                    for child in related_model.objects_with_deleted.filter(
                        **{fk_name: self.pk, "deletion_batch_id": batch_id}
                    ):
                        child.restore()
        post_restore.send(sender=self.__class__, instance=self, batch_id=batch_id)

    @property
    def is_deleted(self):
        return self.deleted_at is not None
