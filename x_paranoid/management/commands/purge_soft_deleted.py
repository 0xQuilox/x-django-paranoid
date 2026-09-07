from django.core.management.base import BaseCommand
from django.utils.timezone import now
from datetime import timedelta
from x_paranoid.models import XParanoidModel

class Command(BaseCommand):
    help = "Hard-delete soft-deleted rows older than TTL"
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--days', type=int, default=None)
    def handle(self, *args, **opts):
        for model in XParanoidModel.__subclasses__():
            ttl = getattr(getattr(model,'XParanoidMeta',None),'auto_hard_delete_after', None)
            if opts['days'] is not None: ttl = timedelta(days=opts['days'])
            if ttl is None: continue
            cutoff = now() - ttl
            qs = model.objects_with_deleted.filter(deleted_at__lte=cutoff)
            n = qs.count()
            if opts['dry_run']:
                self.stdout.write(f"[dry-run] {model.__name__}: {n} would purge")
            else:
                qs.hard_delete()
                self.stdout.write(f"{model.__name__}: purged {n}")