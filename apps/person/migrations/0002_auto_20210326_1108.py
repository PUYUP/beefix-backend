# Generated by Django 3.1.7 on 2021-03-26 04:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='verifycode',
            name='user',
        ),
        migrations.AddField(
            model_name='verifycode',
            name='username',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]