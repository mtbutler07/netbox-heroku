# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-02-07 18:37
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ipam', '0020_ipaddress_add_role_carp'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='vrf',
            options={'ordering': ['name', 'rd'], 'verbose_name': 'VRF', 'verbose_name_plural': 'VRFs'},
        ),
    ]