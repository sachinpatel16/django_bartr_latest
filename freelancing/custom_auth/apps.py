from django.apps import AppConfig

class CustomAuthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = __name__.rpartition(".")[0]

    def ready(self):
            import freelancing.custom_auth.signals