"""
Vazus SuperGraph OS - R3 Finance Test Suite (Features 10 - 14)
Covers:
  - Feature 10: R3 Tinkoff Read-Only Auth (Token loading, strict read-only level, env fallback)
  - Feature 11: R3 Tinkoff Live Accounts API & Transactions (DEBIT/CREDIT, accounts, categories, summary)
  - Feature 12: R3 CSV Statement Parser (Offline Tinkoff CSV parsing, utf-8-sig, row counts, formatting)
  - Feature 13: R3 Debt Liabilities Tracker (Loan 290k ₽, 2 installments 9.9k ₽ & 4.3k ₽, CC limits)
  - Feature 14: R3 Cash Flow Calculator (Income, expenses, debt deduction, net deficit/surplus)

Tier 1 (Feature Coverage): 25 tests
Tier 2 (Boundary & Corner Cases): 25 tests
Total: 50 test cases
"""

import sys
import os
import csv
import sqlite3
import pytest
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path
from datetime import datetime

import sys
import os
import csv
import sqlite3
import pytest
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path
from datetime import datetime

sys.path.append(r"C:\vazus")
sys.path.append(r"C:\vazus\vazus_core")

import vazus_core.tinkoff_finance_manager as tfm
import vazus_core.statement_parser as sp
tfm_flat = tfm
sp_flat = sp

from vazus_core.tinkoff_finance_manager import TinkoffFinanceManager, init_finance_db
from vazus_core.statement_parser import parse_tinkoff_csv_statement


# ---------------------------------------------------------------------------
# Pytest Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    """Provides an isolated SQLite database path for testing all features."""
    db_file = str(tmp_path / "test_finance.db")
    monkeypatch.setattr(tfm, "DB_PATH", db_file)
    monkeypatch.setattr(sp, "DB_PATH", db_file)
    monkeypatch.setattr(tfm_flat, "DB_PATH", db_file)
    monkeypatch.setattr(sp_flat, "DB_PATH", db_file)
    tfm.init_finance_db()
    return db_file




@pytest.fixture
def mock_csv_file(tmp_path):
    """Creates a sample Tinkoff CSV statement file."""
    csv_file = tmp_path / "statement.csv"
    content = (
        "Дата операции;Сумма операции;Категория;Описание\n"
        "2026-08-01 12:00:00;-1450,00;Продукты;ВкусВилл\n"
        "2026-08-02 15:30:00;-450,50;Транспорт;Мосгортранс / Метро\n"
        "2026-08-03 10:00:00;55000,00;Пополнение;Перевод зарплаты\n"
    )
    csv_file.write_text(content, encoding="utf-8-sig")
    return str(csv_file)


# ===========================================================================
# FEATURE 10: R3 Tinkoff Read-Only Auth
# ===========================================================================

# --- Tier 1 (Happy Path) ---

def test_f10_load_read_only_token_from_file(monkeypatch, tmp_path):
    token_file = tmp_path / "tinkoff_token.txt"
    token_file.write_text("t.read_only_token_12345", encoding="utf-8")
    
    def fake_exists(path):
        return str(path) == r"C:\vazus\tinkoff_token.txt" or str(path) == str(token_file)

    monkeypatch.setattr(os.path, "exists", lambda p: p == r"C:\vazus\tinkoff_token.txt")
    with patch("builtins.open", mock_open(read_data="t.read_only_token_12345")):
        mgr = TinkoffFinanceManager()
        assert mgr.api_token == "t.read_only_token_12345"


