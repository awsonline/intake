# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-06-23 18:28
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_accounts', '0003_auto_20160525_1728'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='should_get_notifications',
            field=models.BooleanField(default=False),
        ),
    ]
