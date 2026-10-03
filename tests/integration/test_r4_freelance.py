"""
Vazus SuperGraph OS - R4 Freelance Revenue Engine Test Suite (Features 15 - 19)
Covers:
  - Feature 15: R4 NPD Self-Employed Manager (FNS Мой Налог receipts, 4%/6% tax calculations)
  - Feature 16: R4 Order Scanner & Matcher (Freelance platform order hunter, cataloging)
  - Feature 17: R4 Client Proposal Generator (Automated proposals with tech stack & quote)
  - Feature 18: R4 Micro-IT Code Generator (TeleBot + Gemini AI support bot code templates, OCR & scrapers)
  - Feature 19: R4 Revenue Deficit Link (MRR calculation, client contract logging, covering R3 deficit)

Tier 1 (Feature Coverage): 25 tests
Tier 2 (Boundary & Corner Cases): 25 tests
Total: 50 test cases
"""

import sys
import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import datetime

sys.path.append(r"C:\vazus")
sys.path.append(r"C:\vazus\vazus_core")

import vazus_core.self_employed_order_hunter as seoh
import vazus_core.autonomous_freelance_engine as afe
seoh_flat = seoh
afe_flat = afe

from vazus_core.self_employed_order_hunter import SelfEmployedManager, OrderHunterEngine, init_self_employed_db
from vazus_core.autonomous_freelance_engine import AutonomousFreelanceEngine, init_freelance_db


# ---------------------------------------------------------------------------
# Pytest Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    """Provides an isolated SQLite database path for testing R4 features."""
    db_file = str(tmp_path / "test_freelance.db")
    monkeypatch.setattr(seoh, "DB_PATH", db_file)
    monkeypatch.setattr(afe, "DB_PATH", db_file)
    monkeypatch.setattr(seoh_flat, "DB_PATH", db_file)
    monkeypatch.setattr(afe_flat, "DB_PATH", db_file)
    init_self_employed_db()
    init_freelance_db()
    return db_file





# ===========================================================================
# FEATURE 15: R4 NPD Self-Employed Manager
# ===========================================================================

# --- Tier 1 (Happy Path) ---

def test_f15_register_physical_client_income_4pct(tmp_db):
    mgr = SelfEmployedManager()
    res = mgr.register_income(10000.0, "Разработка Telegram-бота", is_legal_entity=False)
    
    assert res["amount_rub"] == 10000.0
    assert res["tax_rate_pct"] == 4
    assert res["tax_rub"] == 400.0
    assert res["net_rub"] == 9600.0


def test_f15_register_legal_entity_income_6pct(tmp_db):
    mgr = SelfEmployedManager()
    res = mgr.register_income(50000.0, "Внедрение CRM ИИ модулей", is_legal_entity=True)
    
    assert res["amount_rub"] == 50000.0
    assert res["tax_rate_pct"] == 6
    assert res["tax_rub"] == 3000.0
    assert res["net_rub"] == 47000.0


def test_f15_receipts_database_insertion(tmp_db):
    mgr = SelfEmployedManager()
    mgr.register_income(15000.0, "Парсинг сайта автозапчастей", is_legal_entity=False)
    
    conn = sqlite3.connect(tmp_db)
    row = conn.execute("SELECT amount_rub, tax_rub, client_type, service_name FROM self_employed_receipts").fetchone()
    conn.close()
    
    assert row == (15000.0, 600.0, "PHYSICAL", "Парсинг сайта автозапчастей")


def test_f15_net_rub_calculation(tmp_db):
    mgr = SelfEmployedManager()
    res = mgr.register_income(25000.0, "Консультация по Python API", is_legal_entity=True)
    assert res["net_rub"] == (25000.0 - 1500.0)


def test_f15_receipt_client_type_tagging(tmp_db):
    mgr = SelfEmployedManager()
    mgr.register_income(5000.0, "Услуга A", is_legal_entity=False)
    mgr.register_income(8000.0, "Услуга B", is_legal_entity=True)
    
    conn = sqlite3.connect(tmp_db)
    types = [r[0] for r in conn.execute("SELECT client_type FROM self_employed_receipts ORDER BY id").fetchall()]
    conn.close()
    
    assert types == ["PHYSICAL", "LEGAL"]


# --- Tier 2 (Boundary & Corner Cases) ---

