# Generated by Django 4.2 on 2025-07-24 15:39

import django.contrib.auth.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("custom_auth", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="applicationuser",
            name="device_id",
        ),
        migrations.RemoveField(
            model_name="applicationuser",
            name="device_name",
        ),
        migrations.RemoveField(
            model_name="applicationuser",
            name="ip_address",
        ),
        migrations.RemoveField(
            model_name="applicationuser",
            name="os_version",
        ),
        migrations.AddField(
            model_name="applicationuser",
            name="is_merchant",
            field=models.BooleanField(
                default=False,
                help_text="Designates whether the user is a merchant.",
                verbose_name="Is Merchant",
            ),
        ),
        migrations.AlterField(
            model_name="applicationuser",
            name="username",
            field=models.CharField(
                blank=True,
                default="",
                error_messages={"unique": "A user with that username already exists."},
                help_text="Required. 150 characters or fewer. Lettres , digits and @/./+/-/ only .",
                max_length=150,
                unique=True,
                validators=[django.contrib.auth.validators.UnicodeUsernameValidator()],
                verbose_name="username",
            ),
        ),
    ]
