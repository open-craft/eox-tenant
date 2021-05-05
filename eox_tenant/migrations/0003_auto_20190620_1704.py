# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-06-20 21:04
from __future__ import unicode_literals

import django.db.models.deletion
import jsonfield.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eox_tenant', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Route',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=100, unique=True, verbose_name='domain name')),
            ],
        ),
        migrations.CreateModel(
            name='TenantConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_key', models.CharField(db_index=True, max_length=63)),
                ('lms_configs', jsonfield.fields.JSONField(blank=True)),
                ('studio_configs', jsonfield.fields.JSONField(blank=True)),
                ('theming_configs', jsonfield.fields.JSONField(blank=True)),
                ('meta', jsonfield.fields.JSONField(blank=True)),
            ],
        ),
        migrations.AddField(
            model_name='route',
            name='config',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='eox_tenant.TenantConfig'),
        ),
    ]
