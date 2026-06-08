"""
Build P&L and metrics from transactions; export CSV formatted for Singapore AGM / annual accounts.
"""
import csv
import io
from collections import defaultdict
from decimal import Decimal
from datetime import date

from accounting.models import AccountLabel
from accounting.services.cash_flow import net_cash_impact


def build_pl_from_transactions(transactions):
    """Aggregate transactions by label into P&L: { label_id: total_amount }. """
    pl = defaultdict(Decimal)
    for t in transactions:
        if not t.label_id:
            continue
        amt = net_cash_impact(t)
        if amt != 0:
            pl[t.label_id] += amt
    return dict(pl)


def build_metrics_from_transactions(transactions):
    """Compute revenue_total, expenses_total from labelled transactions."""
    revenue = Decimal('0')
    expenses = Decimal('0')
    for t in transactions:
        if not t.label_id:
            continue
        cat = t.label.category if hasattr(t.label, 'category') else None
        amt = net_cash_impact(t)
        if cat == 'revenue':
            revenue += amt
        elif cat == 'expense':
            # Net expense: outflows negative; store as positive total spend
            expenses += -amt
    return {'revenue_total': revenue, 'expenses_total': expenses}


def build_agm_csv(month, transactions, include_guidance_headers=True):
    """
    Build a CSV suitable for Singapore yearly AGM / annual return style accounts.
    Format: date, description, reference, amount, category, label_code, label_name.
    Summary section at top: Revenue by category, Expenses by category, Net.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    if include_guidance_headers:
        writer.writerow(['Singapore AGM / Annual Return - Accounts Summary'])
        writer.writerow(['Period', month.strftime('%B %Y')])
        writer.writerow([])

    pl = build_pl_from_transactions(transactions)
    label_map = {}
    cats = {}
    codes = {}
    if pl:
        label_map = dict(AccountLabel.objects.filter(id__in=pl.keys()).values_list('id', 'name'))
        codes = dict(AccountLabel.objects.filter(id__in=pl.keys()).values_list('id', 'code'))
        cats = dict(AccountLabel.objects.filter(id__in=pl.keys()).values_list('id', 'category'))

    # Net revenue (can be negative if refunds exceed receipts); net expense as positive number
    revenue_total = sum(
        pl[lid] for lid in pl if cats.get(lid) == 'revenue'
    )
    expense_total = sum(
        -pl[lid] for lid in pl if cats.get(lid) == 'expense'
    )
    net = revenue_total - expense_total

    writer.writerow(['Summary'])
    writer.writerow(['Total Revenue', str(revenue_total)])
    writer.writerow(['Total Expenses', str(abs(expense_total))])
    writer.writerow(['Net Profit/(Loss)', str(net)])
    writer.writerow([])

    writer.writerow(['Revenue by Category'])
    for lid in sorted(pl.keys(), key=lambda x: (-pl.get(x, 0), label_map.get(x, ''))):
        if cats.get(lid) == 'revenue' and pl[lid] != 0:
            writer.writerow([label_map.get(lid, ''), codes.get(lid, ''), str(pl[lid])])
    writer.writerow([])

    writer.writerow(['Expenses by Category'])
    for lid in sorted(pl.keys(), key=lambda x: (pl.get(x, 0), label_map.get(x, ''))):
        if cats.get(lid) == 'expense' and pl[lid] != 0:
            writer.writerow([label_map.get(lid, ''), codes.get(lid, ''), str(-pl[lid])])
    writer.writerow([])

    writer.writerow(['Transaction Listing (Tax-Ready)'])
    writer.writerow(['Date', 'Description', 'Reference', 'Debit', 'Credit', 'Category', 'Label Code', 'Label Name'])
    for t in sorted(transactions, key=lambda x: (x.date, x.id)):
        label_name = t.label.name if t.label else ''
        label_code = (t.label.code or '') if t.label else ''
        category = (t.label.get_category_display() or '') if t.label else ''
        writer.writerow([
            t.date.isoformat() if t.date else '',
            (t.description or '')[:200],
            t.reference or '',
            str(t.debit),
            str(t.credit),
            category,
            label_code,
            label_name,
        ])

    return output.getvalue()