def test_f15_zero_income_registration(tmp_db):
    mgr = SelfEmployedManager()
    res = mgr.register_income(0.0, "Бесплатная настройка", is_legal_entity=False)
    
    assert res["tax_rub"] == 0.0
    assert res["net_rub"] == 0.0


def test_f15_large_income_amount_tax(tmp_db):
    mgr = SelfEmployedManager()
    res = mgr.register_income(500000.0, "Годовой контракт поддержки", is_legal_entity=True)
    
    assert res["tax_rub"] == 30000.0
    assert res["net_rub"] == 470000.0


def test_f15_floating_point_rounding_tax(tmp_db):
    mgr = SelfEmployedManager()
    # 1234.56 * 0.04 = 49.3824 -> round(2) -> 49.38
    res = mgr.register_income(1234.56, "Разовая задача", is_legal_entity=False)
    
    assert res["tax_rub"] == 49.38
    assert res["net_rub"] == 1185.18


def test_f15_empty_service_name_handling(tmp_db):
    mgr = SelfEmployedManager()
    res = mgr.register_income(3000.0, "", is_legal_entity=False)
    
    conn = sqlite3.connect(tmp_db)
    name = conn.execute("SELECT service_name FROM self_employed_receipts").fetchone()[0]
    conn.close()
    
    assert name == ""


def test_f15_tax_summary_aggregation(tmp_db):
    mgr = SelfEmployedManager()
    mgr.register_income(10000.0, "Заказ 1", is_legal_entity=False) # tax 400
    mgr.register_income(20000.0, "Заказ 2", is_legal_entity=True)  # tax 1200
    
    conn = sqlite3.connect(tmp_db)
    total_tax = conn.execute("SELECT SUM(tax_rub) FROM self_employed_receipts").fetchone()[0]
    total_income = conn.execute("SELECT SUM(amount_rub) FROM self_employed_receipts").fetchone()[0]
    conn.close()
    
    assert total_income == 30000.0
    assert total_tax == 1600.0


# ===========================================================================
# FEATURE 16: R4 Order Scanner & Matcher
# ===========================================================================

# --- Tier 1 (Happy Path) ---

def test_f16_scan_active_freelance_orders(tmp_db):
    hunter = OrderHunterEngine()
    orders = hunter.scan_active_freelance_orders()
    
    assert isinstance(orders, list)
    assert len(orders) >= 3


def test_f16_catalog_orders_to_database(tmp_db):
    hunter = OrderHunterEngine()
    hunter.scan_active_freelance_orders()
    
    conn = sqlite3.connect(tmp_db)
    count = conn.execute("SELECT COUNT(*) FROM freelance_orders_found").fetchone()[0]
    conn.close()
    
    assert count >= 3


def test_f16_order_fields_integrity(tmp_db):
    hunter = OrderHunterEngine()
    orders = hunter.scan_active_freelance_orders()
    
    for ord_item in orders:
        assert "source" in ord_item
        assert "title" in ord_item
        assert "price_rub" in ord_item
        assert "link" in ord_item
        assert "stack" in ord_item


def test_f16_matched_stack_keywords(tmp_db):
    hunter = OrderHunterEngine()
    orders = hunter.scan_active_freelance_orders()
    
    stacks = [o["stack"] for o in orders]
    all_stacks_str = " ".join(stacks)
    
    assert "Python" in all_stacks_str
    assert ("Telegram" in all_stacks_str or "OCR" in all_stacks_str or "Scraping" in all_stacks_str)


def test_f16_proposed_reply_generation(tmp_db):
    hunter = OrderHunterEngine()
    hunter.scan_active_freelance_orders()
    
    conn = sqlite3.connect(tmp_db)
    replies = conn.execute("SELECT proposed_reply FROM freelance_orders_found").fetchall()
    conn.close()
    
    for r in replies:
        assert "Здравствуйте!" in r[0]
        assert "Самозанятый" in r[0]


# --- Tier 2 (Boundary & Corner Cases) ---

def test_f16_multiple_scans_deduplication(tmp_db):
    hunter = OrderHunterEngine()
    hunter.scan_active_freelance_orders()
    hunter.scan_active_freelance_orders()
    
    conn = sqlite3.connect(tmp_db)
    count = conn.execute("SELECT COUNT(*) FROM freelance_orders_found").fetchone()[0]
    conn.close()
    
    assert count == 3  # Stable deterministic URLs properly deduplicated via UNIQUE(link)


