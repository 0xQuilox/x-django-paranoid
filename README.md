# x-django-paranoid

Improved fork of `django-paranoid` (Carlos Ganoza) - production-grade soft-delete.

## Roadmap

- **Phase 0 (done next):** Fix bulk `QuerySet.delete()` bug, proper managers
- **Phase 1:** Partial unique indexes + restore conflict policies + DRF mixin
- **Phase 2:** `deletion_batch_id` cascade tracing, `PARANOID_CASCADE/PROTECT/SET_NULL`
- **Phase 3:** `XParanoidAdmin`, TTL purge command, DRF viewset mixins

## Quickstart

```python
from x_paranoid.models import XParanoidModel

class Article(XParanoidModel):
    slug = models.SlugField(unique=True)
```
