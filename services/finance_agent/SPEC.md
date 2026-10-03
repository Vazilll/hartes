# Domain Specification: Finance & Self-Employed NPD Engine
**Module Path**: services/finance_agent  
**Domain Lead Archetype**: azus-finance-agent / worker_implementer  
**Current Skill Rank**: Level 3 (Tax & Debt Optimization Ledger)  

## 1. Core Mission & Boundaries
### 1.1 Primary Mission
The Finance & Self-Employed NPD Engine manages personal cash flow, banking statement analytics (T-Bank), self-employed tax accounting under Russian Federal Law 422-FZ (НПД / Мой Налог), debt avalanche optimization, and autonomous freelance order hunting.

### 1.2 Strict Boundary Rules
- **ALLOWED**:
  - Parsing bank CSV statements (TinkoffFinanceManager) with strict regex and locale handling.
  - Registering self-employed (НПД / Мой Налог) income and computing 4% (physical) or 6% (legal) tax rates.
  - Enforcing the statutory annual 2,400,000 RUB NPD threshold limit per 422-FZ.
  - Scanning and matching freelance orders (Habr Freelance, Kwork, FL.ru) based on tech stack and MRR deficit targets.
  - Generating standard micro-service Python templates (Telegram AI bots, OCR extractors, Web scrapers).
- **PROHIBITED**:
  - Executing automated outbound fund transfers, payments, or destructive banking operations.
  - Registering negative income or non-finite numbers (NaN, infinity).
  - Modifying financial records without durable SQLite WAL transactions.
  - Storing raw unencrypted banking passwords or session tokens in git-tracked files.

## 2. Public Typed Interface Contracts
### 2.1 Primary Classes & Signatures
`python
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

class TinkoffFinanceManager:
    def __init__(self, db_path: Optional[Union[str, Path]] = None, token_file: Optional[str] = None) -> None: ...
    def parse_csv_statement(self, csv_filepath: Union[str, Path]) -> List[Dict[str, Any]]: ...
    def calculate_debt_avalanche(self) -> Dict[str, Any]: ...

class SelfEmployedManager:
    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None: ...
    def register_income(
        self,
        amount_rub: float,
        service_name: str,
        client_type: Optional[str] = None,
        is_legal_entity: Optional[bool] = None,
        receipt_url: Optional[str] = None
    ) -> Dict[str, Any]: ...
    def scan_active_freelance_orders(self) -> List[Dict[str, Any]]: ...

class OrderHunterEngine:
    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None: ...
    def generate_proposal_for_task(self, task_title: str, task_budget: float = 0.0, tech_stack: Optional[str] = None) -> str: ...
    def scan_active_freelance_orders(self) -> List[Dict[str, Any]]: ...
    def match_orders_for_target_revenue(self, target_revenue_rub: Optional[float] = 0.0) -> Dict[str, Any]: ...

class AutonomousFreelanceEngine:
    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None: ...
    def generate_telegram_gemini_bot_template(self) -> str: ...
    def generate_ocr_extractor_service_template(self, client_name: str = '', doc_type: str = '') -> str: ...
    def generate_web_scraper_service_template(self, client_name: str = '', target_url: str = '') -> str: ...
    def log_client_contract(self, client_name: str, service_type: str, monthly_fee: float = 0.0, one_time_fee: float = 0.0, status: str = 'ACTIVE') -> Dict[str, Any]: ...
    def get_monthly_recurring_revenue(self) -> float: ...
    def evaluate_deficit_coverage(self, r3_deficit_rub: float) -> Dict[str, Any]: ...
`

### 2.2 Invariant Guarantees
- Invariant 1: Banking operations are strictly READ-ONLY.
- Invariant 2: Self-employed receipts calculate tax deterministically: 4% for PHYSICAL and 6% for LEGAL.
- Invariant 3: Cumulative annual registered NPD income cannot exceed statutory 2,400,000 RUB limit without raising ValueError.
- Invariant 4: All monetary values are stored with 2 decimal places precision (RUB).

## 3. Progressive Skill Level (Level 1..5) & Upgrade Criteria
- **Level 1 (CSV Parser)**: Static parsing of bank CSV exports.  
  *Upgrade criteria*: Implement SQLite storage and debt repayment mathematical models.
- **Level 2 (Debt Avalanche & Cash Flow)**: Snowball/Avalanche debt calculation and monthly cash flow ledger.  
  *Upgrade criteria*: Implement 422-FZ NPD self-employed tax calculation engine.
- **Level 3 (Tax & Debt Optimization Ledger)**: Full FNS receipt tracking, 4%/6% automated tax computation, MRR deficit modeling.  
  *Upgrade criteria*: Implement autonomous freelance order hunting and proposal generation across RSS feeds.
- **Level 4 (Autonomous Order Hunter & Proposal Generator)**: Multi-platform order scraping, tech-stack matching, auto-generated proposal replies, micro-service templates.  
  *Upgrade criteria*: Implement autonomous freelance micro-service synthesis linked to live MRR revenue.
- **Level 5 (Self-Sustaining Financial Governor)**: Real-time banking API webhook integration, predictive budget forecasting, automated invoice generation, and closed-loop financial autonomy.

## 4. Known Bottlenecks & Optimization Backlog
- [ ] Bank statement CSV schema layout variations across mobile banking export releases.
- [ ] Rate limiting on public freelance RSS feeds (Habr Freelance, Kwork).
- [ ] Requirement for external 	inkoff_token.txt for live OpenAPI synchronization.