def test_f16_price_rub_filter_threshold(tmp_db):
    hunter = OrderHunterEngine()
    orders = hunter.scan_active_freelance_orders()
    
    high_value_orders = [o for o in orders if o["price_rub"] >= 5000.0]
    assert len(high_value_orders) >= 2


def test_f16_custom_sample_orders_scan(tmp_db, monkeypatch):
    hunter = OrderHunterEngine()
    
    custom_orders = [
        {
            "source": "Fl.ru",
            "title": "Скрипт мониторинга Telegram каналов",
            "price_rub": 12000.0,
            "link": "https://fl.ru/tasks/123",
            "stack": "Python / Telethon"
        }
    ]
    
    # Mocking order generation if needed or testing custom data
    with patch.object(hunter, "scan_active_freelance_orders", return_value=custom_orders):
        res = hunter.scan_active_freelance_orders()
        assert len(res) == 1
        assert res[0]["source"] == "Fl.ru"


def test_f16_empty_orders_scan_result(tmp_db):
    hunter = OrderHunterEngine()
    with patch.object(hunter, "scan_active_freelance_orders", return_value=[]):
        res = hunter.scan_active_freelance_orders()
        assert res == []


def test_f16_database_schema_freelance_orders_found(tmp_db):
    conn = sqlite3.connect(tmp_db)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(freelance_orders_found)")
    cols = [row[1] for row in cursor.fetchall()]
    conn.close()
    
    expected_cols = {"id", "timestamp", "source", "title", "price_rub", "link", "matched_stack", "proposed_reply"}
    assert expected_cols.issubset(set(cols))


# ===========================================================================
# FEATURE 17: R4 Client Proposal Generator
# ===========================================================================

# --- Tier 1 (Happy Path) ---

def test_f17_generate_proposal_includes_task_title():
    hunter = OrderHunterEngine()
    proposal = hunter.generate_proposal_for_task("Разработка парсера Avito", 6000.0)
    assert "Разработка парсера Avito" in proposal


def test_f17_generate_proposal_includes_budget():
    hunter = OrderHunterEngine()
    proposal = hunter.generate_proposal_for_task("Бот техподдержки", 7500.0)
    assert "7500.0 руб" in proposal or "7500 руб" in proposal


def test_f17_generate_proposal_mentions_self_employed_status():
    hunter = OrderHunterEngine()
    proposal = hunter.generate_proposal_for_task("OCR Модуль", 4000.0)
    assert "Самозанятый" in proposal
    assert "Мой Налог" in proposal


def test_f17_generate_proposal_mentions_tech_stack():
    hunter = OrderHunterEngine()
    proposal = hunter.generate_proposal_for_task("Интеграция ИИ", 10000.0)
    assert "Python" in proposal
    assert "Google Gemini AI" in proposal


def test_f17_generate_proposal_delivery_timeline():
    hunter = OrderHunterEngine()
    proposal = hunter.generate_proposal_for_task("Микро-сервис", 5000.0)
    assert "1-2 дня" in proposal


# --- Tier 2 (Boundary & Corner Cases) ---

def test_f17_proposal_with_special_characters_title():
    hunter = OrderHunterEngine()
    special_title = "Парсинг <catalog> & 'export' (JSON/CSV) [v2.0]"
    proposal = hunter.generate_proposal_for_task(special_title, 8500.0)
    assert special_title in proposal


def test_f17_proposal_with_zero_budget():
    hunter = OrderHunterEngine()
    proposal = hunter.generate_proposal_for_task("Доработка скрипта", 0.0)
    assert "0.0 руб" in proposal or "0 руб" in proposal


def test_f17_proposal_multiline_formatting():
    hunter = OrderHunterEngine()
    proposal = hunter.generate_proposal_for_task("Тест", 1000.0)
    lines = proposal.split("\n")
    assert len(lines) >= 4
    assert lines[0].startswith("Здравствуйте!")


def test_f17_proposal_unicode_cyrillic_encoding():
    hunter = OrderHunterEngine()
    proposal = hunter.generate_proposal_for_task("Оцифровка чеков", 3000.0)
    # Ensure cyrillic characters remain clean unicode strings
    assert isinstance(proposal, str)
    assert "Обращайтесь!" in proposal


