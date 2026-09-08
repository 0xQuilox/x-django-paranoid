from setuptools import setup
excluded = ['manage.py, tests/settings.py']

setup(name="x-django-paranoid",
       version="0.2.0",
       description="Production-grade soft-delete for Django - improved version of django-paranoid",
       long_description=open('README.md', 'r').read() if __import__('os').path.exists('README.md') else '',
       long_description_content_type='text/markdown',
       author="0xQuilox",
       url="https://github.com/0xquilox/x-django-paranoid",
       license="MIT",
       packages=["x_paranoid"],
       keywords="django created_at updated_at deleted_at fields models django-admin soft delete softdelete paranoid",
       )
