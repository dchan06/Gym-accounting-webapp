# Gym Accounting Webapp

Accounting software for gyms: upload bank statements, label transactions (with AI suggestions), and export Singapore AGM-ready CSVs.

## Stack

- **Backend:** Django (Python), local MySQL

If you use **Python 3.14**, install **Django 5.2+** (see `requirements.txt`). Django 4.2’s admin can fail on 3.14 with `AttributeError: 'super' object has no attribute 'dicts'` when copying template context; upgrading Django fixes that.
- **Frontend:** HTML templates, minimal CSS
- **ML:** scikit-learn (TF-IDF + LogisticRegression) for label suggestions from your past labels; Singapore tax guidance for advice

## Setup

1. **Create virtualenv and install dependencies**

   ```bash
   python3 -m venv venv
   source venv/bin/activate   # or `venv\Scripts\activate` on Windows
   pip install -r requirements.txt
   ```

2. **MySQL**

   **Run these commands inside the MySQL client** (not in your normal terminal). Start MySQL, then paste the SQL:

   ```bash
   mysql -u root -p
   ```

   Enter your MySQL root password when prompted. Then at the `mysql>` prompt run:

   ```sql
   CREATE DATABASE gym_accounting CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

   (Optional: create a dedicated user and grant access, then set `DB_USER` and `DB_PASSWORD` in `.env`.)

3. **Database password (if MySQL root has a password)**

   If you see `Access denied for user 'root'@'localhost' (using password: NO)`, Django is not sending a password. Either:

   - **Option A — use a `.env` file (recommended):**
     ```bash
     cp .env.example .env
     ```
     Edit `.env` and set `DB_PASSWORD=your_mysql_root_password`.

   - **Option B — export before running Django:**
     ```bash
     export DB_PASSWORD=your_mysql_root_password
     python manage.py migrate
     ```

4. **Migrations and run**

   ```bash
   python manage.py migrate
   python manage.py createsuperuser   # for admin + login
   python manage.py runserver
   ```

   Open http://127.0.0.1:8000/

## User flow

1. **Upload** — Upload a bank statement CSV (date, description, debit, credit; optional reference/balance). Column names are detected automatically.
2. **AI tagging** — On upload, the app suggests labels from ML (trained on your past labels) and applies the top suggestion. You can change any label and add notes.
3. **Singapore tax advice** — The labelling page shows short guidance (revenue vs expense, deductibility) aligned with typical Singapore business tax treatment.
4. **Save** — When all rows are labelled (or as needed), click “Save labelled data” to update **Monthly metrics**, **Monthly P&L**, and stored **AGM accounts**.
5. **Metrics / P&L** — View monthly metrics and P&L by label.
6. **Download AGM CSV** — From the Metrics page, download a CSV for the chosen month, formatted for Singapore yearly AGM / annual return style (summary + transaction listing by category).

## Features

- **Metrics:** Monthly revenue, expenses, net (from saved labelled data).
- **P&L:** Monthly breakdown by account label (revenue/expense categories).
- **AGM CSV:** Summary (revenue/expenses/net), revenue by category, expenses by category, and full transaction listing with labels for tax-ready use.
- **Labels:** Managed in Admin (or Labels page); default labels (e.g. Membership, Rent, Utilities, Salaries) are created by migration.
- **ML:** Learns from your chosen labels on transaction descriptions; prioritises user-defined labels and past choices.

## Project layout

- `gym_accounting/` — Django project settings and URLs
- `accounting/` — Main app: models, views, forms, `services/` (CSV parse, ML, AGM export)
- `templates/` — Base and accounting templates
- `media/` — Uploaded statements (created at runtime)
- `requirements.txt` — Python dependencies

No cloud or production database setup is included; the app is intended for local MySQL as specified.
