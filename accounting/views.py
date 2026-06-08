"""
Views: upload, label, metrics, P&L, AGM CSV download.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from decimal import Decimal
import csv
import hmac

from .models import (
    BankStatementUpload,
    BankTransaction,
    AccountLabel,
    MonthlyMetrics,
    MonthlyPL,
    MonthlyAGMAccounts,
    StatementUploadStatus,
    TransactionBookmark,
    User, 
)
from .forms import BankStatementUploadForm, TransactionLabelForm
from .services.csv_parser import parse_bank_statement_file
from .services.ml_labels import LabelPredictor, get_singapore_tax_guidance
from .services.agm_export import build_agm_csv
from .services.monthly_rollups import sync_rollups_for_user_month
from .services.cash_flow import net_cash_impact


class _SynthPLLabel:
    """Stand-in label for synthetic P&L rows rendered like MonthlyPL."""

    __slots__ = ('name', 'category')

    def __init__(self, name: str, category: str):
        self.name = name
        self.category = category

    def get_category_display(self):
        return 'Revenue' if self.category == 'revenue' else 'Expense'


class _SynthPLRow:
    __slots__ = ('label', 'amount')

    def __init__(self, label_name: str, category: str, amount: Decimal):
        self.label = _SynthPLLabel(label_name, category)
        self.amount = amount

def api_transactions(request): 
    incoming_request = request.headers.get('Authorization', '').replace('Bearer', '')

    if not hmac.compare_digest(incoming_request, settings.TRANSACTION_API_KEY): 
        return JsonResponse({'error': 'Invalid API key'}, status = 401)

    year = request.GET.get('year')
    month = request.GET.get('month')

    integration_username = User.objects.filter(username=settings.INTEGRATION_USERNAME).first() # In the future you can use a GET parameter to send a specific company ID
    print(integration_username)
    if not integration_username: 
        return JsonResponse({'error': 'No such user found'}, status=404)
    transaction = BankTransaction.objects.filter(upload__user=integration_username)
    if not transaction: 
        return JsonResponse({'error': 'No accounts found'}, status=404)
    if year: 
        transaction = transaction.filter(date__year=year)
    if month: 
        transaction = transaction.filter(date__month=month)
    data = list(transaction.values('id', 'debit', 'credit', 'label', 'date', 'bookmarked', 'notes'))
    return JsonResponse(data, safe=False)

def _aggregate_unlabelled_for_month(month_date):
    """Sum unlabelled cash impact for uploads in ``month_date`` (+ = revenue bucket, − = expense)."""
    qs = BankTransaction.objects.filter(
        upload__month=month_date,
        label__isnull=True,
    ).select_related('upload')
    un_rev = Decimal('0')
    un_exp = Decimal('0')  # sums of negative net impacts only
    for tx in qs:
        imp = net_cash_impact(tx)
        if imp > 0:
            un_rev += imp
        elif imp < 0:
            un_exp += imp
    return un_rev, un_exp


def _pl_month_revenue_expense_net(entries, unlabelled_revenue_extra=Decimal('0'), unlabelled_expense_impact_extra=Decimal('0')):
    """Totals for one month’s P&L rows; matches Metrics convention (expenses stored positive)."""
    revenue = Decimal('0')
    expenses = Decimal('0')
    for e in entries:
        cat = e.label.category
        amt = e.amount
        if cat == 'revenue':
            revenue += amt
        elif cat == 'expense':
            expenses += -amt
    revenue += unlabelled_revenue_extra
    if unlabelled_expense_impact_extra != Decimal('0'):
        expenses += -unlabelled_expense_impact_extra
    return revenue, expenses, revenue - expenses


@login_required
def home(request):
    uploads = (
        BankStatementUpload.objects.filter(user=request.user)
        .annotate(
            transaction_total=Count('transactions'),
            unsure_bookmark_count=Count(
                'transactions',
                filter=Q(transactions__bookmark=TransactionBookmark.UNSURE),
            ),
            unlabelled_count=Count(
                'transactions',
                filter=Q(transactions__label__isnull=True),
            ),
        )
        .order_by('-month', '-created_at')[:10]
    )
    return render(request, 'accounting/home.html', {'uploads': uploads})


@login_required
def upload_statement(request):
    if request.method == 'POST':
        form = BankStatementUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save(commit=False, user=request.user)
            upload.original_filename = request.FILES['file'].name
            upload.status = StatementUploadStatus.PROCESSING
            upload.auto_labelled_count = 0
            upload.save()
            try:
                rows = parse_bank_statement_file(upload.file)
                upload.signed_debit_column = any(
                    (row.get('debit') or Decimal('0')) < 0 for row in rows
                )
                predictor = LabelPredictor()
                predictor.fit()
                threshold = getattr(settings, 'ML_AUTO_LABEL_MIN_CONFIDENCE', 0.5)
                auto_labelled = 0
                for row in rows:
                    tx = BankTransaction(
                        upload=upload,
                        date=row['date'] or timezone.now().date(),
                        description=row['description'],
                        reference=row.get('reference', ''),
                        debit=row.get('debit', Decimal('0')),
                        credit=row.get('credit', Decimal('0')),
                        balance_after=row.get('balance_after'),
                    )
                    if predictor.label_ids_:
                        preds = predictor.predict(row['description'], row.get('reference', ''), top_k=1)
                        if preds:
                            label_id, confidence = preds[0]
                            if confidence >= threshold:
                                tx.label_id = label_id
                                tx.label_confidence = confidence
                    if tx.label_id:
                        auto_labelled += 1
                    tx.save()
                upload.auto_labelled_count = auto_labelled
                upload.status = StatementUploadStatus.AUTOMATICALLY_LABELLED
                upload.save(update_fields=['signed_debit_column', 'auto_labelled_count', 'status'])
                messages.success(
                    request,
                    f'Uploaded {len(rows)} transactions. '
                    f'{auto_labelled} auto-labelled by ML (confidence ≥ {threshold:.0%}). '
                    f'Remaining rows stay unlabelled for you to assign.',
                )
            except Exception as e:
                messages.error(request, f'Error processing CSV: {e}')
            return redirect('accounting:label_statement', upload_id=upload.pk)
        messages.error(request, 'Invalid form.')
    else:
        form = BankStatementUploadForm()
    return render(request, 'accounting/upload.html', {'form': form})


@login_required
def label_statement(request, upload_id):
    upload = get_object_or_404(BankStatementUpload, pk=upload_id, user=request.user)
    transactions = upload.transactions.all().select_related('label').order_by('date', 'id')
    guidance = get_singapore_tax_guidance()
    labels = AccountLabel.objects.all().order_by('category', 'name')
    label_options = [
        {'id': lbl.id, 'text': f'{lbl.name} ({lbl.get_category_display()})'}
        for lbl in labels
    ]
    return render(request, 'accounting/label.html', {
        'upload': upload,
        'transactions': transactions,
        'guidance': guidance,
        'labels': labels,
        'label_options': label_options,
    })


@login_required
@require_POST
def api_set_label(request, transaction_id):
    """JSON: set label (and optional notes) for a transaction."""
    tx = get_object_or_404(BankTransaction, pk=transaction_id)
    upload = tx.upload
    if upload.user_id != request.user.id:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    if 'label_id' in request.POST:
        raw = request.POST.get('label_id', '')
        if raw:
            try:
                tx.label_id = int(raw)
            except ValueError:
                tx.label_id = None
        else:
            tx.label_id = None
    if 'notes' in request.POST:
        tx.notes = request.POST.get('notes', '')
    if 'bookmark' in request.POST:
        mark = request.POST.get('bookmark', '')
        valid_marks = {c[0] for c in TransactionBookmark.choices}
        if mark in valid_marks:
            tx.bookmark = mark
    tx.save()
    if 'label_id' in request.POST:
        sync_rollups_for_user_month(upload.month, request.user)
    return JsonResponse({'ok': True, 'label_id': tx.label_id, 'bookmark': tx.bookmark})


@login_required
def api_suggest_labels(request, transaction_id):
    """JSON: return suggested labels for a transaction (ML + Singapore tax advice)."""
    tx = get_object_or_404(BankTransaction, pk=transaction_id)
    if tx.upload.user_id != request.user.id:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    predictor = LabelPredictor()
    predictor.fit()
    preds = predictor.predict(tx.description, tx.reference or '', top_k=5)
    labels = []
    for label_id, conf in preds:
        try:
            lbl = AccountLabel.objects.get(pk=label_id)
            labels.append({'id': lbl.id, 'name': lbl.name, 'category': lbl.category, 'confidence': round(conf, 2)})
        except AccountLabel.DoesNotExist:
            pass
    return JsonResponse({'suggestions': labels})


@login_required
def save_labelled(request, upload_id):
    """Save labelled data: update MonthlyMetrics, MonthlyPL, and AGM summary from all uploads in that month."""
    upload = get_object_or_404(BankStatementUpload, pk=upload_id, user=request.user)
    month = upload.month
    if not month:
        month = timezone.now().date().replace(day=1)

    sync_rollups_for_user_month(month, request.user)

    upload.status = StatementUploadStatus.PROCESSED
    upload.save(update_fields=['status'])

    messages.success(request, f'Saved labelled data for {month.strftime("%B %Y")}.')
    return redirect('accounting:metrics')


@login_required
def metrics(request):
    rows = MonthlyMetrics.objects.all().order_by('-month')[:24]
    metrics_list = []
    for m in rows:
        net = (m.revenue_total or Decimal('0')) - (m.expenses_total or Decimal('0'))
        metrics_list.append({'month': m.month, 'revenue_total': m.revenue_total, 'expenses_total': m.expenses_total, 'net': net})
    return render(request, 'accounting/metrics.html', {'metrics_list': metrics_list})


@login_required
def pl(request):
    months = list(MonthlyPL.objects.values_list('month', flat=True).distinct().order_by('-month')[:24])
    pl_by_month = []
    for m in months:
        entries = list(
            MonthlyPL.objects.filter(month=m)
            .select_related('label')
            .order_by('label__category', 'label__name')
        )
        un_rev, un_exp_imp = _aggregate_unlabelled_for_month(m)
        synth = []
        if un_rev != Decimal('0'):
            synth.append(
                _SynthPLRow('Unlabelled revenue', 'revenue', un_rev),
            )
        if un_exp_imp != Decimal('0'):
            synth.append(
                _SynthPLRow('Unlabelled expense', 'expense', un_exp_imp),
            )
        display_entries = synth + entries
        rev, exp, net = _pl_month_revenue_expense_net(
            entries,
            unlabelled_revenue_extra=un_rev,
            unlabelled_expense_impact_extra=un_exp_imp,
        )
        pl_by_month.append({
            'month': m,
            'entries': display_entries,
            'revenue_total': rev,
            'expenses_total': exp,
            'net': net,
        })
    overall = None
    if pl_by_month:
        chrono = list(reversed(pl_by_month))
        overall = {
            'revenue_total': sum(x['revenue_total'] for x in chrono),
            'expenses_total': sum(x['expenses_total'] for x in chrono),
            'net': sum(x['net'] for x in chrono),
            'months_count': len(chrono),
        }
    return render(request, 'accounting/pl.html', {'pl_by_month': pl_by_month, 'overall': overall})


@login_required
def download_agm_csv(request, month_str):
    """Download CSV for Singapore AGM / annual return for the given month (YYYY-MM)."""
    from datetime import date
    try:
        year, month = map(int, month_str.split('-'))
        month_date = date(year, month, 1)
    except (ValueError, TypeError):
        return HttpResponse('Invalid month', status=400)

    # Prefer transactions from upload for that month; else use stored P&L
    uploads = BankStatementUpload.objects.filter(user=request.user, month__year=year, month__month=month)
    transactions = BankTransaction.objects.filter(upload__in=uploads).select_related('label').order_by('date', 'id')
    if not transactions.exists():
        agm = MonthlyAGMAccounts.objects.filter(month=month_date).first()
        if agm and agm.summary_json:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="agm_accounts_{month_str}.csv"'
            # Minimal CSV from summary only
            w = csv.writer(response)
            w.writerow(['Singapore AGM Accounts Summary', month_str])
            for k, v in agm.summary_json.items():
                w.writerow([str(k), str(v)])
            return response
        return HttpResponse('No data for this month.', status=404)

    csv_content = build_agm_csv(month_date, list(transactions))
    response = HttpResponse(csv_content, content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="agm_accounts_{month_str}.csv"'
    return response


@login_required
def labels_manage(request):
    """List and quick-add labels (user-defined)."""
    labels = AccountLabel.objects.all().order_by('category', 'name')
    return render(request, 'accounting/labels.html', {'labels': labels})

