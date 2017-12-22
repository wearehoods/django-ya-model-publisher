# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2017-12-22 13:06
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0002_auto_20171122_1551'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='publisherstatemodel',
            options={'get_latest_by': 'request_timestamp', 'ordering': ['-request_timestamp'], 'verbose_name': 'Publisher State', 'verbose_name_plural': 'Publisher States'},
        ),
    ]
