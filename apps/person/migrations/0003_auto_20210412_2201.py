# Generated by Django 3.2 on 2021-04-12 15:01

import django.core.validators
from django.db import migrations, models
import utils.validators


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0002_auto_20210326_1108'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='verifycode',
            name='username',
        ),
        migrations.AlterField(
            model_name='profile',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='user',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='verifycode',
            name='challenge',
            field=models.SlugField(choices=[('validate_email', 'Validate Email'), ('validate_msisdn', 'Validate MSISDN'), ('password_recovery', 'Password Recovery'), ('username_recovery', 'Username Recovery'), ('change_msisdn', 'Change MSISDN'), ('change_email', 'Change Email'), ('change_username', 'Change Username'), ('change_password', 'Change Password')], default=1, max_length=128, validators=[django.core.validators.RegexValidator(message="Code can only contain the letters a-z, A-Z, digits, and underscores, and can't start with a digit.", regex='^[a-zA-Z_][0-9a-zA-Z_]*$'), utils.validators.non_python_keyword]),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='verifycode',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]