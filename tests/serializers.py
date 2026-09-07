from rest_framework import serializers
from x_paranoid.serializers import XParanoidSerializerMixin
from tests.models import Article
class ArticleSerializer(XParanoidSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ['id','slug']