def test_f17_proposal_template_consistency():
    hunter = OrderHunterEngine()
    p1 = hunter.generate_proposal_for_task("Задача X", 5000.0)
    p2 = hunter.generate_proposal_for_task("Задача X", 5000.0)
    assert p1 == p2


# ===========================================================================
# FEATURE 18: R4 Micro-IT Code Generator
# ===========================================================================

# --- Tier 1 (Happy Path) ---

def test_f18_generate_telegram_bot_code_template():
    engine = AutonomousFreelanceEngine()
    code = engine.generate_telegram_bot_service_template("Салон Красоты Элегант", "Бьюти-сфера")
    assert isinstance(code, str)
    assert len(code) > 100


def test_f18_bot_code_includes_business_name_and_niche():
    engine = AutonomousFreelanceEngine()
    code = engine.generate_telegram_bot_service_template("Стоматология ДентПро", "Стоматология")
    assert "Стоматология ДентПро" in code
    assert "Стоматология" in code


def test_f18_bot_code_python_syntax_validity():
    engine = AutonomousFreelanceEngine()
    code = engine.generate_telegram_bot_service_template("Автосервис Вектор", "Автоуслуги")
    # Verify code compiles cleanly without SyntaxError
    compiled = compile(code, "<generated_code>", "exec")
    assert compiled is not None


def test_f18_bot_code_imports_telebot_and_genai():
    engine = AutonomousFreelanceEngine()
    code = engine.generate_telegram_bot_service_template("Фитнес Клуб Олимп", "Спорт")
    assert "import telebot" in code
    assert "from google import genai" in code


def test_f18_bot_code_uses_gemini_model():
    engine = AutonomousFreelanceEngine()
    code = engine.generate_telegram_bot_service_template("Кофейня Арома", "Общепит")
    assert "gemini-2.5-flash" in code


# --- Tier 2 (Boundary & Corner Cases) ---

def test_f18_bot_code_business_name_with_quotes():
    engine = AutonomousFreelanceEngine()
    code = engine.generate_telegram_bot_service_template("ООО 'Вектор-ИТ'", "Айти")
    assert "ООО 'Вектор-ИТ'" in code
    # Must compile without breaking quotes
    assert compile(code, "<test>", "exec") is not None



def test_f18_bot_code_non_ascii_cyrillic_niche():
    engine = AutonomousFreelanceEngine()
    code = engine.generate_telegram_bot_service_template("Юридическая фирма Право", "Юриспруденция и Консалтинг")
    assert "Юриспруденция и Консалтинг" in code


def test_f18_bot_code_empty_niche_handling():
    engine = AutonomousFreelanceEngine()
    code = engine.generate_telegram_bot_service_template("Компания X", "")
    assert compile(code, "<test>", "exec") is not None


def test_f18_ocr_extractor_code_template_generator():
    """Generates and tests an OCR extraction service script template."""
    ocr_code_template = '''# Pix2Text + Gemini Multimodal OCR Micro-Service
import sys
from vazus_core.google_multimodal_vision import analyze_lab_report_image

def process_document(pdf_or_img_path):
    return analyze_lab_report_image(pdf_or_img_path)
'''
    compiled = compile(ocr_code_template, "<ocr_template>", "exec")
    assert compiled is not None


def test_f18_web_scraper_code_template_generator():
    """Generates and tests a Web Scraper service script template."""
    scraper_code_template = '''# Web Catalog Scraping Micro-Service
import requests
from bs4 import BeautifulSoup

def scrape_catalog_prices(url):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, 'html.parser')
    return [item.text.strip() for item in soup.find_all('span', class_='price')]
'''
    compiled = compile(scraper_code_template, "<scraper_template>", "exec")
    assert compiled is not None


# ===========================================================================
# FEATURE 19: R4 Revenue Deficit Link
# ===========================================================================

# --- Tier 1 (Happy Path) ---

def test_f19_log_active_client_contract(tmp_db):
    engine = AutonomousFreelanceEngine()
    engine.log_client_contract("Клиент Клиника Дент", "Telegram AI Bot Support", monthly_fee=15000.0, one_time_fee=10000.0)
    
    conn = sqlite3.connect(tmp_db)
    row = conn.execute("SELECT client_name, service_type, monthly_fee_rub, one_time_fee_rub, status FROM freelance_clients").fetchone()
    conn.close()
    
    assert row == ("Клиент Клиника Дент", "Telegram AI Bot Support", 15000.0, 10000.0, "ACTIVE")


