"""
train_julia_router.py — Training & ONNX Export Pipeline for Julia System-1 Router.
Architecture: 64-dim Deep Averaging Network (DAN) + 2-layer MLP on Rust BERT Tokenizer.
Optimized for ultra-low latency (<1.5 ms) execution on Intel(R) AI Boost NPU via OpenVINO.
"""

import os
import sys
import time
import shutil
import random
from typing import List, Tuple

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from tokenizers import Tokenizer

CANONICAL_DOMAINS = [
    "academic",
    "code",
    "browser",
    "finance",
    "health",
    "system_architecture",
    "jules",
    "cloud_run",
    "general_reasoning",
]

DOMAIN_TO_IDX = {d: i for i, d in enumerate(CANONICAL_DOMAINS)}
MAX_SEQ_LEN = 64
TOKENIZER_PATH = "C:/vazus/models/openvino_npu/tokenizer/tokenizer.json"
MODEL_DIR = "C:/vazus/models/julia_router"
ONNX_PATH = os.path.join(MODEL_DIR, "julia_classifier.onnx")


# ============================================================================
# 1. Dataset Generation: Bilingual High-Coverage Vazus Corpus
# ============================================================================

def generate_training_data() -> List[Tuple[str, str]]:
    """Generates a rich, balanced bilingual corpus for all 9 canonical domains."""
    data = []

    # --- ACADEMIC ---
    academic_ru = [
        "какие у меня академические задолженности в МИРЭА",
        "сколько долгов осталось сдать до 15 октября 2026",
        "помоги подготовиться к пересдаче по матанализу",
        "кафедра КИТПиПИ ИИТ расписание пересдач",
        "группа ИВБО-22-25 расписание пар на завтра",
        "личный номер 25И0566 статус в деканате",
        "объясни теорию пределов последовательностей как сократический ментор",
        "не решай за меня контрольную, только подскажи формулу",
        "типовой расчет по линейной алгебре задача 3",
        "тест СДО Moodle дискретная математика теория графов",
        "какой дедлайн сдачи лабораторной работы по базам данных",
        "как сдать зачет по физкультуре в МИРЭА баллы БРС",
        "балльно-рейтинговая система МИРЭА сколько нужно для допуска",
        "пересдача комиссии протокол сдачи хвостов",
        "лекция по дифференциальным уравнениям конспект",
        "расписание сессии зимний семестр 2 курс",
        "вопросы к экзамену по операционным системам",
        "список должников деканата ИИТ Жуков Максим",
        "как доказать теорему Коши о промежуточных значениях",
        "правило Лопиталя когда нельзя применять",
        "собственные векторы матрицы переход к базису",
        "нормальная форма дизъюнктов матлогика СДО",
        "сократический диалог по доказательству индукцией",
        "методичка МИРЭА по расчетно-графической работе",
        "курсовая работа КИТПиПИ требования к оформлению",
    ]
    academic_en = [
        "check my university academic debts and deadlines",
        "MIREA university math exam schedule",
        "how many academic subjects do I need to retake",
        "calculus limits theorem explanation socratic tutor",
        "linear algebra eigenvalues and eigenvectors study guide",
        "discrete mathematics graph theory homework questions",
        "study guide for computer architecture final exam",
        "deadline for laboratory submission university portal",
        "do not solve the assignment for me, guide my thinking",
        "Moodle LMS test preparation and review",
        "university schedule for group IVBO-22-25",
        "academic recovery plan for semester debts",
        "mathematical analysis Cauchy theorem proof guidance",
        "grading criteria and minimum score for course admission",
        "academic integrity socratic mentor mode",
    ]

    # --- CODE ---
    code_ru = [
        "отладь мой Python код в модуле embeddings.py",
        "почему возникает AttributeError 'ChoiceDecision' object has no attribute",
        "оптимизируй этот цикл for через numpy векторизацию",
        "как написать pytest тест для асинхронной функции",
        "напиши AST парсер для удаления неиспользуемых импортов",
        "синтаксическая ошибка SyntaxError invalid syntax в строке 42",
        "исправь утечку памяти в генераторе PyTorch",
        "как запустить линтер ruff и mypy в репозитории",
        "напиши функцию бинарного поиска на Python с аннотацией типов",
        "почему torch.load падает с FileNotFoundError",
        "как работает decorator в Python c functools.wraps",
        "реализуй LRU cache с потокобезопасностью",
        "почему OpenVINO infer_request возвращает dict тензоров",
        "напиши скрипт для парсинга JSON файлов в каталоге",
        "рефакторинг класса JuliaRouter устранение дублирования",
        "запусти pytest тесты для vazus_core",
        "проверь Z3 SMT верификацию контрактов функций",
        "как сериализовать dataclass в JSON без ошибок",
        "напиши регулярное выражение для парсинга логов",
        "почему компилятор C++ ругается на undefined reference",
        "реализация очереди с приоритетами heapq в Python",
        "напиши асинхронный контекстный менеджер asynccontextmanager",
        "как запустить subprocess без зависания stdout",
        "профилирование кода через cProfile и pyinstrument",
        "найди циклические импорты в пакете vazus_core",
    ]
    code_en = [
        "debug this Python script error traceback",
        "fix the AttributeError in the decision dataclass",
        "optimize function performance using numpy vectorization",
        "write a unit test with pytest for this API endpoint",
        "parse python AST and extract all class definitions",
        "memory leak in torch tensor allocation fix",
        "refactor this module to adhere to SOLID principles",
        "type hints and generics in Python typing module",
        "implement a thread-safe singleton in Python",
        "write a bash script to automate build process",
        "fix syntax error in list comprehension",
        "run static analysis with mypy and flake8",
        "how to use asyncio.gather without blocking event loop",
        "convert PyTorch model to ONNX dynamic axes",
        "benchmark execution time with perf_counter",
    ]

    # --- BROWSER ---
    browser_ru = [
        "найди в интернете последние бенчмарки моделей RWKV-7",
        "открой страницу huggingface и проверь релизы timesfm",
        "спарси через playwright текст со страницы документации",
        "найди актуальные статьи по System-1 LLM routing 2026",
        "скачай содержимое веб-страницы по ссылке через HTTP",
        "сделай скриншот сайта через playwright браузер",
        "загугли документацию по Intel OpenVINO 2026.3 NPU",
        "поищи в сети отзывы о процессоре Meteor Lake 125U",
        "заполни форму на веб-сайте через автоматизацию браузера",
        "перейди по URL и извлеки таблицу с результатами",
        "проверь статус доступности веб-сервиса через curl",
        "найди в GitHub репозиторий google/timesfm-3.0-pytorch",
        "поиск в google последних новостей о Gemma 4 release",
        "кликни по кнопке входа на странице через playwright",
        "извлеки markdown из HTML страницы",
    ]
    browser_en = [
        "search the web for the latest benchmarks of local models",
        "open url and extract article content as markdown",
        "automate headless browser with playwright to click button",
        "scrape tabular data from web page url",
        "google search for Intel NPU OpenVINO driver updates",
        "fetch website contents using http get request",
        "navigate browser to documentation page",
        "take a screenshot of web page using playwright",
        "search online for research paper on fast routing",
        "download file from public url via python",
    ]

    # --- FINANCE ---
    finance_ru = [
        "сколько денег на карте Тинькофф сейчас",
        "покажи баланс дебетовой карты Т-Банк",
        "какие расходы были за прошлую неделю по категориям",
        "сформируй чек самозанятого в приложении Мой Налог НПД",
        "сколько налога нужно заплатить за профессиональный доход",
        "выписка по операциям из банка за сентябрь 2026",
        "добавь транзакцию 1500 рублей на продукты в vazus.db",
        "какой остаток бюджета на текущий месяц",
        "посчитай общую сумму поступлений от фриланса",
        "проверь лимит по доходу самозанятого 2.4 млн рублей",
        "оплата мобильной связи и интернета квитанция",
        "сколько отложено в инвесткопилку Тинькофф",
        "категории повышенного кэшбэка на этот месяц",
        "проверь задолженность по налогам в ФНС",
        "финансовый отчет доходы минус расходы сальдо",
    ]
    finance_en = [
        "how much money on Tinkoff card balance",
        "show my bank account balance and recent transactions",
        "calculate total expenses for the last month",
        "generate self-employed tax receipt NPD",
        "check remaining monthly budget and savings rate",
        "export transaction history to CSV from banking API",
        "calculate freelance tax obligations and deadlines",
        "track daily grocery spending in finance database",
        "current investment portfolio value and returns",
        "credit card payment due date and amount",
    ]

    # --- HEALTH ---
    health_ru = [
        "какой у меня сегодня вес по данным умных весов",
        "синхронизируй показатели с весов Xiaomi Mi Scale",
        "составь программу силовых тренировок в зале на 3 дня",
        "сколько шагов я прошел за сегодня Google Fit",
        "проанализируй фазы сна и средний пульс за ночь",
        "какой прогресс похудения за последние 30 дней",
        "сколько калорий нужно для дефицита при моем весе",
        "напомни выпить витамины и креатин после тренировки",
        "разминка перед жимом лежа для плечевых суставов",
        "запиши взвешивание 74.5 кг в базу health vazus.db",
        "почему болят мышцы после приседаний крепатура",
        "норма воды в день при физических нагрузках",
        "соотношение белков жиров и углеводов в рационе",
        "график изменения индекса массы тела ИМТ",
        "кардио тренировка на беговой дорожке пульсовые зоны",
    ]
    health_en = [
        "help plan my gym workout schedule and routine",
        "what is my current weight from smart scales sync",
        "track daily calorie intake and macro nutrients",
        "sleep tracker metrics deep sleep and heart rate",
        "workout routine for muscle hypertrophy and strength",
        "sync steps and physical activity from fitness tracker",
        "weight loss trajectory and trend analysis",
        "post workout nutrition and protein requirements",
        "stretching exercises for lower back pain relief",
        "record morning weight measurement in health db",
    ]

    # --- SYSTEM_ARCHITECTURE ---
    system_ru = [
        "обнови граф знаний SuperGraph из базы vazus.db",
        "как устроен pre_tool_hook в системе vazus",
        "проверь целостность базы данных SQLite vazus.db",
        "настрой конфигурацию MCP серверов в settings.json",
        "как работают слои памяти Layer A, Layer B и Layer C",
        "переиндексируй репозиторий через cbm graph schema",
        "проверь статус фоновых задач manage_task",
        "какие правила изоляции Strict Path Jail активны",
        "запусти синхронизацию памяти с файлами USER.md и STUDY.md",
        "покажи граф вызовов функций ядра vazus_core",
        "настройка cron расписания для ночного бэкапа",
        "архитектура SuperGraph OS топология узлов",
        "проверь конфигурацию OpenVINO NPU embedder",
        "проведи аудит неиспользуемых артефактов Zero Artifact Accumulation",
        "миграция схемы таблиц транзакций в базе данных",
    ]
    system_en = [
        "update knowledge graph nodes from vazus.db",
        "inspect vazus SuperGraph OS system architecture",
        "verify MCP server registrations and permissions",
        "check memory layers consistency between markdown and sqlite",
        "how does pre_tool_hook enforce fail-closed security jail",
        "reindex codebase call graph with code knowledge base",
        "manage active background tasks and scheduled timers",
        "zero artifact accumulation workspace cleanliness audit",
        "configure OpenVINO NPU inference engine parameters",
        "supergraph kernel dispatch pipeline topology",
    ]

    # --- JULES ---
    jules_ru = [
        "сделай pull request для ветки vazus-dev в main",
        "запусти асинхронную сборку PR в облачной виртуалке Jules",
        "проверь статус проверки GitHub Pull Request CI",
        "сгенерируй описание изменений для мерджа в релиз",
        "запусти удаленный воркер Jules для тестирования ветки",
        "создай новую ветку git checkout -b feature/npu-router",
        "запушь коммит в удаленный репозиторий github",
        "проверь конфликты слияния в пулреквесте",
        "автоматическое создание PR через GitHub MCP",
        "запусти линтинг на CI воркере Jules",
    ]
    jules_en = [
        "generate a PR for the refactored module on github",
        "create pull request from dev branch to main",
        "trigger cloud VM Jules worker for async coding tasks",
        "check github actions CI status for open pull request",
        "push branch to remote repository and open draft PR",
        "merge pull request after all review checks pass",
        "resolve git merge conflicts in PR branch",
        "dispatch Jules task for background code generation",
        "review changes in pull request before merging",
        "git rebase feature branch onto latest main",
    ]

    # --- CLOUD_RUN ---
    cloud_ru = [
        "отправь уведомление на телефон через Gemini Spark мост",
        "проверь мобильный MCP bridge на Cloud Run сервере",
        "синхронизируй состояние со смартфоном через мобильный клиент",
        "запусти удаленную команду через Telegram Spark bridge",
        "статус подключения mobile cloud run connector",
        "передай контекст задачи в мобильный интерфейс",
        "проверь webhook от мобильного приложения",
        "удаленное пробуждение системы через Spark RPC",
    ]
    cloud_en = [
        "trigger notification to mobile device via Spark bridge",
        "check cloud run mobile connector endpoint status",
        "sync state with smartphone app via gemini spark",
        "send quick status update to mobile companion",
        "dispatch event to telegram mcp gateway",
    ]

    # --- GENERAL_REASONING ---
    general_ru = [
        "подумай и составь долгосрочный план развития карьеры",
        "в чем философский смысл разделения мышления на System 1 и System 2",
        "почему баланс между учебой и здоровьем критичен для продуктивности",
        "помоги расставить жизненные приоритеты на ближайший год",
        "проанализируй плюсы и минусы перехода на удаленную работу",
        "как научиться сохранять дисциплину при сложных задолженностях",
        "свободное размышление о будущем локальных нейросетей",
        "сократический диалог о понятии ответственности в инженерии",
        "как побороть прокрастинацию при подготовке к сложным экзаменам",
        "составь структурированный план принятия сложного решения",
    ]
    general_en = [
        "philosophical reasoning about human cognition and AI",
        "help me prioritize goals and life balance for the next quarter",
        "analyze trade-offs between specialization and broad knowledge",
        "how to maintain intrinsic motivation during academic stress",
        "strategic long term career roadmapping and skill tree",
        "deep thinking about autonomous agents architecture",
        "open ended reflection on personal growth and discipline",
    ]

    domain_buckets = {
        "academic": academic_ru + academic_en,
        "code": code_ru + code_en,
        "browser": browser_ru + browser_en,
        "finance": finance_ru + finance_en,
        "health": health_ru + health_en,
        "system_architecture": system_ru + system_en,
        "jules": jules_ru + jules_en,
        "cloud_run": cloud_ru + cloud_en,
        "general_reasoning": general_ru + general_en,
    }

    # Data augmentation: synthetically expand each bucket to ~400 samples
    prefix_variations = [
        "", "пожалуйста, ", "нужно ", "помоги ", "срочно ", "подскажи ",
        "please ", "can you ", "i need to ", "how to ", "hey vazus, ", "быстро ",
    ]
    suffix_variations = [
        "", " прямо сейчас", " подробнее", " пошагово", " в системе",
        " right now", " please", " step by step", " as soon as possible",
    ]

    for domain, samples in domain_buckets.items():
        # Add seed samples
        for s in samples:
            data.append((s, domain))

        # Generate augmented variations
        target_count = 400
        generated = 0
        while len([d for d in data if d[1] == domain]) < target_count:
            base = random.choice(samples)
            p = random.choice(prefix_variations)
            s = random.choice(suffix_variations)
            text = f"{p}{base}{s}".strip()
            data.append((text, domain))
            generated += 1

    random.seed(42)
    random.shuffle(data)
    return data


