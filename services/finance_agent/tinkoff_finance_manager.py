"""
Vazus SuperGraph OS - Tinkoff / T-Bank Finance Manager
Handles Tinkoff OpenAPI token sync (ACCOUNT_ACCESS_LEVEL_READ_ONLY),
live RUB account balances, portfolio, transaction querying, offline CSV statement parsing,
debt liabilities tracking, and monthly cash flow deficit calculation.
"""

import sys
import os
import io
import json
import csv
import sqlite3
import requests
import urllib3
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(r"C:\vazus")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_PATH = r"C:\vazus\services\memory\vazus.db"
TOKEN_PATH = r"C:\vazus\tinkoff_token.txt"
TINKOFF_API_BASE = "https://invest-public-api.tinkoff.ru/rest/"

def init_finance_db(db_path=None):
    target_db = db_path if db_path is not None else DB_PATH
    conn = sqlite3.connect(target_db)
    cur = conn.cursor()
    
    # 1. finance_transactions table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS finance_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        external_id TEXT UNIQUE,
        timestamp TEXT,
        amount_rub REAL,
        category TEXT,
        merchant TEXT,
        operation_type TEXT,
        account_name TEXT,
        raw_json TEXT
    )
    """)

    cur.execute("PRAGMA table_info(finance_transactions)")
    cols = [col[1] for col in cur.fetchall()]
    if "external_id" not in cols:
        try:
            cur.execute("ALTER TABLE finance_transactions ADD COLUMN external_id TEXT UNIQUE")
        except Exception:
            pass

    # 2. user_liabilities table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_liabilities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE,
        total_remaining_rub REAL,
        monthly_payment_rub REAL,
        payments_left INTEGER,
        next_payment_date TEXT,
        category TEXT,
        credit_limit_rub REAL DEFAULT 0.0,
        used_credit_rub REAL DEFAULT 0.0
    )
    """)

    cur.execute("PRAGMA table_info(user_liabilities)")
    cols_liab = [col[1] for col in cur.fetchall()]
    if "credit_limit_rub" not in cols_liab:
        try:
            cur.execute("ALTER TABLE user_liabilities ADD COLUMN credit_limit_rub REAL DEFAULT 0.0")
        except Exception:
            pass
    if "used_credit_rub" not in cols_liab:
        try:
            cur.execute("ALTER TABLE user_liabilities ADD COLUMN used_credit_rub REAL DEFAULT 0.0")
        except Exception:
            pass

    # Seed default user_liabilities if empty
    count = cur.execute("SELECT COUNT(*) FROM user_liabilities").fetchone()[0]
    if count == 0:
        cur.executemany("""
        INSERT INTO user_liabilities (title, total_remaining_rub, monthly_payment_rub, payments_left, next_payment_date, category, credit_limit_rub, used_credit_rub)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            ("Кредит на покупку", 290000.0, 12700.0, 36, "16 сентября", "Кредит", 0.0, 0.0),
            ("Рассрочка: Покоритель Наташек 7.0", 9900.0, 3300.0, 3, "Ежемесячно", "Рассрочка", 0.0, 0.0),
            ("Рассрочка: Playerok", 4335.0, 1445.0, 3, "Ежемесячно", "Рассрочка", 0.0, 0.0),
            ("Кредитная карта Т-Банк Платинум", 45000.0, 3400.0, 0, "Ежемесячно", "Кредитная карта", 150000.0, 45000.0)
        ])
    else:
        # Ensure Credit Card entry exists
        cc_exists = cur.execute("SELECT COUNT(*) FROM user_liabilities WHERE category = 'Кредитная карта' OR title LIKE '%Кредитная%'").fetchone()[0]
        if cc_exists == 0:
            cur.execute("""
            INSERT INTO user_liabilities (title, total_remaining_rub, monthly_payment_rub, payments_left, next_payment_date, category, credit_limit_rub, used_credit_rub)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ("Кредитная карта Т-Банк Платинум", 45000.0, 3400.0, 0, "Ежемесячно", "Кредитная карта", 150000.0, 45000.0))

    conn.commit()
    conn.close()

