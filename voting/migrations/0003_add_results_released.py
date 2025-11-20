from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voting', '0002_poll_creator_code_poll_is_deleted_poll_is_public_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='poll',
            name='results_released',
            field=models.BooleanField(default=False, help_text='Whether results have been released by the creator while poll is active'),
        ),
    ]