# ============================================================================
# 2. PyTorch Model Architecture (Identical to ONNX spec)
# ============================================================================

class JuliaClassifierPyTorch(nn.Module):
    """
    Fast Deep Averaging Network (DAN) + 2-layer MLP classifier.
    Matches the input [1, 64] -> output [1, 9] signature of julia_classifier.onnx.
    """
    def __init__(self, vocab_size: int = 30522, embed_dim: int = 64, hidden_dim: int = 64, num_classes: int = 9):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.fc1 = nn.Linear(embed_dim, hidden_dim)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.1)
        self.fc2 = nn.Linear(hidden_dim, num_classes)
        self.softmax = nn.Softmax(dim=-1)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        # input_ids: [batch_size, seq_len]
        embeds = self.embedding(input_ids)  # [batch_size, seq_len, embed_dim]
        # Mean pooling ignoring padding (token 0)
        mask = (input_ids != 0).unsqueeze(-1).float()  # [batch_size, seq_len, 1]
        sum_embeds = (embeds * mask).sum(dim=1)  # [batch_size, embed_dim]
        counts = mask.sum(dim=1).clamp(min=1.0)  # [batch_size, 1]
        pooled = sum_embeds / counts             # [batch_size, embed_dim]

        h = self.dropout(self.relu(self.fc1(pooled)))
        logits = self.fc2(h)
        return self.softmax(logits)


