"""
Parse bank statement CSV and Excel spreadsheets with flexible column detection.
"""
import csv
import io
from datetime import datetime, date as date_cls
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dateutil.parser import parse as parse_date

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

# Common column name variants (case-insensitive)
DATE_ALIASES = ('date', 'transaction date', 'value date', 'posting date', 'trans date')
DESC_ALIASES = ('description', 'particulars', 'narration', 'details', 'transaction details', 'remarks')
REF_ALIASES = ('reference', 'ref', 'transaction ref', 'cheque no')
DEBIT_ALIASES = ('debit', 'withdrawal', 'dr', 'amount out')
CREDIT_ALIASES = ('credit', 'deposit', 'cr', 'amount in')
BALANCE_ALIASES = ('balance', 'running balance', 'balance after', 'closing balance')


def _normalize_header(name):
    return (name or '').strip().lower()


def _find_column(headers, aliases):
    norm = [_normalize_header(h) for h in headers]
    for a in aliases:
        if not a:
            continue
        for i, n in enumerate(norm):
            if not n:
                continue
            if a in n or n in a:
                return i
    return None


def _description_column_indices(headers):
    norm = [_normalize_header(h) for h in headers]
    idxs = []
    for i, n in enumerate(norm):
        if any(a in n for a in DESC_ALIASES):
            idxs.append(i)
    return sorted(idxs)


def _gather_description(row, desc_indices):
    if not desc_indices:
        return ''
    parts = []
    for j in desc_indices:
        cell = row[j].strip() if j < len(row) else ''
        if cell:
            parts.append(cell)
    return (' '.join(parts))[:512]


def _parse_amount(val):
    if val is None or (isinstance(val, str) and not val.strip()):
        return Decimal('0')
    s = str(val).strip().replace(',', '')
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal('0')


def _parse_date(val):
    if not val:
        return None
    try:
        return parse_date(str(val).strip()).date()
    except (ValueError, TypeError):
        return None


def _excel_cell_to_str(val):
    """Turn pandas / xlrd cell values into CSV-like strings."""
    if val is None:
        return ''
    if pd is not None:
        try:
            if pd.isna(val):
                return ''
        except (TypeError, ValueError):
            pass
        if hasattr(val, 'to_pydatetime'):
            try:
                dt = val.to_pydatetime()
                if isinstance(dt, datetime):
                    return dt.date().strftime('%Y-%m-%d')
            except Exception:
                pass
    if isinstance(val, datetime):
        return val.date().strftime('%Y-%m-%d')
    if isinstance(val, date_cls):
        return val.strftime('%Y-%m-%d')
    # Excel numbers/float amounts
    if isinstance(val, bool):
        return str(val)
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
        return str(val)
    if isinstance(val, int):
        return str(val)
    return str(val).strip()


def _detect_header_row(rows, max_scan=60):
    """
    Locate the row containing column headings (handles bank preamble lines above the table).
    """
    if not rows:
        return None
    for i, row in enumerate(rows[:max_scan]):
        if not row or not any((c or '').strip() for c in row):
            continue
        idx_date = _find_column(row, DATE_ALIASES)
        if idx_date is None:
            continue
        idx_debit = _find_column(row, DEBIT_ALIASES)
        idx_credit = _find_column(row, CREDIT_ALIASES)
        idx_bal = _find_column(row, BALANCE_ALIASES)
        if idx_debit is not None or idx_credit is not None or idx_bal is not None:
            return i
        for _, h in enumerate(row):
            if _normalize_header(h) in ('amount', 'transaction amount', 'sum'):
                return i
    return None


