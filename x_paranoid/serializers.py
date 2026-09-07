from rest_framework.validators import UniqueValidator
from django.db.models import Q

class XParanoidSerializerMixin:
    
    def get_fields(self):
        fields = super().get_fields()
        model = getattr(self.Meta, 'model', None)
        if not model:
            return fields
        unique_fields = set()

        for f in model._meta.get_fields():
            if getattr(f, 'unique', False) and hasattr(f, 'name'):
                unique_fields.add(f.name)

        for c in model._meta.constraints:
            if hasattr(c, 'fields'):
                unique_fields.update(c.fields or [])
        
        for fname in unique_fields:
            if fname not in fields:
                continue
            field = fields[fname]
            field.validators = [v for v in field.validators if not isinstance(v, UniqueValidator)]
            field.validators.append(
                UniqueValidator(
                    queryset=model.objects.all(),
                    message=field.error_messages.get('unique', 'Already exists (active).')
                )
            )
        return fields