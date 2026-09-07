from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

class SoftDeleteModelMixin:
    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if request.query_params.get('hard') == 'true':
            obj.hard_delete()
        else:
            obj.delete()
        return Response(status=204)

class RestoreModelMixin:
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        obj = self.get_queryset().model.objects_with_deleted.get(pk=pk)
        obj.restore()
        return Response(self.get_serializer(obj).data)

class DeletedListModelMixin:
    @action(detail=False, methods=['get'])
    def deleted(self, request):
        qs = self.get_queryset().model.objects_with_deleted.filter(deleted_at__isnull=False)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)