def parse_statement_rows(rows):
    """
    Parse a bank statement represented as rows of string cells (header auto-detected).
    Returns list of dicts with keys: date, description, reference, debit, credit, balance_after.
    """
    if not rows:
        return []

    hdr_i = _detect_header_row(rows)
    if hdr_i is None:
        hdr_i = 0

    headers = [str(c).strip() for c in rows[hdr_i]]

    idx_date = _find_column(headers, DATE_ALIASES)
    idx_desc_cols = _description_column_indices(headers)
    idx_ref = _find_column(headers, REF_ALIASES)
    idx_debit = _find_column(headers, DEBIT_ALIASES)
    idx_credit = _find_column(headers, CREDIT_ALIASES)
    idx_balance = _find_column(headers, BALANCE_ALIASES)

    if idx_desc_cols:
        idx_desc = idx_desc_cols[0]
    else:
        idx_desc = _find_column(headers, DESC_ALIASES)

    idx_amount_single = None
    if idx_debit is None and idx_credit is None:
        for i, h in enumerate(headers):
            if _normalize_header(h) in ('amount', 'transaction amount', 'sum'):
                idx_amount_single = i
                break

    max_idx_candidates = [
        idx_date, idx_desc, idx_ref,
        idx_debit, idx_credit, idx_balance, idx_amount_single,
    ]
    if idx_desc_cols:
        max_idx_candidates.extend(idx_desc_cols)
    finite_indices = [i for i in max_idx_candidates if i is not None]
    max_idx_needed = max(finite_indices) if finite_indices else 0

    result = []
    for row_raw in rows[hdr_i + 1:]:
        base = [(str(c).strip() if c is not None else '') for c in list(row_raw)]
        while len(base) <= max_idx_needed:
            base.append('')
        row = base

        desc_val = _gather_description(row, idx_desc_cols) if idx_desc_cols else ''
        if not desc_val and idx_desc is not None and idx_desc < len(row):
            desc_val = row[idx_desc].strip()[:512]

        date_val = row[idx_date] if idx_date is not None and idx_date < len(row) else None
        ref_val = row[idx_ref] if idx_ref is not None and idx_ref < len(row) else ''
        debit_val = row[idx_debit] if idx_debit is not None and idx_debit < len(row) else '0'
        credit_val = row[idx_credit] if idx_credit is not None and idx_credit < len(row) else '0'
        balance_val = row[idx_balance] if idx_balance is not None and idx_balance < len(row) else None

        date_parsed = _parse_date(date_val)
        if not date_parsed:
            continue

        if idx_amount_single is not None and idx_amount_single < len(row):
            amt = _parse_amount(row[idx_amount_single])
            debit = -amt if amt < 0 else Decimal('0')
            credit = amt if amt > 0 else Decimal('0')
        else:
            debit = _parse_amount(debit_val)
            credit = _parse_amount(credit_val)
            if idx_debit is None and idx_credit is not None:
                amt = credit
                debit = -amt if amt < 0 else Decimal('0')
                credit = amt if amt > 0 else Decimal('0')

        balance_after = None
        if balance_val is not None and str(balance_val).strip():
            balance_after = _parse_amount(balance_val)

        result.append({
            'date': date_parsed,
            'description': (desc_val or '').strip()[:512],
            'reference': (ref_val or '').strip()[:128],
            'debit': debit,
            'credit': credit,
            'balance_after': balance_after,
        })

    return result


def parse_bank_statement_csv(file_or_path):
    """
    Parse a bank statement CSV. Returns list of dicts with keys:
    date, description, reference, debit, credit, balance_after.
    """
    if hasattr(file_or_path, 'read'):
        content = file_or_path.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
    else:
        with open(file_or_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

    reader = csv.reader(io.StringIO(content))
    rows = [[c.strip() for c in row] for row in reader]
    return parse_statement_rows(rows)


def parse_bank_statement_spreadsheet(path):
    """
    Read .xls (xlrd) or .xlsx (openpyxl) and return the same row dicts as CSV parsing.

    Raises ImportError if pandas or engines are missing, ValueError on unknown extension.
    """
    if pd is None:
        raise ImportError('pandas is required for Excel uploads')

    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == '.xls':
        kwargs = {'engine': 'xlrd'}
    elif suffix == '.xlsx':
        kwargs = {'engine': 'openpyxl'}
    else:
        raise ValueError(f'Unsupported spreadsheet type: {suffix}')

    df = pd.read_excel(path, header=None, dtype=object)
    rows = []
    for i in range(len(df)):
        cells = [_excel_cell_to_str(x) for x in df.iloc[i].tolist()]
        rows.append(cells)
    return parse_statement_rows(rows)


def parse_bank_statement_file(path_or_uploaded_field):
    """
    Dispatch CSV vs Excel based on filename extension.

    ``path_or_uploaded_field`` may be a filesystem path string or Django FieldFile (.path).
    """
    path = getattr(path_or_uploaded_field, 'path', path_or_uploaded_field)
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in ('.xls', '.xlsx'):
        return parse_bank_statement_spreadsheet(path)
    return parse_bank_statement_csv(path)

