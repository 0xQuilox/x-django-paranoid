from django.core import checks
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models.fields.related_descriptors import ForwardManyToOneDescriptor


class ObjectSoftDeleted(ObjectDoesNotExist):
    pass


class SoftDeletedForwardManyToOneDescriptor(ForwardManyToOneDescriptor):

    def __get__(self, instance, cls=None):
        if instance is None:
            return self
        try:
            obj = super().__get__(instance, cls)
        except ObjectDoesNotExist:
            return None

        if obj is not None and getattr(obj, 'is_deleted', False):
            if getattr(self.field, 'raise_on_deleted', False):
                raise ObjectSoftDeleted(
                    f"{obj.__class__.__name__} instance ({obj.pk}) has been soft-deleted."
                )
            return None
        return obj


class XParanoidForeignKey(models.ForeignKey):
    forward_related_accessor_class = SoftDeletedForwardManyToOneDescriptor

    def __init__(self, *args, raise_on_deleted=False, **kwargs):
        self.raise_on_deleted = raise_on_deleted
        super().__init__(*args, **kwargs)


class XParanoidManyToManyField(models.ManyToManyField):

    def check(self, **kwargs):
        errors = super().check(**kwargs)
        through = self.remote_field.through

        if getattr(through, '_meta', None) and through._meta.auto_created:
            return errors

        if isinstance(through, str):
            try:
                from django.apps import apps
                through = apps.get_model(through, require_ready=False)
            except Exception:
                return errors

        if through is not None and hasattr(through, '__mro__'):
            is_paranoid = any(base.__name__ == 'XParanoidModel' for base in through.__mro__)
            if not is_paranoid:
                errors.append(
                    checks.Warning(
                        f"Through model '{through.__name__}' on field '{self.name}' should inherit XParanoidModel "
                        f"to support soft-deletable junctions.",
                        obj=self,
                        id="x_paranoid.W001",
                    )
                )
        return errors