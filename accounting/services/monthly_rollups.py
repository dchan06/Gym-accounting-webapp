"""Recompute stored MonthlyMetrics, MonthlyPL, and AGM summary from live transactions."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.db import transaction

from accounting.models import BankTransaction, MonthlyAGMAccounts, MonthlyMetrics, MonthlyPL
from accounting.services.agm_export import (
    build_metrics_from_transactions,
    build_pl_from_transactions,
)


def sync_rollups_for_user_month(month_first_day, user: User):
    """
    Aggregate all transactions for uploads owned by ``user`` in ``month_first_day``
    into MonthlyMetrics, MonthlyPL rows, and MonthlyAGMAccounts.summary_json.

    Drops MonthlyPL rows for that month whose labels no longer have a non‑zero balance.
    """
    txs = BankTransaction.objects.filter(
        upload__month=month_first_day,
        upload__user=user,
    ).select_related('label')
    lst = list(txs)

    pl = build_pl_from_transactions(lst)
    metrics_data = build_metrics_from_transactions(lst)
    rev = metrics_data.get('revenue_total', Decimal('0'))
    exp = metrics_data.get('expenses_total', Decimal('0'))

    with transaction.atomic():
        MonthlyMetrics.objects.update_or_create(
            month=month_first_day,
            defaults={
                'revenue_total': rev,
                'expenses_total': exp,
            },
        )
        MonthlyAGMAccounts.objects.update_or_create(
            month=month_first_day,
            defaults={'summary_json': dict(pl)},
        )

        present = {lid for lid, amt in pl.items() if amt != Decimal('0')}
        if not present:
            MonthlyPL.objects.filter(month=month_first_day).delete()
        else:
            MonthlyPL.objects.filter(month=month_first_day).exclude(
                label_id__in=present,
            ).delete()
            for label_id, amount in pl.items():
                if amount == Decimal('0'):
                    continue
                MonthlyPL.objects.update_or_create(
                    month=month_first_day,
                    label_id=label_id,
                    defaults={'amount': amount},
                )
