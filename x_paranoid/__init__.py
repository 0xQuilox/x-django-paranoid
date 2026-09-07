def __getattr__(name):
    if name in {"XParanoidModel", "XParanoidManager", "XParanoidQuerySet", "ParanoidUniqueConstraint", "XParanoidUniqueConstraint"}:
        from . import models as _models
        from . import constraints as _constraints
        if hasattr(_models, name):
            return getattr(_models, name)
        return getattr(_constraints, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["XParanoidModel", "XParanoidManager", "XParanoidQuerySet", "ParanoidUniqueConstraint", "XParanoidUniqueConstraint"]