class TinkoffFinanceManager:
    def __init__(self, api_token=None, db_path=None):
        """
        STRICT READ-ONLY ENFORCEMENT:
        Only read access to transaction history, balances, and categories.
        Writing/purchasing endpoints are strictly disallowed and technically impossible.
        """
        self.api_token = api_token or self._load_read_only_token()
        self.db_path = db_path or DB_PATH
        init_finance_db(self.db_path)

    def _load_read_only_token(self):
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, "r", encoding="utf-8") as f:
                return f.read().strip()
        return os.environ.get("TINKOFF_READONLY_TOKEN")

    def _parse_money(self, money_dict):
        if not money_dict:
            return 0.0
        units = float(money_dict.get("units", 0))
        nano = float(money_dict.get("nano", 0))
        return units + nano / 1e9

    def fetch_live_accounts(self):
        """Fetches live accounts via Tinkoff Invest REST API v2"""
        if not self.api_token:
            return []
        headers = {"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"}
        url = TINKOFF_API_BASE + "tinkoff.public.invest.api.contract.v1.UsersService/GetAccounts"
        try:
            res = requests.post(url, headers=headers, json={}, verify=False, timeout=10)
            if res.status_code == 200:
                return res.json().get("accounts", [])
        except Exception as e:
            print(f"⚠️ [Tinkoff API] Error fetching accounts: {e}")
        return []

    def fetch_live_balances_and_portfolio(self):
        """Returns total live RUB balances and portfolio positions across accounts"""
        accounts = self.fetch_live_accounts()
        if not accounts:
            return {"total_live_rub": 0.0, "accounts": []}

        headers = {"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"}
        total_rub = 0.0
        acc_details = []

        for acc in accounts:
            acc_id = acc["id"]
            acc_name = acc.get("name", "Account")
            access_level = acc.get("accessLevel", "UNKNOWN")

            url_pos = TINKOFF_API_BASE + "tinkoff.public.invest.api.contract.v1.OperationsService/GetPositions"
            rub_bal = 0.0
            try:
                res_pos = requests.post(url_pos, headers=headers, json={"accountId": acc_id}, verify=False, timeout=10)
                if res_pos.status_code == 200:
                    money_list = res_pos.json().get("money", [])
                    for m in money_list:
                        if m.get("currency", "").lower() == "rub":
                            rub_bal += self._parse_money(m)
            except Exception as e:
                print(f"⚠️ [Tinkoff API] Error fetching positions for account {acc_id}: {e}")

            total_rub += rub_bal
            acc_details.append({
                "account_id": acc_id,
                "name": acc_name,
                "access_level": access_level,
                "rub_balance": rub_bal
            })

        return {"total_live_rub": total_rub, "accounts": acc_details}

    def sync_live_transactions(self, days_back=90):
        """Syncs executed operations from Tinkoff Invest REST API into SQLite database"""
        accounts = self.fetch_live_accounts()
        if not accounts or not self.api_token:
            return 0

        headers = {"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"}
        from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00Z")
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:59Z")
        url_ops = TINKOFF_API_BASE + "tinkoff.public.invest.api.contract.v1.OperationsService/GetOperations"

        synced_count = 0
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        for acc in accounts:
            acc_id = acc["id"]
            acc_name = acc.get("name", "Tinkoff Account")
            body = {
                "accountId": acc_id,
                "from": from_date,
                "to": to_date,
                "state": "OPERATION_STATE_EXECUTED"
            }
            try:
                res = requests.post(url_ops, headers=headers, json=body, verify=False, timeout=10)
                if res.status_code == 200:
                    ops = res.json().get("operations", [])
                    for op in ops:
                        ext_id = str(op.get("id", ""))
                        ts = op.get("date", datetime.now(timezone.utc).isoformat())
                        pmt = self._parse_money(op.get("payment", {}))
                        type_str = op.get("type", "Операция")
                        amount = abs(pmt)
                        op_type = "DEBIT" if pmt < 0 else "CREDIT"
                        category = type_str

                        if ext_id:
                            cur.execute("""
                            INSERT OR IGNORE INTO finance_transactions 
                            (external_id, timestamp, amount_rub, category, merchant, operation_type, account_name, raw_json)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (ext_id, ts, amount, category, type_str, op_type, acc_name, json.dumps(op, ensure_ascii=False)))
                        else:
                            cur.execute("""
                            INSERT INTO finance_transactions 
                            (timestamp, amount_rub, category, merchant, operation_type, account_name, raw_json)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (ts, amount, category, type_str, op_type, acc_name, json.dumps(op, ensure_ascii=False)))
                        
                        if cur.rowcount > 0:
                            synced_count += 1
            except Exception as e:
                print(f"⚠️ [Tinkoff Sync Error] Account {acc_id}: {e}")

        conn.commit()
        conn.close()
        return synced_count

    def parse_csv_statement(self, file_path_or_content, account_name="Т-Банк Блэк") -> dict:
        """
        Parses offline Tinkoff / T-Bank CSV statements (UTF-8, UTF-8-SIG, CP1251 encodings),
        semicolon/comma delimiter auto-detection, maps columns to finance_transactions table,
        filters out non-successful operations, deduplicates entries, and returns parsing summary.
        """
        decoded_text = None
        if isinstance(file_path_or_content, str):
            is_file_path = file_path_or_content.lower().endswith('.csv') or '\\' in file_path_or_content or '/' in file_path_or_content
            if is_file_path and not os.path.exists(file_path_or_content):
                return {"status": "ERROR", "message": "File not found", "total_parsed": 0, "inserted_count": 0, "skipped_count": 0}
            if os.path.exists(file_path_or_content):
                encodings = ['utf-8-sig', 'utf-8', 'cp1251', 'windows-1251', 'latin1']
                with open(file_path_or_content, 'rb') as f:
                    raw_bytes = f.read()
                    for enc in encodings:
                        try:
                            decoded_text = raw_bytes.decode(enc)
                            break
                        except UnicodeDecodeError:
                            continue
                if decoded_text is None:
                    raise ValueError(f"Unable to decode file {file_path_or_content} with supported encodings.")
            else:
                decoded_text = str(file_path_or_content)
        else:
            decoded_text = str(file_path_or_content)

        f_io = io.StringIO(decoded_text)
        sample = decoded_text[:2048]
        delimiter = ';' if ';' in sample else ','

        reader = csv.DictReader(f_io, delimiter=delimiter)
        if not reader.fieldnames:
            return {"status": "ERROR", "message": "Empty or invalid CSV file", "total_parsed": 0, "inserted_count": 0, "skipped_count": 0}

        field_map = {}
        for name in reader.fieldnames:
            clean_name = name.strip().lower()
            if 'дата операции' in clean_name:
                field_map['date'] = name
            elif 'дата' in clean_name or 'date' in clean_name:
                if 'date' not in field_map:
                    field_map['date'] = name
            elif 'категория' in clean_name or 'category' in clean_name:
                field_map['category'] = name
            elif 'сумма' in clean_name or 'amount' in clean_name:
                if 'валюте' not in clean_name or 'amount' not in field_map:
                    if 'amount' not in field_map or 'операции' in clean_name:
                        field_map['amount'] = name
            elif any(k in clean_name for k in ['описание', 'наименование', 'description', 'торговая']):
                if 'merchant' not in field_map:
                    field_map['merchant'] = name
            elif 'статус' in clean_name or 'status' in clean_name:
                field_map['status'] = name

        parsed_count = 0
        inserted_count = 0
        skipped_count = 0
        total_income = 0.0
        total_expense = 0.0
        transactions = []

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        valid_statuses = {'OK', 'УСПЕШНО', 'SUCCESS', 'COMPLETED'}

        for row in reader:
            parsed_count += 1

            # Check operation status filter
            status_val = str(row.get(field_map.get('status', ''), '')).strip().upper()
            if status_val and status_val not in valid_statuses:
                skipped_count += 1
                continue

            # Parse amount
            raw_amount = str(row.get(field_map.get('amount', ''), '')).strip()
            if not raw_amount:
                skipped_count += 1
                continue

            clean_amount = raw_amount.replace('\xa0', '').replace(' ', '').replace('₽', '').replace('руб.', '').replace(',', '.')
            try:
                val = float(clean_amount)
            except ValueError:
                skipped_count += 1
                continue

            if val < 0:
                op_type = 'DEBIT'
                amount_rub = abs(val)
                total_expense += amount_rub
            else:
                op_type = 'CREDIT'
                amount_rub = val
                total_income += amount_rub

            # Parse date
            raw_date = str(row.get(field_map.get('date', ''), '')).strip()
            iso_ts = None
            date_formats = [
                "%d.%m.%Y %H:%M:%S",
                "%d.%m.%Y %H:%M",
                "%d.%m.%Y",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S"
            ]
            for df in date_formats:
                try:
                    dt = datetime.strptime(raw_date, df)
                    iso_ts = dt.isoformat()
                    break
                except ValueError:
                    continue

            if not iso_ts:
                iso_ts = datetime.now(timezone.utc).isoformat()

            category = str(row.get(field_map.get('category', ''), '')).strip() or "Другое"
            merchant = str(row.get(field_map.get('merchant', ''), '')).strip() or "Неизвестно"
            raw_json = json.dumps(row, ensure_ascii=False)

            # Deduplication check
            cur.execute("""
            SELECT id FROM finance_transactions 
            WHERE timestamp = ? AND amount_rub = ? AND merchant = ? AND operation_type = ?
            """, (iso_ts, amount_rub, merchant, op_type))
            if not cur.fetchone():
                cur.execute("""
                INSERT INTO finance_transactions (timestamp, amount_rub, category, merchant, operation_type, account_name, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (iso_ts, amount_rub, category, merchant, op_type, account_name, raw_json))
                inserted_count += 1
            else:
                skipped_count += 1

            transactions.append({
                "timestamp": iso_ts,
                "amount_rub": amount_rub,
                "category": category,
                "merchant": merchant,
                "operation_type": op_type,
                "account_name": account_name
            })

        conn.commit()
        conn.close()

        return {
            "status": "SUCCESS",
            "total_parsed": parsed_count,
            "inserted_count": inserted_count,
            "skipped_count": skipped_count,
            "total_income_rub": round(total_income, 2),
            "total_expense_rub": round(total_expense, 2),
            "transactions": transactions
        }

    def get_liabilities_summary(self):
        """
        Queries user_liabilities table and returns structured breakdown of debt liabilities,
        installment payments, and credit card limits.
        """
        init_finance_db(self.db_path)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute("SELECT * FROM user_liabilities").fetchall()
        conn.close()

        purchase_loan = None
        installments = []
        credit_cards = []
        total_debt = 0.0
        total_monthly_liabilities = 0.0

        for r in rows:
            row_dict = dict(r)
            cat = row_dict.get("category", "")
            title = row_dict.get("title", "")
            monthly = float(row_dict.get("monthly_payment_rub", 0.0))
            remaining = float(row_dict.get("total_remaining_rub", 0.0))
            
            total_monthly_liabilities += monthly
            total_debt += remaining

            if cat == "Кредитная карта" or "Кредитная" in title or "Платинум" in title:
                credit_limit = float(row_dict.get("credit_limit_rub", 0.0))
                used_credit = float(row_dict.get("used_credit_rub", remaining))
                row_dict["available_credit_rub"] = max(0.0, credit_limit - used_credit)
                credit_cards.append(row_dict)
            elif cat == "Рассрочка" or "Рассрочка" in title:
                installments.append(row_dict)
            elif cat == "Кредит" or title == "Кредит на покупку" or "Покупку" in title or ("Кредит" in title and "карта" not in title.lower()):
                purchase_loan = row_dict

        return {
            "total_debt_rub": total_debt,
            "total_monthly_liabilities_rub": total_monthly_liabilities,
            "purchase_loan": purchase_loan,
            "installments": installments,
            "credit_cards": credit_cards,
            "raw_items": [dict(r) for r in rows]
        }

    def compute_cash_flow_balance(self, monthly_income=None, monthly_expenses=None):
        """
        Computes monthly cash flow balance: Income - (Expenses + Monthly Liabilities).
        Determines DEFICIT or SURPLUS status and recommends freelance target revenue (>= 10 000 ₽).
        """
        liabilities_summary = self.get_liabilities_summary()

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        db_expense = cur.execute("SELECT SUM(amount_rub) FROM finance_transactions WHERE operation_type='DEBIT'").fetchone()[0] or 0.0
        db_income = cur.execute("SELECT SUM(amount_rub) FROM finance_transactions WHERE operation_type='CREDIT'").fetchone()[0] or 0.0
        conn.close()

        if monthly_income is None:
            monthly_income = db_income

        if monthly_expenses is None:
            monthly_expenses = db_expense

        monthly_liabilities = liabilities_summary["total_monthly_liabilities_rub"]
        total_outflow = monthly_expenses + monthly_liabilities
        net_cash_flow = monthly_income - total_outflow

        if net_cash_flow < 0:
            status = "DEFICIT"
            deficit_amount = abs(net_cash_flow)
            freelance_target = max(10000.0, deficit_amount)
            recommendation = (f"Monthly deficit of {deficit_amount:.2f} ₽ detected. "
                              f"Target R4 freelance revenue is {freelance_target:.2f} ₽/month to achieve balance.")
        else:
            status = "SURPLUS"
            deficit_amount = 0.0
            freelance_target = 0.0
            recommendation = (f"Monthly surplus of {net_cash_flow:.2f} ₽. "
                              f"Recommend allocating surplus to accelerate installment payoff.")

        return {
            "monthly_income_rub": monthly_income,
            "monthly_expenses_rub": monthly_expenses,
            "monthly_liabilities_rub": monthly_liabilities,
            "total_monthly_outflow_rub": total_outflow,
            "net_cash_flow_rub": net_cash_flow,
            "status": status,
            "deficit_amount_rub": deficit_amount,
            "freelance_target_revenue_rub": freelance_target,
            "recommendation": recommendation
        }

    def add_transaction(self, amount, category, merchant, op_type="DEBIT", account="Т-Банк Блэк"):
        """
        Logs a transaction into finance_transactions table
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        ts = datetime.now(timezone.utc).isoformat()
        cur.execute("""
        INSERT INTO finance_transactions (timestamp, amount_rub, category, merchant, operation_type, account_name)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (ts, amount, category, merchant, op_type, account))
        conn.commit()
        conn.close()
        print(f"💰 [Tinkoff Finance] Logged: {merchant} ({amount} RUB) [{category}]")

    def get_financial_summary(self):
        """
        Returns complete financial summary: income, expenses, liabilities, net cash flow, deficit target, and live accounts.
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        expenses = cur.execute("SELECT category, SUM(amount_rub) FROM finance_transactions WHERE operation_type='DEBIT' GROUP BY category").fetchall()
        total_expense = cur.execute("SELECT SUM(amount_rub) FROM finance_transactions WHERE operation_type='DEBIT'").fetchone()[0] or 0.0
        total_income = cur.execute("SELECT SUM(amount_rub) FROM finance_transactions WHERE operation_type='CREDIT'").fetchone()[0] or 0.0
        conn.close()

        liabilities = self.get_liabilities_summary()
        cash_flow = self.compute_cash_flow_balance(total_income, total_expense)
        live_data = self.fetch_live_balances_and_portfolio()

        return {
            "total_income_rub": cash_flow["monthly_income_rub"],
            "total_expense_rub": cash_flow["monthly_expenses_rub"],
            "monthly_liabilities_rub": liabilities["total_monthly_liabilities_rub"],
            "net_cash_flow_rub": cash_flow["net_cash_flow_rub"],
            "status": cash_flow["status"],
            "cash_flow_deficit_rub": cash_flow["deficit_amount_rub"],
            "freelance_target_revenue_rub": cash_flow["freelance_target_revenue_rub"],
            "live_balance_rub": live_data.get("total_live_rub", 0.0),
            "expenses_by_category": dict(expenses) if expenses else {},
            "liabilities_summary": liabilities,
            "cash_flow_details": cash_flow,
            "live_accounts": live_data.get("accounts", [])
        }

if __name__ == '__main__':
    print("=== Vazus SuperGraph OS - Tinkoff Finance Manager (R3) ===")
    mgr = TinkoffFinanceManager()
    
    # 1. Test live balances
    live_info = mgr.fetch_live_balances_and_portfolio()
    print(f"📊 Live RUB Portfolio Balance: {live_info.get('total_live_rub', 0.0):.2f} ₽")
    print(f"💳 Active Accounts: {len(live_info.get('accounts', []))}")
    
    # 2. Test live sync
    synced = mgr.sync_live_transactions(days_back=30)
    print(f"🔄 Synced Live Transactions: {synced}")

    # 3. Test CSV statement parsing
    sample_csv = (
        "Дата операции;Дата платежа;Номер карты;Статус;Сумма операции;Валюта операции;Категория;Описание\n"
        "01.08.2026 14:30:15;01.08.2026;*1234;OK;-1450,50;RUB;Продукты;ВкусВилл\n"
        "02.08.2026 10:15:00;02.08.2026;*1234;OK;-450,00;RUB;Транспорт;Метро\n"
        "03.08.2026 18:00:00;03.08.2026;*1234;OK;25000,00;RUB;Пополнение;Перевод по SBP\n"
        "03.08.2026 19:00:00;03.08.2026;*1234;FAILED;-5000,00;RUB;Переводы;Отклонено\n"
    )
    csv_res = mgr.parse_csv_statement(sample_csv)
    print(f"📄 CSV Statement Parsing Test: {csv_res.get('status')} (Inserted: {csv_res.get('inserted_count')}, Skipped: {csv_res.get('skipped_count')})")

    # 4. Test liabilities summary
    liab = mgr.get_liabilities_summary()
    print(f"📉 Total Debt Outstanding: {liab.get('total_debt_rub', 0.0):.2f} ₽")
    print(f"📅 Total Monthly Liabilities Outflow: {liab.get('total_monthly_liabilities_rub', 0.0):.2f} ₽")

    # 5. Test cash flow balance
    cf = mgr.compute_cash_flow_balance()
    print(f"💸 Monthly Net Cash Flow: {cf.get('net_cash_flow_rub', 0.0):.2f} ₽ [{cf.get('status')}]")
    print(f"🎯 Target Freelance Revenue: {cf.get('freelance_target_revenue_rub', 0.0):.2f} ₽")

    # 6. Full summary
    summary = mgr.get_financial_summary()
    print("✅ Full Financial Summary:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
