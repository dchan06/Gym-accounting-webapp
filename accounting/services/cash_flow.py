"""
Normalize bank CSV conventions to a single signed cash impact on the account.

Many Singapore bank exports use one column (often labelled Debit) with *signed*
amounts: negative = money out, positive = money in, credit = 0.

Classical CSVs use: money out as debit > 0, money in as credit > 0.

BankStatementUpload.signed_debit_column is set at import when any parsed row has
debit < 0. For debit-only rows with debit > 0, that flag disambiguates inflow vs outflow.
"""
from decimal import Decimal


def net_cash_impact(transaction):
    """
    Net impact on bank balance: positive = money in, negative = money out.
    """
    d = transaction.debit or Decimal('0')
    c = transaction.credit or Decimal('0')
    if c != 0 or d == 0:
        return c - d
    if d < 0:
        return d
    upload = transaction.upload
    signed = getattr(upload, 'signed_debit_column', False)
    return d if signed else -d
