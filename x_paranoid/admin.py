from django.contrib import admin

class SoftDeletedListFilter(admin.SimpleListFilter):
    title = "status"
    parameter_name = "deleted"
    def lookups(self, request, model_admin):
        return [("active","Active"),("deleted","Soft Deleted"),("all","All")]
    def queryset(self, request, queryset):
        if self.value() == "deleted":
            return queryset.model.objects_with_deleted.filter(deleted_at__isnull=False)
        if self.value() == "all":
            return queryset.model.objects_with_deleted.all()
        return queryset

class XParanoidAdmin(admin.ModelAdmin):
    readonly_fields = ('created_at','deleted_at','updated_at','deletion_batch_id')
    list_display = ('__str__','is_deleted_badge','deleted_at')
    list_filter = (SoftDeletedListFilter,)
    actions = ('restore_selected',)
    def get_queryset(self, request):
        return self.model.objects_with_deleted.all()
    @admin.display(boolean=True, description="Deleted")
    def is_deleted_badge(self, obj):
        return obj.is_deleted
    @admin.action(description="Restore selected soft-deleted")
    def restore_selected(self, request, queryset):
        for obj in queryset.filter(deleted_at__isnull=False):
            obj.restore()