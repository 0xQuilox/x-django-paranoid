"""x-django-paranoid package."""

# Lazy re-exports to avoid AppRegistryNotReady during Django setup.
# Use: from x_paranoid.models import XParanoidModel  (preferred)
# or:  from x_paranoid import XParanoidModel  (also works after apps ready)

def __getattr__(name):
    if name in {"ParanoidModel", "XParanoidModel", "ParanoidModelManager", "XParanoidManager", "XParanoidQuerySet", "ParanoidQuerySet"}:
        from . import models as _models
        return getattr(_models, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["ParanoidModel", "ParanoidModelManager", "XParanoidModel", "XParanoidQuerySet", "XParanoidManager", "ParanoidQuerySet"]