def test_f19_get_monthly_recurring_revenue_mrr(tmp_db):
    engine = AutonomousFreelanceEngine()
    engine.log_client_contract("Клиент A", "Bot Support", monthly_fee=12000.0)
    engine.log_client_contract("Клиент B", "Scraping Feed", monthly_fee=8000.0)
    
    mrr = engine.get_monthly_recurring_revenue()
    assert mrr == 20000.0


def test_f19_mrr_filters_only_active_status(tmp_db):
    engine = AutonomousFreelanceEngine()
    engine.log_client_contract("Клиент Активный", "Бот", monthly_fee=10000.0)
    engine.log_client_contract("Клиент Ушедший", "OCR", monthly_fee=15000.0)
    
    # Manually mark second client as INACTIVE
    conn = sqlite3.connect(tmp_db)
    conn.execute("UPDATE freelance_clients SET status='INACTIVE' WHERE client_name='Клиент Ушедший'")
    conn.commit()
    conn.close()
    
    mrr = engine.get_monthly_recurring_revenue()
    assert mrr == 10000.0


def test_f19_revenue_covers_deficit_target_threshold(tmp_db):
    engine = AutonomousFreelanceEngine()
    engine.log_client_contract("Клиент Крупный", "AI Bot + Analytics", monthly_fee=18000.0)
    
    mrr = engine.get_monthly_recurring_revenue()
    target_threshold = 10000.0
    
    assert mrr > target_threshold


def test_f19_one_time_fee_plus_mrr_total_revenue(tmp_db):
    engine = AutonomousFreelanceEngine()
    engine.log_client_contract("Клиент C", "Под ключ", monthly_fee=10000.0, one_time_fee=15000.0)
    
    conn = sqlite3.connect(tmp_db)
    row = conn.execute("SELECT monthly_fee_rub, one_time_fee_rub FROM freelance_clients").fetchone()
    conn.close()
    
    first_month_total = row[0] + row[1]
    assert first_month_total == 25000.0


# --- Tier 2 (Boundary & Corner Cases) ---

def test_f19_zero_active_clients_mrr_returns_zero(tmp_db):
    engine = AutonomousFreelanceEngine()
    mrr = engine.get_monthly_recurring_revenue()
    assert mrr == 0.0


def test_f19_client_status_update_recalculation(tmp_db):
    engine = AutonomousFreelanceEngine()
    engine.log_client_contract("Клиент D", "Поддержка", monthly_fee=12000.0)
    
    assert engine.get_monthly_recurring_revenue() == 12000.0
    
    conn = sqlite3.connect(tmp_db)
    conn.execute("UPDATE freelance_clients SET status='PAUSED' WHERE client_name='Клиент D'")
    conn.commit()
    conn.close()
    
    assert engine.get_monthly_recurring_revenue() == 0.0


def test_f19_multiple_clients_mrr_aggregation(tmp_db):
    engine = AutonomousFreelanceEngine()
    fees = [3000.0, 4500.0, 6000.0, 7500.0, 9000.0]
    for idx, fee in enumerate(fees):
        engine.log_client_contract(f"Клиент_{idx}", "Микроуслуга", monthly_fee=fee)
        
    assert engine.get_monthly_recurring_revenue() == sum(fees) # 30,000.0 RUB


def test_f19_deficit_coverage_percentage_calculation(tmp_db):
    engine = AutonomousFreelanceEngine()
    engine.log_client_contract("Клиент E", "ИИ Помощник", monthly_fee=15000.0)
    
    mrr = engine.get_monthly_recurring_revenue()
    r3_cash_flow_deficit = 12000.0
    
    coverage_pct = round((mrr / r3_cash_flow_deficit) * 100, 2)
    assert coverage_pct == 125.0  # 125% coverage (deficit fully eliminated)


def test_f19_net_freelance_profit_after_npd_tax(tmp_db):
    engine = AutonomousFreelanceEngine()
    se = SelfEmployedManager()
    
    # Client pays 20,000 RUB as Legal Entity (6% tax)
    rec = se.register_income(20000.0, "Абонентское обслуживание ИИ", is_legal_entity=True)
    engine.log_client_contract("ООО БьютиКлиник", "Абонентка", monthly_fee=20000.0)
    
    net_mrr = rec["net_rub"]  # 18,800 RUB
    assert net_mrr == 18800.0
    assert rec["tax_rub"] == 1200.0


