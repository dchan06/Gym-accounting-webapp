from django import forms
from django.core.validators import FileExtensionValidator
from datetime import date
from .models import BankStatementUpload, BankTransaction, AccountLabel

_STATEMENT_EXTENSIONS = ('csv', 'xls', 'xlsx')


class BankStatementUploadForm(forms.ModelForm):
    month = forms.CharField(
        help_text='Statement period (YYYY-MM)',
        widget=forms.TextInput(attrs={'type': 'month', 'placeholder': 'YYYY-MM'}),
    )
    file = forms.FileField(
        validators=[FileExtensionValidator(allowed_extensions=_STATEMENT_EXTENSIONS)],
        help_text='CSV, or Excel .xls / .xlsx (converted automatically)',
    )

    class Meta:
        model = BankStatementUpload
        fields = ['file', 'month']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].widget.attrs.update({'accept': '.csv,.xls,.xlsx,application/vnd.ms-excel'})

    def clean_month(self):
        val = self.cleaned_data.get('month') or ''
        if not val:
            raise forms.ValidationError('Select statement month (YYYY-MM).')
        parts = val.strip().split('-')
        if len(parts) == 2:
            try:
                y, m = int(parts[0]), int(parts[1])
                return date(y, m, 1)
            except (ValueError, TypeError):
                pass
        raise forms.ValidationError('Use YYYY-MM format.')

    def save(self, commit=True, user=None):
        obj = super().save(commit=False)
        obj.month = self.cleaned_data['month']
        if user:
            obj.user = user
        if obj.file and hasattr(obj.file, 'name'):
            obj.original_filename = obj.file.name
        if commit:
            obj.save()
        return obj


class TransactionLabelForm(forms.ModelForm):
    class Meta:
        model = BankTransaction
        fields = ['label', 'notes', 'bookmark']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['label'].queryset = AccountLabel.objects.all().order_by('category', 'name')
        self.fields['label'].required = False
