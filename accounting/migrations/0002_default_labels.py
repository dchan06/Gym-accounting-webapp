# Data migration: create default Singapore-friendly account labels

from django.db import migrations


def create_default_labels(apps, schema_editor):
    AccountLabel = apps.get_model('accounting', 'AccountLabel')
    defaults = [
        ('Membership / Subscriptions', 'REV-001', 'revenue', 'Gym membership and subscription income'),
        ('Rent', 'EXP-RENT', 'expense', 'Premises rent'),
        ('Utilities', 'EXP-UTIL', 'expense', 'Electricity, water, etc.'),
        ('Salaries & CPF', 'EXP-PAY', 'expense', 'Staff salaries and CPF'),
        ('Insurance', 'EXP-INS', 'expense', 'Business insurance'),
        ('Equipment & Maintenance', 'EXP-EQUIP', 'expense', 'Equipment and repairs'),
        ('Marketing', 'EXP-MKT', 'expense', 'Advertising and marketing'),
        ('Bank Charges', 'EXP-BANK', 'expense', 'Bank fees'),
        ('Other Revenue', 'REV-OTH', 'revenue', 'Other income'),
        ('Other Expenses', 'EXP-OTH', 'expense', 'Other expenses'),
    ]
    for name, code, category, desc in defaults:
        AccountLabel.objects.get_or_create(
            name=name,
            defaults={'code': code, 'category': category, 'description': desc, 'is_user_defined': True},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_labels, noop),
    ]
