# Generated by Django 2.0.4 on 2018-04-30 22:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0002_auto_20180418_2039'),
    ]

    operations = [
        migrations.AlterField(
            model_name='googlefitmember',
            name='access_token',
            field=models.CharField(max_length=512),
        ),
        migrations.AlterField(
            model_name='googlefitmember',
            name='expires_in',
            field=models.CharField(max_length=512),
        ),
        migrations.AlterField(
            model_name='googlefitmember',
            name='refresh_token',
            field=models.CharField(max_length=512),
        ),
        migrations.AlterField(
            model_name='googlefitmember',
            name='scope',
            field=models.CharField(max_length=512),
        ),
        migrations.AlterField(
            model_name='googlefitmember',
            name='token_type',
            field=models.CharField(max_length=512),
        ),
    ]
