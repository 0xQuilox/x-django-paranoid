DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECRET_KEY = "secrekey"

INSTALLED_APPS = ["x_paranoid", "tests", ]
