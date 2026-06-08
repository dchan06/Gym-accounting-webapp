# Generated manually for gym accounting

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AccountLabel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, unique=True)),
                ('code', models.CharField(blank=True, max_length=32)),
                ('category', models.CharField(choices=[('revenue', 'Revenue'), ('expense', 'Expense'), ('asset', 'Asset'), ('liability', 'Liability'), ('equity', 'Equity'), ('other', 'Other')], default='expense', max_length=32)),
                ('description', models.TextField(blank=True)),
                ('is_user_defined', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['category', 'name'],
            },
        ),
        migrations.CreateModel(
            name='BankStatementUpload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='statements/%Y/%m/')),
                ('original_filename', models.CharField(max_length=255)),
                ('month', models.DateField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('processed', models.BooleanField(default=False)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='statement_uploads', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-month', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MonthlyAGMAccounts',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month', models.DateField()),
                ('document', models.FileField(blank=True, null=True, upload_to='agm_accounts/%Y/%m/')),
                ('summary_json', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-month'],
                'verbose_name_plural': 'Monthly AGM accounts',
            },
        ),
        migrations.CreateModel(
            name='MonthlyMetrics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month', models.DateField()),
                ('revenue_total', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('expenses_total', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('member_count', models.PositiveIntegerField(blank=True, null=True)),
                ('new_members', models.PositiveIntegerField(blank=True, null=True)),
                ('churn_count', models.PositiveIntegerField(blank=True, null=True)),
                ('extra_data', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-month'],
                'verbose_name_plural': 'Monthly metrics',
            },
        ),
        migrations.CreateModel(
            name='BankTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('description', models.CharField(max_length=512)),
                ('reference', models.CharField(blank=True, max_length=128)),
                ('debit', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('credit', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('balance_after', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ('label_confidence', models.FloatField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('label', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transactions', to='accounting.accountlabel')),
                ('upload', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='accounting.bankstatementupload')),
            ],
            options={
                'ordering': ['date', 'id'],
            },
        ),
        migrations.CreateModel(
            name='MonthlyPL',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month', models.DateField()),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('label', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pl_entries', to='accounting.accountlabel')),
            ],
            options={
                'ordering': ['-month', 'label__category', 'label__name'],
                'verbose_name': 'Monthly P&L',
                'verbose_name_plural': 'Monthly P&L',
            },
        ),
        migrations.CreateModel(
            name='LabelSuggestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(max_length=64)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('label', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='suggestions', to='accounting.accountlabel')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='monthlymetrics',
            constraint=models.UniqueConstraint(fields=('month',), name='unique_monthly_metrics'),
        ),
        migrations.AddConstraint(
            model_name='monthlypl',
            constraint=models.UniqueConstraint(fields=('month', 'label'), name='unique_monthly_pl_per_label'),
        ),
    ]