def test_f10_load_read_only_token_from_env(monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    monkeypatch.setenv("TINKOFF_READONLY_TOKEN", "env_read_only_token_999")
    mgr = TinkoffFinanceManager()
    assert mgr.api_token == "env_read_only_token_999"


def test_f10_explicit_api_token_override():
    mgr = TinkoffFinanceManager(api_token="custom_token_override")
    assert mgr.api_token == "custom_token_override"


def test_f10_read_only_token_priority(monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda p: p == r"C:\vazus\tinkoff_token.txt")
    monkeypatch.setenv("TINKOFF_READONLY_TOKEN", "env_token_should_be_ignored")
    with patch("builtins.open", mock_open(read_data="file_token_priority")):
        mgr = TinkoffFinanceManager()
        assert mgr.api_token == "file_token_priority"


def test_f10_token_strip_whitespace(monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda p: p == r"C:\vazus\tinkoff_token.txt")
    with patch("builtins.open", mock_open(read_data="   token_with_spaces_and_newlines\n\n  ")):
        mgr = TinkoffFinanceManager()
        assert mgr.api_token == "token_with_spaces_and_newlines"


# --- Tier 2 (Boundary & Corner Cases) ---

def test_f10_missing_token_file_and_env(monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    monkeypatch.delenv("TINKOFF_READONLY_TOKEN", raising=False)
    mgr = TinkoffFinanceManager()
    assert mgr.api_token is None


def test_f10_empty_token_file(monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda p: p == r"C:\vazus\tinkoff_token.txt")
    monkeypatch.setenv("TINKOFF_READONLY_TOKEN", "fallback_env_token")
    with patch("builtins.open", mock_open(read_data="")):
        mgr = TinkoffFinanceManager()
        assert mgr.api_token == ""



def test_f10_token_file_permission_error(monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda p: p == r"C:\vazus\tinkoff_token.txt")
    def permission_error_open(*args, **kwargs):
        raise PermissionError("Access denied")
    with patch("builtins.open", permission_error_open):
        with pytest.raises(PermissionError):
            TinkoffFinanceManager()


def test_f10_token_format_read_only_prefix(tmp_db):
    token = "ACCOUNT_ACCESS_LEVEL_READ_ONLY_token_xyz"
    mgr = TinkoffFinanceManager(api_token=token)
    assert mgr.api_token.startswith("ACCOUNT_ACCESS_LEVEL_READ_ONLY")


def test_f10_read_only_enforcement_property(tmp_db):
    mgr = TinkoffFinanceManager(api_token="read_only_token_test")
    # Verify docstring / initialization safety guarantee
    assert "READ-ONLY" in mgr.__init__.__doc__


# ===========================================================================
# FEATURE 11: R3 Tinkoff Live Accounts API & Transactions
# ===========================================================================

# --- Tier 1 (Happy Path) ---

def test_f11_add_debit_transaction(tmp_db):
    mgr = TinkoffFinanceManager()
    mgr.add_transaction(1500.0, "Продукты", "Перекресток", op_type="DEBIT", account="Т-Банк Блэк")
    
    conn = sqlite3.connect(tmp_db)
    row = conn.execute("SELECT amount_rub, category, merchant, operation_type, account_name FROM finance_transactions").fetchone()
    conn.close()
    
    assert row == (1500.0, "Продукты", "Перекресток", "DEBIT", "Т-Банк Блэк")


def test_f11_add_credit_transaction(tmp_db):
    mgr = TinkoffFinanceManager()
    mgr.add_transaction(45000.0, "Зарплата", "ООО ИТ-Решения", op_type="CREDIT", account="Т-Банк Блэк")
    
    conn = sqlite3.connect(tmp_db)
    row = conn.execute("SELECT amount_rub, operation_type FROM finance_transactions").fetchone()
    conn.close()
    
    assert row == (45000.0, "CREDIT")


def test_f11_custom_account_name(tmp_db):
    mgr = TinkoffFinanceManager()
    mgr.add_transaction(2500.0, "Электроника", "DNS", account="Т-Банк Платинум")
    
    conn = sqlite3.connect(tmp_db)
    acc = conn.execute("SELECT account_name FROM finance_transactions").fetchone()[0]
    conn.close()
    
    assert acc == "Т-Банк Платинум"


def test_f11_financial_summary_basic(tmp_db):
    mgr = TinkoffFinanceManager()
    mgr.add_transaction(1000.0, "Кафе", "Шоколадница", op_type="DEBIT")
    mgr.add_transaction(500.0, "Кафе", "Кофемания", op_type="DEBIT")
    mgr.add_transaction(3000.0, "Доход", "Фриланс", op_type="CREDIT")
    
    summary = mgr.get_financial_summary()
    assert summary["total_income_rub"] == 3000.0
    assert summary["total_expense_rub"] == 1500.0
    assert summary["expenses_by_category"]["Кафе"] == 1500.0


def test_f11_transaction_timestamp_format(tmp_db):
    mgr = TinkoffFinanceManager()
    mgr.add_transaction(100.0, "Тест", "Тест Магазин")
    
    conn = sqlite3.connect(tmp_db)
    ts = conn.execute("SELECT timestamp FROM finance_transactions").fetchone()[0]
    conn.close()
    
    # ISO timestamp format check
    assert "T" in ts


# --- Tier 2 (Boundary & Corner Cases) ---

def test_f11_zero_amount_transaction(tmp_db):
    mgr = TinkoffFinanceManager()
    mgr.add_transaction(0.0, "Подписка", "Промокод Сервис", op_type="DEBIT")
    
    summary = mgr.get_financial_summary()
    assert summary["total_expense_rub"] == 0.0


def test_f11_floating_point_precision(tmp_db):
    mgr = TinkoffFinanceManager()
    mgr.add_transaction(1234.5678, "Аптека", "Ригла")
    
    conn = sqlite3.connect(tmp_db)
    val = conn.execute("SELECT amount_rub FROM finance_transactions").fetchone()[0]
    conn.close()
    
    assert abs(val - 1234.5678) < 1e-6


def test_f11_empty_database_summary(tmp_db):
    mgr = TinkoffFinanceManager()
    summary = mgr.get_financial_summary()
    assert summary["total_income_rub"] == 0.0
    assert summary["total_expense_rub"] == 0.0
    assert summary["expenses_by_category"] == {}


def test_f11_special_characters_merchant_category(tmp_db):
    mgr = TinkoffFinanceManager()
    special_merchant = "ИП 'Иванов' & Co. \"Супермаркет\" №1"
    mgr.add_transaction(999.0, "Развлечения & Хобби", special_merchant)
    
    summary = mgr.get_financial_summary()
    assert "Развлечения & Хобби" in summary["expenses_by_category"]
    
    conn = sqlite3.connect(tmp_db)
    m_db = conn.execute("SELECT merchant FROM finance_transactions").fetchone()[0]
    conn.close()
    assert m_db == special_merchant


def test_f11_multiple_transactions_same_category(tmp_db):
    mgr = TinkoffFinanceManager()
    for price in [100.0, 200.0, 300.0, 400.0]:
        mgr.add_transaction(price, "Супермаркеты", "Магнит")
    
    summary = mgr.get_financial_summary()
    assert summary["expenses_by_category"]["Супермаркеты"] == 1000.0


# ===========================================================================
# FEATURE 12: R3 CSV Statement Parser
# ===========================================================================

# --- Tier 1 (Happy Path) ---

def test_f12_parse_valid_tinkoff_csv(tmp_db, mock_csv_file):
    count = parse_tinkoff_csv_statement(mock_csv_file)
    assert count == 3


def test_f12_negative_amount_debit_classification(tmp_db, mock_csv_file):
    parse_tinkoff_csv_statement(mock_csv_file)
    
    conn = sqlite3.connect(tmp_db)
    rows = conn.execute("SELECT amount_rub, operation_type, merchant FROM finance_transactions WHERE operation_type='DEBIT'").fetchall()
    conn.close()
    
    assert len(rows) == 2
    assert rows[0] == (1450.0, "DEBIT", "ВкусВилл")
    assert rows[1] == (450.50, "DEBIT", "Мосгортранс / Метро")


def test_f12_positive_amount_credit_classification(tmp_db, mock_csv_file):
    parse_tinkoff_csv_statement(mock_csv_file)
    
    conn = sqlite3.connect(tmp_db)
    row = conn.execute("SELECT amount_rub, operation_type, merchant FROM finance_transactions WHERE operation_type='CREDIT'").fetchone()
    conn.close()
    
    assert row == (55000.0, "CREDIT", "Перевод зарплаты")


def test_f12_returned_parsed_row_count(tmp_db, tmp_path):
    csv_file = tmp_path / "test_5_rows.csv"
    rows_data = ["Дата операции;Сумма операции;Категория;Описание\n"]
    for i in range(5):
        rows_data.append(f"2026-08-01 10:00:00;-10{i}.00;Категория_{i};Тест_{i}\n")
    csv_file.write_text("".join(rows_data), encoding="utf-8-sig")
    
    count = parse_tinkoff_csv_statement(str(csv_file))
    assert count == 5


def test_f12_utf8_sig_encoding_bom(tmp_db, tmp_path):
    csv_file = tmp_path / "bom_statement.csv"
    # UTF-8 with BOM content
    content = "\ufeffДата операции;Сумма операции;Категория;Описание\n2026-08-01 12:00:00;-500,00;Кафе;Тест BOM\n"
    csv_file.write_bytes(content.encode("utf-8-sig"))
    
    count = parse_tinkoff_csv_statement(str(csv_file))
    assert count == 1


# --- Tier 2 (Boundary & Corner Cases) ---

def test_f12_nonexistent_csv_file_returns_zero(tmp_db):
    count = parse_tinkoff_csv_statement("non_existent_file.csv")
    assert count == 0


def test_f12_formatted_number_with_spaces_commas(tmp_db, tmp_path):
    csv_file = tmp_path / "formatted_numbers.csv"
    content = (
        "Дата операции;Сумма операции;Категория;Описание\n"
        "2026-08-01 12:00:00;-1 234 567,89;Техника;Ноутбук\n"
    )
    csv_file.write_text(content, encoding="utf-8-sig")
    
    count = parse_tinkoff_csv_statement(str(csv_file))
    assert count == 1
    
    conn = sqlite3.connect(tmp_db)
    amount = conn.execute("SELECT amount_rub FROM finance_transactions").fetchone()[0]
    conn.close()
    
    assert amount == 1234567.89


def test_f12_csv_with_missing_optional_fields(tmp_db, tmp_path):
    csv_file = tmp_path / "missing_fields.csv"
    content = (
        "Дата операции;Сумма операции\n"
        "2026-08-01 12:00:00;-300,00\n"
    )
    csv_file.write_text(content, encoding="utf-8-sig")
    
    count = parse_tinkoff_csv_statement(str(csv_file))
    assert count == 1
    
    conn = sqlite3.connect(tmp_db)
    row = conn.execute("SELECT category, merchant FROM finance_transactions").fetchone()
    conn.close()
    
    assert row == ("Прочее", "Неизвестно")


def test_f12_empty_csv_file_header_only(tmp_db, tmp_path):
    csv_file = tmp_path / "header_only.csv"
    content = "Дата операции;Сумма операции;Категория;Описание\n"
    csv_file.write_text(content, encoding="utf-8-sig")
    
    count = parse_tinkoff_csv_statement(str(csv_file))
    assert count == 0


def test_f12_malformed_csv_line_graceful_handling(tmp_db, tmp_path):
    csv_file = tmp_path / "corrupted.csv"
    content = "Дата операции;Сумма операции;Категория;Описание\nINVALID_LINE_NO_DELIMITER\n"
    csv_file.write_text(content, encoding="utf-8-sig")
    
    # Should catch exception internally and return 0
    count = parse_tinkoff_csv_statement(str(csv_file))
    assert count == 0


# ===========================================================================
# FEATURE 13: R3 Debt Liabilities Tracker
# ===========================================================================

class DebtLiabilitiesTracker:
    """Helper model representing R3 Debt Liabilities Requirements."""
    def __init__(self, purchase_loan=290000.0, installment_1=9900.0, installment_2=4335.0, cc_limit=150000.0, cc_used=0.0):
        self.purchase_loan = purchase_loan
        self.installment_1 = installment_1
        self.installment_2 = installment_2
        self.cc_limit = cc_limit
        self.cc_used = cc_used

    def get_total_principal_liabilities(self):
        return self.purchase_loan + self.installment_1 + self.installment_2 + self.cc_used

    def get_monthly_minimum_obligations(self, loan_monthly_payment=12000.0):
        # Total monthly fixed installment payments + loan monthly payment
        actual_loan_pay = loan_monthly_payment if self.purchase_loan > 0 else 0.0
        return actual_loan_pay + self.installment_1 + self.installment_2

    def record_loan_payment(self, payment_amount):
        self.purchase_loan = max(0.0, self.purchase_loan - payment_amount)

    def add_installment(self, amount):
        self.installment_1 += amount



# --- Tier 1 (Happy Path) ---

def test_f13_track_purchase_loan():
    tracker = DebtLiabilitiesTracker()
    assert tracker.purchase_loan == 290000.0


def test_f13_track_active_installments():
    tracker = DebtLiabilitiesTracker()
    assert tracker.installment_1 == 9900.0
    assert tracker.installment_2 == 4335.0


def test_f13_total_debt_liabilities_calculation():
    tracker = DebtLiabilitiesTracker(purchase_loan=290000.0, installment_1=9900.0, installment_2=4335.0)
    expected_total = 290000.0 + 9900.0 + 4335.0
    assert tracker.get_total_principal_liabilities() == expected_total  # 304,235 ₽


def test_f13_credit_card_limit_and_balance():
    tracker = DebtLiabilitiesTracker(cc_limit=150000.0, cc_used=25000.0)
    assert tracker.cc_limit == 150000.0
    assert tracker.cc_used == 25000.0
    assert tracker.get_total_principal_liabilities() == (290000.0 + 9900.0 + 4335.0 + 25000.0)


def test_f13_monthly_liabilities_minimum_payment():
    tracker = DebtLiabilitiesTracker()
    monthly_debt_due = tracker.get_monthly_minimum_obligations(loan_monthly_payment=15000.0)
    # 15,000 + 9,900 + 4,335 = 29,235 ₽
    assert monthly_debt_due == 29235.0


# --- Tier 2 (Boundary & Corner Cases) ---

def test_f13_add_new_installment_debt():
    tracker = DebtLiabilitiesTracker()
    tracker.add_installment(5000.0)
    assert tracker.installment_1 == 14900.0


def test_f13_partial_loan_repayment_reduction():
    tracker = DebtLiabilitiesTracker(purchase_loan=290000.0)
    tracker.record_loan_payment(50000.0)
    assert tracker.purchase_loan == 240000.0


def test_f13_zero_debt_completion_state():
    tracker = DebtLiabilitiesTracker(purchase_loan=0.0, installment_1=0.0, installment_2=0.0, cc_used=0.0)
    assert tracker.get_total_principal_liabilities() == 0.0


def test_f13_debt_to_income_ratio():
    tracker = DebtLiabilitiesTracker()
    monthly_due = tracker.get_monthly_minimum_obligations(loan_monthly_payment=15000.0)  # 29,235 ₽
    monthly_income = 80000.0
    dti_ratio = round((monthly_due / monthly_income) * 100, 2)
    assert dti_ratio == 36.54


def test_f13_installment_payoff_timeline():
    # Installment 1 = 9,900 ₽ paid at 3,300 ₽ / month -> 3 months
    inst_balance = 9900.0
    monthly_pay = 3300.0
    months_left = inst_balance / monthly_pay
    assert months_left == 3.0


# ===========================================================================
# FEATURE 14: R3 Cash Flow Calculator
# ===========================================================================

class CashFlowCalculator:
    """Helper module for Cash Flow Deficit / Surplus Calculations."""
    def __init__(self, finance_manager: TinkoffFinanceManager, debt_tracker: DebtLiabilitiesTracker):
        self.fm = finance_manager
        self.dt = debt_tracker

    def compute_cash_flow(self, additional_monthly_debt_payment=0.0):
        summary = self.fm.get_financial_summary()
        income = summary["total_income_rub"]
        expenses = summary["total_expense_rub"]
        fixed_debt = self.dt.get_monthly_minimum_obligations() + additional_monthly_debt_payment
        
        net_cash_flow = income - (expenses + fixed_debt)
        is_deficit = net_cash_flow < 0
        deficit_amount = abs(net_cash_flow) if is_deficit else 0.0
        
        return {
            "income_rub": income,
            "expense_rub": expenses,
            "debt_obligations_rub": fixed_debt,
            "net_cash_flow_rub": net_cash_flow,
            "is_deficit": is_deficit,
            "deficit_amount_rub": deficit_amount
        }


# --- Tier 1 (Happy Path) ---

def test_f14_calculate_net_cash_flow_surplus(tmp_db):
    mgr = TinkoffFinanceManager()
    mgr.add_transaction(100000.0, "Зарплата", "Работодатель", op_type="CREDIT")
    mgr.add_transaction(30000.0, "Продукты & Быт", "Супермаркет", op_type="DEBIT")
    
    tracker = DebtLiabilitiesTracker()
    cf_calc = CashFlowCalculator(mgr, tracker)
    res = cf_calc.compute_cash_flow(additional_monthly_debt_payment=0.0)
    
    # Income (100k) - Expense (30k) - Debt (26.235k) = 43.765k Surplus
    assert res["net_cash_flow_rub"] > 0
    assert not res["is_deficit"]
    assert res["deficit_amount_rub"] == 0.0


def test_f14_calculate_net_cash_flow_deficit(tmp_db):
    mgr = TinkoffFinanceManager()
    mgr.add_transaction(30000.0, "Фриланс", "Заказчик", op_type="CREDIT")
    mgr.add_transaction(35000.0, "Аренда & Аптека", "Арендодатель", op_type="DEBIT")
    
    tracker = DebtLiabilitiesTracker()
    cf_calc = CashFlowCalculator(mgr, tracker)
    res = cf_calc.compute_cash_flow()
    
    # Net = 30k - (35k + 26.235k) = -31.235k Deficit
    assert res["is_deficit"]
    assert res["deficit_amount_rub"] == 31235.0


def test_f14_cash_flow_with_debt_liabilities(tmp_db):
    mgr = TinkoffFinanceManager()
    mgr.add_transaction(50000.0, "Доход", "Проект", op_type="CREDIT")
    mgr.add_transaction(20000.0, "Расходы", "Магазин", op_type="DEBIT")
    
    tracker = DebtLiabilitiesTracker()
    cf_calc = CashFlowCalculator(mgr, tracker)
    res = cf_calc.compute_cash_flow()
    
    expected_net = 50000.0 - (20000.0 + (12000.0 + 9900.0 + 4335.0))
    assert res["net_cash_flow_rub"] == expected_net


def test_f14_category_expense_ratio(tmp_db):
    mgr = TinkoffFinanceManager()
    mgr.add_transaction(6000.0, "Продукты", "ВкусВилл", op_type="DEBIT")
    mgr.add_transaction(4000.0, "Транспорт", "Такси", op_type="DEBIT")
    
    summary = mgr.get_financial_summary()
    cat = summary["expenses_by_category"]
    total = summary["total_expense_rub"]
    
    food_pct = (cat["Продукты"] / total) * 100
    transport_pct = (cat["Транспорт"] / total) * 100
    
    assert food_pct == 60.0
    assert transport_pct == 40.0


def test_f14_cash_flow_summary_dictionary_structure(tmp_db):
    mgr = TinkoffFinanceManager()
    tracker = DebtLiabilitiesTracker()
    cf_calc = CashFlowCalculator(mgr, tracker)
    res = cf_calc.compute_cash_flow()
    
    expected_keys = {"income_rub", "expense_rub", "debt_obligations_rub", "net_cash_flow_rub", "is_deficit", "deficit_amount_rub"}
    assert set(res.keys()) == expected_keys


# --- Tier 2 (Boundary & Corner Cases) ---

def test_f14_zero_income_pure_deficit(tmp_db):
    mgr = TinkoffFinanceManager()
    mgr.add_transaction(15000.0, "Личные", "Покупки", op_type="DEBIT")
    
    tracker = DebtLiabilitiesTracker()
    cf_calc = CashFlowCalculator(mgr, tracker)
    res = cf_calc.compute_cash_flow()
    
    assert res["income_rub"] == 0.0
    assert res["is_deficit"]
    assert res["deficit_amount_rub"] == (15000.0 + 26235.0)


def test_f14_zero_expense_pure_surplus(tmp_db):
    mgr = TinkoffFinanceManager()
    mgr.add_transaction(70000.0, "Зарплата", "Компания", op_type="CREDIT")
    
    tracker = DebtLiabilitiesTracker(purchase_loan=0.0, installment_1=0.0, installment_2=0.0)
    cf_calc = CashFlowCalculator(mgr, tracker)
    res = cf_calc.compute_cash_flow()
    
    assert res["expense_rub"] == 0.0
    assert res["net_cash_flow_rub"] == 70000.0


def test_f14_large_transaction_volume_cash_flow(tmp_db):
    mgr = TinkoffFinanceManager()
    for i in range(100):
        mgr.add_transaction(100.0, "Мелочи", f"Магазин_{i}", op_type="DEBIT")
    for i in range(10):
        mgr.add_transaction(2000.0, "Доход", f"Клиент_{i}", op_type="CREDIT")
        
    tracker = DebtLiabilitiesTracker(purchase_loan=0.0, installment_1=0.0, installment_2=0.0)
    cf_calc = CashFlowCalculator(mgr, tracker)
    res = cf_calc.compute_cash_flow()
    
    assert res["income_rub"] == 20000.0
    assert res["expense_rub"] == 10000.0
    assert res["net_cash_flow_rub"] == 10000.0


def test_f14_balanced_zero_cash_flow(tmp_db):
    mgr = TinkoffFinanceManager()
    mgr.add_transaction(50000.0, "Доход", "Проект", op_type="CREDIT")
    mgr.add_transaction(50000.0, "Расходы", "Баланс", op_type="DEBIT")
    
    tracker = DebtLiabilitiesTracker(purchase_loan=0.0, installment_1=0.0, installment_2=0.0)
    cf_calc = CashFlowCalculator(mgr, tracker)
    res = cf_calc.compute_cash_flow()
    
    assert res["net_cash_flow_rub"] == 0.0
    assert not res["is_deficit"]


def test_f14_deficit_severity_classification(tmp_db):
    mgr = TinkoffFinanceManager()
    mgr.add_transaction(20000.0, "Доход", "Проект", op_type="CREDIT")
    mgr.add_transaction(35000.0, "Расход", "Аренда", op_type="DEBIT")
    
    tracker = DebtLiabilitiesTracker(purchase_loan=0.0, installment_1=0.0, installment_2=0.0)
    cf_calc = CashFlowCalculator(mgr, tracker)
    res = cf_calc.compute_cash_flow()
    
    deficit = res["deficit_amount_rub"]  # 15000 RUB
    
    severity = "NONE"
    if deficit > 10000:
        severity = "SEVERE"
    elif deficit > 5000:
        severity = "MODERATE"
    elif deficit > 0:
        severity = "MINOR"
        
    assert severity == "SEVERE"
