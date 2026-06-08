from django.contrib import admin
from .models import (
    AccountLabel,
    BankStatementUpload,
    BankTransaction,
    MonthlyMetrics,
    MonthlyPL,
    MonthlyAGMAccounts,
    LabelSuggestion,
)


@admin.register(AccountLabel)
class AccountLabelAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'is_user_defined')
    list_filter = ('category', 'is_user_defined')
    search_fields = ('name', 'code')


@admin.register(BankStatementUpload)
class BankStatementUploadAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'month', 'user', 'status', 'auto_labelled_count', 'created_at')
    list_filter = ('status', 'month')


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'description', 'debit', 'credit', 'label', 'bookmark', 'upload')
    list_filter = ('label', 'bookmark', 'upload__month')
    search_fields = ('description', 'reference')


@admin.register(MonthlyMetrics)
class MonthlyMetricsAdmin(admin.ModelAdmin):
    list_display = ('month', 'revenue_total', 'expenses_total', 'member_count')


@admin.register(MonthlyPL)
class MonthlyPLAdmin(admin.ModelAdmin):
    list_display = ('month', 'label', 'amount')
    list_filter = ('month', 'label__category')


@admin.register(MonthlyAGMAccounts)
class MonthlyAGMAccountsAdmin(admin.ModelAdmin):
    list_display = ('month', 'document', 'created_at')


@admin.register(LabelSuggestion)
class LabelSuggestionAdmin(admin.ModelAdmin):
    list_display = ('label', 'source', 'created_at')
