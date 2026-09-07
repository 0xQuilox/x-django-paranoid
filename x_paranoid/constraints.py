from django.db.models import Q, UniqueConstraint


class ParanoidUniqueConstraint(UniqueConstraint):

    def __init__(self, *args, **kwargs):
        active_q = Q(deleted_at__isnull=True)
        if "condition" in kwargs and kwargs["condition"] is not None:
            kwargs["condition"] = kwargs["condition"] & active_q
        else:
            kwargs["condition"] = active_q
        super().__init__(*args, **kwargs)



XParanoidUniqueConstraint = ParanoidUniqueConstraint