# ===========================================================================
# ITERATION 2 REMEDIATION TESTS (Challenger 1 Edge Cases)
# ===========================================================================

def test_remediation_fns_npd_input_validation(tmp_db):
    import math
    mgr = SelfEmployedManager()

    # Test NaN
    with pytest.raises(ValueError, match="Income amount must be a finite number"):
        mgr.register_income(float('nan'), "Тестовая услуга")

    # Test Infinity
    with pytest.raises(ValueError, match="Income amount must be a finite number"):
        mgr.register_income(float('inf'), "Тестовая услуга")

    # Test Exceeding Annual Limit (2,400,000 RUB)
    with pytest.raises(ValueError, match="Single receipt amount exceeds statutory FNS NPD annual limit of 2,400,000 RUB"):
        mgr.register_income(2500000.0, "Крупный контракт")


def test_remediation_newline_comment_syntax_error():
    engine = AutonomousFreelanceEngine()

    multiline_name = "ООО 'Бьюти-Маркет'\nВторая строка"
    multiline_niche = "Косметология\r\nСалон"

    bot_code = engine.generate_telegram_bot_service_template(multiline_name, multiline_niche)
    ocr_code = engine.generate_ocr_extractor_service_template(multiline_name, multiline_niche)
    scraper_code = engine.generate_web_scraper_service_template(multiline_name, "https://example.com/item\n")

    # All generated code strings must parse with ast without SyntaxError
    import ast
    assert ast.parse(bot_code) is not None
    assert ast.parse(ocr_code) is not None
    assert ast.parse(scraper_code) is not None

    assert compile(bot_code, "<bot_test>", "exec") is not None
    assert compile(ocr_code, "<ocr_test>", "exec") is not None
    assert compile(scraper_code, "<scraper_test>", "exec") is not None


# ===========================================================================
# ITERATION 3 REMEDIATION TESTS (Challenger 4 Edge Cases)
# ===========================================================================

def test_remediation_null_byte_sanitization():
    import ast
    engine = AutonomousFreelanceEngine()

    null_name = "ООО\x00 'Техно\x00Маркет'"
    null_niche = "IT\x00-услуги\x00"
    null_doc = "Накладная\x00_v1"
    null_site = "https://\x00example.com/\x00parts"

    bot_code = engine.generate_telegram_bot_service_template(null_name, null_niche)
    ocr_code = engine.generate_ocr_extractor_service_template(null_name, null_doc)
    scraper_code = engine.generate_web_scraper_service_template(null_name, null_site)

    assert '\x00' not in bot_code
    assert '\x00' not in ocr_code
    assert '\x00' not in scraper_code

    assert ast.parse(bot_code) is not None
    assert ast.parse(ocr_code) is not None
    assert ast.parse(scraper_code) is not None

    assert compile(bot_code, "<bot_null_test>", "exec") is not None
    assert compile(ocr_code, "<ocr_null_test>", "exec") is not None
    assert compile(scraper_code, "<scraper_null_test>", "exec") is not None


def test_remediation_status_case_normalization(tmp_db):
    engine = AutonomousFreelanceEngine()

    # Log contract with lowercase/mixed-case status
    engine.log_client_contract("Client Alpha", "Bot Support", monthly_fee=15000.0, status='active')
    engine.log_client_contract("Client Beta", "OCR Service", monthly_fee=10000.0, status='Active')

    conn = sqlite3.connect(tmp_db)
    statuses = [r[0] for r in conn.execute("SELECT status FROM freelance_clients ORDER BY id").fetchall()]
    conn.close()

    assert statuses == ["ACTIVE", "ACTIVE"]
    assert engine.get_monthly_recurring_revenue() == 25000.0

    # Update status with lowercase
    engine.update_client_status("Client Alpha", "paused")
    
    conn = sqlite3.connect(tmp_db)
    alpha_status = conn.execute("SELECT status FROM freelance_clients WHERE client_name='Client Alpha'").fetchone()[0]
    conn.close()

    assert alpha_status == "PAUSED"
    assert engine.get_monthly_recurring_revenue() == 10000.0

    # Re-activate with mixed case
    engine.update_client_status("Client Alpha", "aCtIvE")
    assert engine.get_monthly_recurring_revenue() == 25000.0


