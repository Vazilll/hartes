"""
Vazus SuperGraph OS - Offline Bank Statement Parser
Parses exported Tinkoff CSV/PDF monthly statements locally without online network requests
"""

import sys
import os
import csv
import sqlite3
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(r"C:\vazus")
from vazus_core.tinkoff_finance_manager import init_finance_db, DB_PATH

def parse_tinkoff_csv_statement(csv_path, db_path=None):
    """
    Parses Tinkoff CSV statement locally and imports into vazus.db or target_db
    """
    print(f"📄 [Statement Parser] Parsing Tinkoff CSV file: {csv_path}...")
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return 0

    target_db = db_path if db_path is not None else getattr(sys.modules[__name__], "DB_PATH", DB_PATH)
    init_finance_db(target_db)
    conn = sqlite3.connect(target_db)
    cur = conn.cursor()

    count = 0
    try:
        with open(csv_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                ts = row.get('Дата операции', datetime.now().isoformat())
                amount = float(row.get('Сумма операции', '0').replace(',', '.').replace(' ', ''))
                category = row.get('Категория', 'Прочее')
                merchant = row.get('Описание', 'Неизвестно')
                op_type = 'DEBIT' if amount < 0 else 'CREDIT'
                
                cur.execute("""
                INSERT INTO finance_transactions (timestamp, amount_rub, category, merchant, operation_type, account_name)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (ts, abs(amount), category, merchant, op_type, "Т-Банк (Офлайн Выписка)"))
                count += 1

        conn.commit()
        print(f"✅ Successfully parsed {count} transactions from CSV!")
    except Exception as e:
        print(f"Error parsing CSV: {e}")
    finally:
        conn.close()

    return count

if __name__ == '__main__':
    print("Offline Bank Statement Parser initialized.")