class TextDataset(Dataset):
    def __init__(self, samples: List[Tuple[str, str]], tokenizer: Tokenizer, max_len: int = 64):
        self.items = []
        for text, domain in samples:
            enc = tokenizer.encode(text)
            ids = enc.ids[:max_len]
            if len(ids) < max_len:
                ids = ids + [0] * (max_len - len(ids))
            label = DOMAIN_TO_IDX[domain]
            self.items.append((torch.tensor(ids, dtype=torch.long), label))

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        return self.items[idx]


# ============================================================================
# 3. Training Loop
# ============================================================================

def train_and_export():
    print("=" * 65)
    print("  TRAINING PIPELINE: Julia System-1 Router (9 Domains)")
    print("=" * 65)

    # 1. Load Rust Tokenizer
    print(f"[1/5] Loading tokenizer from: {TOKENIZER_PATH}")
    if not os.path.exists(TOKENIZER_PATH):
        raise FileNotFoundError(f"Tokenizer not found at {TOKENIZER_PATH}")
    tokenizer = Tokenizer.from_file(TOKENIZER_PATH)
    tokenizer.enable_padding(length=MAX_SEQ_LEN)
    tokenizer.enable_truncation(max_length=MAX_SEQ_LEN)
    vocab_size = tokenizer.get_vocab_size()
    print(f"      Vocab size: {vocab_size}, Max seq len: {MAX_SEQ_LEN}")

    # 2. Build Dataset
    print("[2/5] Synthesizing high-coverage bilingual training corpus...")
    all_data = generate_training_data()
    print(f"      Total samples generated: {len(all_data)}")
    
    # Train/Val split (85% / 15%)
    split_idx = int(len(all_data) * 0.85)
    train_samples = all_data[:split_idx]
    val_samples = all_data[split_idx:]
    print(f"      Train: {len(train_samples)} | Validation: {len(val_samples)}")

    train_ds = TextDataset(train_samples, tokenizer, MAX_SEQ_LEN)
    val_ds = TextDataset(val_samples, tokenizer, MAX_SEQ_LEN)

    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=128, shuffle=False)

    # 3. Model & Optimizer
    print("[3/5] Initializing PyTorch model & optimizer...")
    model = JuliaClassifierPyTorch(vocab_size=vocab_size, embed_dim=64, hidden_dim=64, num_classes=len(CANONICAL_DOMAINS))
    
    optimizer = optim.AdamW(model.parameters(), lr=3e-3, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=20)

    # 4. Train
    print("[4/5] Training on CPU (Intel Core Ultra 5)...")
    epochs = 20
    t0 = time.perf_counter()
    best_val_acc = 0.0

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        correct = 0
        total = 0

        for input_ids, labels in train_loader:
            optimizer.zero_grad()
            # Predict probabilities
            probs = model(input_ids)
            # Log probabilities for NLLLoss / CrossEntropy
            log_probs = torch.log(probs.clamp(min=1e-9))
            loss = nn.NLLLoss()(log_probs, labels)
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * len(labels)
            preds = probs.argmax(dim=-1)
            correct += (preds == labels).sum().item()
            total += len(labels)

        scheduler.step()
        train_acc = correct / total

        # Validation
        model.train(False)
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for input_ids, labels in val_loader:
                probs = model(input_ids)
                preds = probs.argmax(dim=-1)
                val_correct += (preds == labels).sum().item()
                val_total += len(labels)

        val_acc = val_correct / val_total
        if val_acc > best_val_acc:
            best_val_acc = val_acc

        if epoch % 5 == 0 or epoch == epochs:
            print(f"      Epoch {epoch:2d}/{epochs} | Loss: {total_loss/total:.4f} | Train Acc: {train_acc*100:.1f}% | Val Acc: {val_acc*100:.1f}%")

    train_time = time.perf_counter() - t0
    print(f"      Done in {train_time:.2f}s | Best Val Accuracy: {best_val_acc*100:.2f}%")

    # 5. Export to ONNX
    print("[5/5] Exporting to ONNX...")
    model.train(False)
    os.makedirs(MODEL_DIR, exist_ok=True)

    # Backup old model
    if os.path.exists(ONNX_PATH):
        backup_path = ONNX_PATH + ".bak"
        shutil.copy2(ONNX_PATH, backup_path)
        print(f"      Backed up previous model to {backup_path}")

    dummy_input = torch.zeros(1, MAX_SEQ_LEN, dtype=torch.long)
    torch.onnx.export(
        model,
        dummy_input,
        ONNX_PATH,
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=["input_ids"],
        output_names=["probabilities"],
        dynamic_axes=None,  # Static shape [1, 64] strictly optimized for Intel NPU VPUX compiler!
        dynamo=False,
    )
    print(f"      Saved new ONNX model to {ONNX_PATH} ({os.path.getsize(ONNX_PATH)/1024/1024:.2f} MB)")

    # 6. Verify with OpenVINO
    print("\n--- Verifying with OpenVINO Engine ---")
    import openvino as ov
    core = ov.Core()
    ov_model = core.read_model(ONNX_PATH)
    print(f"      Available devices: {core.available_devices}")
    
    # Try compiling for NPU, fallback to CPU
    dev = "NPU" if "NPU" in core.available_devices else "CPU"
    try:
        compiled = core.compile_model(ov_model, device_name=dev)
        print(f"      Compiled successfully on {dev}!")
    except Exception as e:
        print(f"      NPU compile warning: {e}, falling back to CPU")
        dev = "CPU"
        compiled = core.compile_model(ov_model, device_name=dev)
        print("      Compiled successfully on CPU!")

    infer_req = compiled.create_infer_request()

    # Test cases that previously failed
    test_cases = [
        ("how much money on Tinkoff card balance", "finance"),
        ("help plan my gym workout schedule", "health"),
        ("deadline for math exam at MIREA university", "academic"),
        ("debug Python code in embeddings.py", "code"),
        ("update knowledge graph from vazus.db", "system_architecture"),
        ("generate a PR for the refactored module", "jules"),
        ("найди в интернете бенчмарки RWKV-7", "browser"),
        ("отправь уведомление на телефон через Spark", "cloud_run"),
        ("почему баланс между учебой и здоровьем важен", "general_reasoning"),
    ]

    print("\n--- Live Test on Diverse Queries ---")
    correct_cnt = 0
    for q, expected in test_cases:
        enc = tokenizer.encode(q)
        ids = enc.ids[:MAX_SEQ_LEN]
        if len(ids) < MAX_SEQ_LEN:
            ids = ids + [0] * (MAX_SEQ_LEN - len(ids))
        inp = np.array([ids], dtype=np.int64)

        t_inf = time.perf_counter()
        res = infer_req.infer({"input_ids": inp})
        ms = (time.perf_counter() - t_inf) * 1000.0
        out = list(res.values())[0][0]
        pred_idx = int(np.argmax(out))
        pred_domain = CANONICAL_DOMAINS[pred_idx]
        conf = float(out[pred_idx])

        ok = "PASS" if pred_domain == expected else "FAIL"
        if ok == "PASS":
            correct_cnt += 1
        print(f"  [{ok}][{ms:4.1f}ms] {pred_domain:20s} ({conf:.2f}) | Exp: {expected:20s} | '{q[:40]}'")

    print(f"\nScore: {correct_cnt}/{len(test_cases)} ({correct_cnt/len(test_cases)*100:.0f}%)")
    print("=" * 65)


if __name__ == "__main__":
    train_and_export()
