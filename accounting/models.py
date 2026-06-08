"""
Models for gym accounting: bank statements, labels, metrics, P&L, AGM accounts.
"""
from django.contrib.auth.models import User
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class AccountLabel(models.Model):
    """User-defined or AI-suggested labels for categorising transactions (Singapore tax-friendly)."""
    name = models.CharField(max_length=128, unique=True)
    code = models.CharField(max_length=32, blank=True)  # e.g. REV-001, EXP-UTIL
    category = models.CharField(
        max_length=32,
        choices=[
            ('revenue', 'Revenue'),
            ('expense', 'Expense'),
            ('asset', 'Asset'),
            ('liability', 'Liability'),
            ('equity', 'Equity'),
            ('other', 'Other'),
        ],
        default='expense',
    )
    description = models.TextField(blank=True)
    is_user_defined = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class StatementUploadStatus(models.TextChoices):
    PROCESSING = 'processing', 'Processing'
    AUTOMATICALLY_LABELLED = 'automatically_labelled', 'Automatically labelled'
    PROCESSED = 'processed', 'Processed'


class TransactionBookmark(models.TextChoices):
    EMPTY = '', '—'
    UNSURE = 'unsure', 'Unsure'
    CHECK = 'check', 'Check'
    MISSING_RECEIPT = 'missing_receipt', 'Missing receipt'


class BankStatementUpload(models.Model):
    """Tracks an uploaded bank statement file and its parsed state."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='statement_uploads')
    file = models.FileField(upload_to='statements/%Y/%m/')
    original_filename = models.CharField(max_length=255)
    month = models.DateField()  # statement period month
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=32,
        choices=StatementUploadStatus.choices,
        default=StatementUploadStatus.PROCESSING,
    )
    # How many transactions received an ML-applied label on upload (confidence ≥ threshold).
    auto_labelled_count = models.PositiveIntegerField(default=0)
    # True when CSV uses signed amounts in the debit column (negative=out, positive=in).
    signed_debit_column = models.BooleanField(default=False)

    class Meta:
        ordering = ['-month', '-created_at']

    def __str__(self):
        return f"{self.original_filename} ({self.month})"


class BankTransaction(models.Model):
    """Single transaction from a bank statement (user-labelled or AI-suggested)."""
    upload = models.ForeignKey(
        BankStatementUpload,
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    date = models.DateField()
    description = models.CharField(max_length=512)  # narrative from bank
    reference = models.CharField(max_length=128, blank=True)
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance_after = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    label = models.ForeignKey(
        AccountLabel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
    )
    label_confidence = models.FloatField(null=True, blank=True)  # ML confidence 0–1
    bookmark = models.CharField(
        max_length=24,
        choices=TransactionBookmark.choices,
        blank=True,
        default=TransactionBookmark.EMPTY,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date', 'id']

    @property
    def amount(self):
        from accounting.services.cash_flow import net_cash_impact

        return net_cash_impact(self)


class MonthlyMetrics(models.Model):
    """Stored monthly metrics (KPIs) for the gym."""
    month = models.DateField()
    revenue_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expenses_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    member_count = models.PositiveIntegerField(null=True, blank=True)
    new_members = models.PositiveIntegerField(null=True, blank=True)
    churn_count = models.PositiveIntegerField(null=True, blank=True)
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder,
    )  # flexible KPIs
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-month']
        verbose_name_plural = 'Monthly metrics'
        constraints = [
            models.UniqueConstraint(fields=['month'], name='unique_monthly_metrics'),
        ]

    def __str__(self):
        return f"Metrics {self.month.strftime('%Y-%m')}"


class MonthlyPL(models.Model):
    """Stored monthly Profit & Loss summary by label/category."""
    month = models.DateField()
    label = models.ForeignKey(
        AccountLabel,
        on_delete=models.CASCADE,
        related_name='pl_entries',
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-month', 'label__category', 'label__name']
        verbose_name = 'Monthly P&L'
        verbose_name_plural = 'Monthly P&L'
        constraints = [
            models.UniqueConstraint(
                fields=['month', 'label'],
                name='unique_monthly_pl_per_label',
            ),
        ]

    def __str__(self):
        return f"P&L {self.month.strftime('%Y-%m')} — {self.label.name}: {self.amount}"


class MonthlyAGMAccounts(models.Model):
    """Stored monthly accounts formatted for Singapore AGM / annual return submission."""
    month = models.DateField()
    document = models.FileField(upload_to='agm_accounts/%Y/%m/', null=True, blank=True)
    summary_json = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder,
    )  # totals by category
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-month']
        verbose_name_plural = 'Monthly AGM accounts'

    def __str__(self):
        return f"AGM accounts {self.month.strftime('%Y-%m')}"


class LabelSuggestion(models.Model):
    """Cache of AI/ML suggestions and Singapore tax guidance for display."""
    label = models.ForeignKey(
        AccountLabel,
        on_delete=models.CASCADE,
        related_name='suggestions',
    )
    source = models.CharField(max_length=64)  # 'ml', 'singapore_tax', 'user'
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
