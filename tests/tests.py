from django.test import TestCase
from tests.models import MyModel
from tests.models import Author, Book


class MyModelTestCase(TestCase):

    def setUp(self):
        obj1 = MyModel.objects.create(field="soft_delete")
        obj2 = MyModel.objects.create(field="hard_delete")

    def test_soft_delete_obj(self):
        obj = MyModel.objects.filter(field="soft_delete")
        obj.delete()
        obj_soft_deleted = MyModel.objects.filter(field="soft_delete")
        self.assertEqual(obj_soft_deleted.count(), 0)

    def test_soft_delete_get_obj(self):
        obj_soft_deleted = MyModel.objects_with_deleted.get(
            field="soft_delete")
        self.assertEqual(obj_soft_deleted.field, "soft_delete")

    def test_soft_restore_obj(self):
        obj_soft_deleted = MyModel.objects_with_deleted.get(
            field="soft_delete")
        obj_soft_deleted.restore()
        obj_restore_soft_deleted = MyModel.objects.filter(field="soft_delete")
        self.assertEqual(obj_soft_deleted.field, "soft_delete")

    def test_hard_delete_obj(self):
        obj = MyModel.objects_with_deleted.get(
            field="hard_delete")
        obj.delete(True)
        obj_hard_deleted = MyModel.objects.filter(field="hard_delete")
        self.assertEqual(obj_hard_deleted.count(), 0)


class BulkCascadeTest(TestCase):
    
    def test_bulk_delete_cascades(self):
        a = Author.objects.create(name="A")
        Book.objects.create(title="T1", author=a)
        Book.objects.create(title="T2", author=a)
        Author.objects.filter(pk=a.pk).delete()
        self.assertEqual(Book.objects.count(), 0)
        self.assertEqual(Book.objects_with_deleted.count(), 2)
    def test_bulk_restore(self):
        a = Author.objects.create(name="A")
        Book.objects.create(title="T1", author=a)
        Author.objects.filter(pk=a.pk).delete()
        Author.objects_with_deleted.filter(pk=a.pk).restore()
        self.assertEqual(Book.objects.count(), 1)