from django.db import migrations, models


def backfill_signed_debit(apps, schema_editor):
    BankStatementUpload = apps.get_model('accounting', 'BankStatementUpload')
    BankTransaction = apps.get_model('accounting', 'BankTransaction')
    for upload in BankStatementUpload.objects.all():
        if BankTransaction.objects.filter(upload=upload, debit__lt=0).exists():
            upload.signed_debit_column = True
            upload.save(update_fields=['signed_debit_column'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0003_jsonfield_django_encoder'),
    ]

    operations = [
        migrations.AddField(
            model_name='bankstatementupload',
            name='signed_debit_column',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(backfill_signed_debit, noop),
    ]
