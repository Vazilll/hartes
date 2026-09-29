"""
vazus_core.memory.j_space_tool_indexer
======================================
J-Space Tool Indexer:
Индексация всех инструментов (MCP-серверов и нативных модулей Vazus OS)
в виде 768D L2-нормированных векторов в таблице j_space_vectors (SQLite vazus.db).

Обеспечивает суб-миллисекундный семантический поиск релевантных инструментов
по косинусному сходству векторов на NPU/CPU.
"""

import glob
import json
import logging
import os
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from vazus_core.memory.embeddings import UnifiedEmbeddingManager, get_embedding_manager
from vazus_core.memory.j_space_vector_index import DEFAULT_DB_PATH, JSpaceVectorIndex

logger = logging.getLogger("vazus_core.memory.j_space_tool_indexer")

DEFAULT_MCP_DIR = Path(r"C:\Users\Vaz\.gemini\antigravity\mcp")


@dataclass
class ToolSpec:
    name: str
    module: str
    description: str
    keywords: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    is_native: bool = False

    @property
    def signature(self) -> str:
        return f"{self.name}: {self.description}. Keywords: {self.keywords}"


# Канонический реестр ключевых нативных модулей Vazus OS
NATIVE_MODULES_CATALOG: List[ToolSpec] = [
    # 1. vazus-sandbox
    ToolSpec(
        name="vazus-sandbox",
        module="vazus-sandbox",
        description="Запуск изолированной песочницы Windows Sandbox (WSB), аппаратная изоляция, VMBus, zero-artifact контроллер, безопасный запуск ненадежного кода, изоляция и тестирование.",
        keywords="запусти изолированную песочницу, изолированная песочница, песочница, sandbox, запуск песочницы, wsb, windows sandbox, аппаратная изоляция, vmbus, zero-artifact, изолированная среда, безопасный запуск",
        is_native=True,
    ),
    ToolSpec(
        name="sandbox_launch",
        module="vazus-sandbox",
        description="Запуск или подключение к изолированному экземпляру Windows Sandbox с активным сетевым мостом и гостевым агентом. Launch isolated Windows Sandbox.",
        keywords="запусти изолированную песочницу, запуск песочницы, sandbox_launch, launch sandbox, wsb, изоляция, старт sandbox, безопасное окружение",
        parameters={"force_restart": "bool", "timeout_sec": "int"},
        is_native=True,
    ),
    ToolSpec(
        name="sandbox_action",
        module="vazus-sandbox",
        description="Выполнение действий внутри Windows Sandbox: клики мыши, ввод текста, нажатие горячих клавиш, запуск команд PowerShell, запуск приложений.",
        keywords="действие в песочнице, клик, powershell, ввод текста, hotkey, mouse, execute, guest, автоматизация gui",
        parameters={"action": "str", "x": "int", "y": "int", "text": "str", "command": "str"},
        is_native=True,
    ),
    ToolSpec(
        name="sandbox_capture",
        module="vazus-sandbox",
        description="Снятие скриншота экрана гостевой системы Windows Sandbox с поддержкой Set-of-Mark (SoM) и распознаванием текста RapidOCR.",
        keywords="скриншот песочницы, снимок экрана, capture, som, rapidocr, framebuffer, визуал, распознавание текста",
        parameters={"mode": "str"},
        is_native=True,
    ),
    ToolSpec(
        name="sandbox_terminate",
        module="vazus-sandbox",
        description="Завершение работы и уничтожение сессии Windows Sandbox с полным сбросом состояния (zero-artifact).",
        keywords="закрыть песочницу, остановить sandbox, terminate, cleanup, kill sandbox, сброс состояния, zero-artifact",
        is_native=True,
    ),
    ToolSpec(
        name="wsb_sandbox_controller",
        module="vazus-sandbox",
        description="Контроллер аппаратной изоляции Windows Sandbox (WSB), генерация конфигураций .wsb, запуск команд с нулевым следом (zero-artifact), обмен через VMBus.",
        keywords="контроллер песочницы, windows sandbox, wsb_sandbox_controller, vmbus, zero-artifact, аппаратная изоляция, генерация wsb",
        is_native=True,
    ),
    # 2. vazus-organic
    ToolSpec(
        name="vazus-organic",
        module="vazus-organic",
        description="Органическая память и самообучение Vazus OS: запись проверенных инсайтов, адаптация реактивных параметров, факты Mem0 в vazus.db.",
        keywords="органическая память, vazus-organic, самообучение, инсайты, адаптивные параметры, mem0, долговременная память",
        is_native=True,
    ),
    ToolSpec(
        name="vazus_record_insight",
        module="vazus-organic",
        description="Запись проверенного инсайта, архитектурного урока или оптимизации кода в органическую память vazus.db.",
        keywords="инсайт, insight, органическая память, vazus.db, архитектурный урок, запись памяти, learn, vazus_record_insight",
        parameters={"category": "str", "insight": "str"},
        is_native=True,
    ),
    ToolSpec(
        name="vazus_update_reactive_parameter",
        module="vazus-organic",
        description="Обновление значения реактивного системного параметра и порогов адаптации в vazus.db.",
        keywords="реактивный параметр, reactive parameter, порог, threshold, тюнинг, vazus.db, vazus_update_reactive_parameter",
        parameters={"name": "str", "value": "float", "reason": "str"},
        is_native=True,
    ),
    ToolSpec(
        name="vazus_mem0_add_fact",
        module="vazus-organic",
        description="Добавление подтвержденного факта в память Mem0 (vazus.db) с би-темпоральной меткой и валидацией.",
        keywords="добавить факт, mem0, факт, би-темпоральный, память, knowledge, vazus_mem0_add_fact",
        parameters={"fact": "str", "entity": "str", "category": "str"},
        is_native=True,
    ),
    ToolSpec(
        name="vazus_mem0_search",
        module="vazus-organic",
        description="Семантический и точный поиск фактов в базе знаний Mem0 по ключевым словам или вектору.",
        keywords="поиск фактов, mem0 search, найти факт, семантический поиск, память, vazus_mem0_search",
        parameters={"query": "str", "top_k": "int"},
        is_native=True,
    ),
    # 3. cbm (Code Base Manager)
    ToolSpec(
        name="cbm",
        module="cbm",
        description="Code Base Manager (CBM): граф кодовой базы, AST-индексация, связи зависимостей, поиск сниппетов и архитектура.",
        keywords="cbm, code base manager, граф кода, ast граф, архитектура кодовой базы, поиск кода",
        is_native=True,
    ),
    ToolSpec(
        name="get_code_snippet",
        module="cbm",
        description="Получение фрагмента исходного кода по символу, функции или диапазону строк из графа кодовой базы.",
        keywords="код, сниппет, функция, get_code_snippet, cbm, фрагмент кода, ast, исходный код",
        parameters={"symbol": "str", "path": "str", "start_line": "int", "end_line": "int"},
        is_native=True,
    ),
    ToolSpec(
        name="search_graph",
        module="cbm",
        description="Поиск по графу кодовой базы (узлы, вызовы, зависимости, AST, call graph).",
        keywords="поиск по графу, call graph, граф кода, зависимости, cbm, search_graph, граф вызовов",
        parameters={"query": "str", "node_type": "str"},
        is_native=True,
    ),
    ToolSpec(
        name="get_architecture",
        module="cbm",
        description="Получение высокоуровневой архитектурной структуры кодовой базы и связей модулей.",
        keywords="архитектура, структура модулей, get_architecture, cbm, топология кода, слои системы",
        parameters={"scope": "str"},
        is_native=True,
    ),
    # 4. code-quality
    ToolSpec(
        name="code-quality",
        module="code-quality",
        description="Анализ качества кода, статический анализ AST, профилирование производительности и расчет цикломатической сложности.",
        keywords="качество кода, code-quality, ast-grep, профилирование, сложность кода, рефакторинг, линтинг",
        is_native=True,
    ),
    ToolSpec(
        name="ast_grep_search",
        module="code-quality",
        description="Структурный синтаксический поиск по абстрактному синтаксическому дереву (AST) с использованием ast-grep.",
        keywords="ast grep, поиск по ast, качество кода, паттерны, code quality, ast_grep_search",
        parameters={"pattern": "str", "path": "str"},
        is_native=True,
    ),
    ToolSpec(
        name="pyinstrument_profile",
        module="code-quality",
        description="Профилирование производительности Python-скрипта через PyInstrument (выявление узких мест CPU, flamegraph).",
        keywords="профилирование, pyinstrument, профайлер, cpu bottleneck, бенчмарк производительности, pyinstrument_profile",
        parameters={"script_path": "str", "args": "list"},
        is_native=True,
    ),
    ToolSpec(
        name="radon_complexity",
        module="code-quality",
        description="Расчет цикломатической сложности кода (Cyclomatic Complexity, McCabe) через Radon.",
        keywords="сложность кода, radon, цикломатическая сложность, maintainability, метрики кода, radon_complexity",
        parameters={"path": "str"},
        is_native=True,
    ),
    # 5. db_backup
    ToolSpec(
        name="db_backup",
        module="db_backup",
        description="Резервное копирование SQLite базы данных vazus.db (WAL mode online backup), проверка целостности, ротация и синхронизация в Google Drive.",
        keywords="сделай бэкап базы, бэкап базы, db_backup, резервная копия vazus.db, резервное копирование, сбережение данных, sqlite backup",
        is_native=True,
    ),
    ToolSpec(
        name="run_backup",
        module="db_backup",
        description="Создание безопасного резервного бэкапа базы данных SQLite (vazus.db) через sqlite3.backup() API с PRAGMA integrity_check, ротацией и GDrive sync.",
        keywords="сделай бэкап базы, сделать бэкап, run_backup, создать резервную копию, бэкап sqlite, backup vazus.db, сохранить базу",
        parameters={"verify": "bool", "sync_gdrive": "bool"},
        is_native=True,
    ),
    ToolSpec(
        name="get_backup_status",
        module="db_backup",
        description="Просмотр текущего инвентаря бэкапов базы данных, возраста последнего бэкапа и общего размера.",
        keywords="статус бэкапа, список бэкапов, возраст бэкапа, backup status, инвентарь, get_backup_status",
        parameters={},
        is_native=True,
    ),
    # 6. dream_consolidator
    ToolSpec(
        name="dream_consolidator",
        module="dream_consolidator",
        description="Сон и ночная консолидация памяти (Mem0 Dream consolidation): сжатие уроков, дедупликация фактов, очистка графа, WAL checkpoint и VACUUM vazus.db.",
        keywords="консолидация памяти, dream_consolidator, сон, dream consolidation, сжатие памяти, чистка vazus.db, дедупликация фактов, vacuum",
        is_native=True,
    ),
    ToolSpec(
        name="run_dream_consolidation",
        module="dream_consolidator",
        description="Запуск ночной консолидации памяти (Mem0 Dream consolidation): дедупликация уроков, разрешение конфликтов би-темпоральных фактов, очистка графа, WAL checkpoint и VACUUM vazus.db.",
        keywords="запусти консолидацию памяти, run_dream_consolidation, ночная консолидация, оптимизация памяти, сжатие базы",
        parameters={"run_vacuum": "bool"},
        is_native=True,
    ),
    # 7. desktop-commander
    ToolSpec(
        name="desktop-commander",
        module="desktop-commander",
        description="Управление процессами Windows, запуск приложений, консольные команды, чтение вывода и взаимодействие с процессами.",
        keywords="desktop-commander, управление процессами, системные команды, запуск приложений, windows процессы",
        is_native=True,
    ),
    ToolSpec(
        name="list_processes",
        module="desktop-commander",
        description="Список запущенных процессов операционной системы с PID, именем и потреблением ресурсов.",
        keywords="процессы, список процессов, list_processes, tasklist, pid, cpu, ram, активные программы",
        parameters={},
        is_native=True,
    ),
    ToolSpec(
        name="start_process",
        module="desktop-commander",
        description="Запуск нового процесса или приложения в операционной системе Windows.",
        keywords="запустить процесс, старт программы, запуск приложения, start_process, execute",
        parameters={"command": "str", "cwd": "str"},
        is_native=True,
    ),
    ToolSpec(
        name="read_process_output",
        module="desktop-commander",
        description="Чтение stdout/stderr запущенного фонового процесса.",
        keywords="вывод процесса, логи процесса, stdout, stderr, read_process_output",
        parameters={"pid": "int"},
        is_native=True,
    ),
    ToolSpec(
        name="interact_with_process",
        module="desktop-commander",
        description="Взаимодействие с интерактивным процессом через stdin.",
        keywords="ввод в процесс, stdin, интерактивный ввод, interact_with_process",
        parameters={"pid": "int", "input_text": "str"},
        is_native=True,
    ),
    # 8. telegram-mcp
    ToolSpec(
        name="telegram-mcp",
        module="telegram-mcp",
        description="Интеграция с Telegram: поиск диалогов, чтение истории сообщений и загрузка медиафайлов.",
        keywords="telegram-mcp, телеграм, telegram клиент, чаты, сообщения, медиа файлы",
        is_native=True,
    ),
    ToolSpec(
        name="tg_search_dialogs",
        module="telegram-mcp",
        description="Поиск диалогов и чатов в Telegram по имени или тексту.",
        keywords="телеграм, telegram чаты, поиск диалогов, tg_search_dialogs, мессенджер",
        parameters={"query": "str", "limit": "int"},
        is_native=True,
    ),
    ToolSpec(
        name="tg_get_history",
        module="telegram-mcp",
        description="Получение истории сообщений из выбранного чата Telegram.",
        keywords="история телеграм, сообщения telegram, tg_get_history, чат логи",
        parameters={"chat_id": "str", "limit": "int"},
        is_native=True,
    ),
    ToolSpec(
        name="tg_download_media",
        module="telegram-mcp",
        description="Скачивание медиафайлов (фото, документы, голосовые) из Telegram.",
        keywords="скачать из телеграм, загрузка медиа, фото, документы, tg_download_media",
        parameters={"message_id": "str", "output_dir": "str"},
        is_native=True,
    ),
]


def stem_word(word: str) -> str:
    """Нормализует основу слова для русского и английского языков."""
    w = word.lower().strip()
    if not w:
        return ""
    # Русские грамматические окончания
    ru_suffixes = [
        "ными",
        "ного",
        "ному",
        "ную",
        "ная",
        "ное",
        "ные",
        "ных",
        "ным",
        "ицу",
        "ица",
        "ицы",
        "ице",
        "ицей",
        "ами",
        "ями",
        "ов",
        "ев",
        "ей",
        "ам",
        "ям",
        "ом",
        "ем",
        "ой",
        "ей",
        "а",
        "я",
        "у",
        "ю",
        "о",
        "е",
        "ы",
        "и",
    ]
    for s in ru_suffixes:
        if w.endswith(s) and len(w) - len(s) >= 3:
            return w[: -len(s)]
    # Английские окончания
    en_suffixes = ["tion", "ing", "ies", "ied", "ed", "es", "s"]
    for s in en_suffixes:
        if w.endswith(s) and len(w) - len(s) >= 3:
            return w[: -len(s)]
    return w


class JSpaceToolIndexer:
    """
    Управляет каталогизацией и 768D L2-векторизацией инструментов
    в семантическом пространстве J-Space (SQLite vazus.db).
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        mcp_dir: Optional[str] = None,
        embedding_manager: Optional[UnifiedEmbeddingManager] = None,
    ):
        raw_db = db_path or os.environ.get("VAZUS_DB_PATH") or str(DEFAULT_DB_PATH)
        self.db_path = str(raw_db)
        raw_mcp = mcp_dir or os.environ.get("ANTIGRAVITY_MCP_DIR") or str(DEFAULT_MCP_DIR)
        self.mcp_dir = Path(raw_mcp)

        self.vector_index = JSpaceVectorIndex(db_path=self.db_path)
        self._embedding_manager = embedding_manager

        self._ensure_meta_table()
        self._cached_specs: Dict[str, ToolSpec] = {}

    @property
    def embedding_manager(self) -> UnifiedEmbeddingManager:
        if self._embedding_manager is None:
            self._embedding_manager = get_embedding_manager(dimension=768)
        return self._embedding_manager

    @embedding_manager.setter
    def embedding_manager(self, value: UnifiedEmbeddingManager) -> None:
        self._embedding_manager = value

    def get_status(self) -> Dict[str, Any]:
        """
        Возвращает статус индекса J-Space:
        - indexed_tools / indexed_tools_count: количество инструментов в j_space_tool_metadata
        - vectors_count: количество векторов в j_space_vectors
        - table_status: статус таблицы ("ONLINE", "EXISTS", "NOT_FOUND", "ERROR")
        - status: общий статус ("ONLINE", "READY", "EMPTY", "ERROR")
        """
        conn = self.vector_index._get_connection()
        try:
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='j_space_vectors'")
            has_vectors_table = cur.fetchone() is not None

            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='j_space_tool_metadata'")
            has_meta_table = cur.fetchone() is not None

            vectors_count = 0
            if has_vectors_table:
                cur = conn.execute("SELECT COUNT(*) FROM j_space_vectors")
                vectors_count = cur.fetchone()[0]

            indexed_tools = 0
            if has_meta_table:
                cur = conn.execute("SELECT COUNT(*) FROM j_space_tool_metadata")
                indexed_tools = cur.fetchone()[0]

            table_status = "ONLINE" if has_vectors_table else "NOT_FOUND"
            status = (
                "ONLINE" if (has_vectors_table and vectors_count > 0) else ("READY" if has_vectors_table else "OFFLINE")
            )

            return {
                "status": status,
                "table_status": table_status,
                "vectors_count": vectors_count,
                "indexed_tools": indexed_tools,
                "indexed_tools_count": indexed_tools,
                "db_path": self.db_path,
            }
        except Exception as e:
            logger.debug("Failed to get J-Space indexer status: %s", e)
            return {
                "status": "ERROR",
                "table_status": "ERROR",
                "vectors_count": 0,
                "indexed_tools": 0,
                "indexed_tools_count": 0,
                "db_path": self.db_path,
                "error": str(e),
            }
        finally:
            self.vector_index._release_connection(conn)

    def _ensure_meta_table(self) -> None:
        """Создает таблицу метаданных инструментов j_space_tool_metadata."""
        conn = self.vector_index._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS j_space_tool_metadata (
                    tool_name TEXT PRIMARY KEY,
                    module TEXT NOT NULL,
                    description TEXT NOT NULL,
                    parameters_json TEXT,
                    keywords TEXT,
                    signature TEXT,
                    is_native INTEGER DEFAULT 0,
                    updated_at REAL NOT NULL,
                    weight REAL DEFAULT 1.0
                );
            """)
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(j_space_tool_metadata)")
            cols = [r[1] for r in cur.fetchall()]
            if "weight" not in cols:
                try:
                    conn.execute("ALTER TABLE j_space_tool_metadata ADD COLUMN weight REAL DEFAULT 1.0")
                except Exception:
                    pass

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_j_space_tool_meta_module
                ON j_space_tool_metadata(module);
            """)
            conn.commit()
        finally:
            self.vector_index._release_connection(conn)

    def scan_mcp_schemas(self) -> List[ToolSpec]:
        """
        Сканирует все схемы MCP в C:\\Users\\Vaz\\.gemini\\antigravity\\mcp\\*\\*.json.
        """
        tools: List[ToolSpec] = []
        if not self.mcp_dir.exists():
            logger.warning("MCP directory does not exist: %s", self.mcp_dir)
            return tools

        json_pattern = str(self.mcp_dir / "*" / "*.json")
        json_files = glob.glob(json_pattern)

        for json_path in json_files:
            p = Path(json_path)
            server_name = p.parent.name
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if not isinstance(data, dict):
                    continue

                name = data.get("name") or p.stem
                description = data.get("description", "")
                parameters = data.get("parameters", {})

                # Извлекаем параметры для ключевых слов
                props = parameters.get("properties", {}) if isinstance(parameters, dict) else {}
                param_names = list(props.keys())

                # Формируем ключевые слова
                name_parts = [part for part in name.replace("-", "_").split("_") if part]
                kw_set = set([name, server_name] + name_parts + param_names)
                keywords = ", ".join(sorted(kw_set))

                tools.append(
                    ToolSpec(
                        name=name,
                        module=server_name,
                        description=description,
                        keywords=keywords,
                        parameters=props,
                        is_native=False,
                    )
                )
            except Exception as e:
                logger.warning("Failed to parse MCP schema %s: %s", json_path, e)

        return tools

    def collect_all_tools(self) -> List[ToolSpec]:
        """
        Собирает полный каталог: MCP инструменты + канонические нативные модули.
        Нативные спецификации обогащают и дополняют схемы MCP.
        """
        tools_by_name: Dict[str, ToolSpec] = {}

        # 1. MCP сканирование
        mcp_tools = self.scan_mcp_schemas()
        for t in mcp_tools:
            tools_by_name[t.name] = t

        # 2. Нативные модули Vazus OS (приоритетное объединение)
        for nat in NATIVE_MODULES_CATALOG:
            if nat.name in tools_by_name:
                # Обогащаем существующий MCP инструмент русскими ключевыми словами и деталями
                existing = tools_by_name[nat.name]
                merged_desc = f"{nat.description} {existing.description}".strip()
                merged_kw = f"{nat.keywords}, {existing.keywords}".strip(", ")
                merged_props = {**existing.parameters, **nat.parameters}
                tools_by_name[nat.name] = ToolSpec(
                    name=nat.name,
                    module=nat.module,
                    description=merged_desc,
                    keywords=merged_kw,
                    parameters=merged_props,
                    is_native=True,
                )
            else:
                tools_by_name[nat.name] = nat

        return list(tools_by_name.values())

    def index_tools(self, force_reindex: bool = True) -> Dict[str, Any]:
        """
        Индексирует все инструменты в J-пространстве:
        1. Формирует текстовые сигнатуры: f"{tool_name}: {description}. Keywords: {keywords}".
        2. Вычисляет 768D эмбеддинги через UnifiedEmbeddingManager / OpenVINO NPU.
        3. Сохраняет векторы через JSpaceVectorIndex с source='tool_catalog',
           concept_id=f"tool:{tool_name}", semantic_label=tool_name.
        4. Сохраняет метаданные в j_space_tool_metadata.
        """
        t0 = time.perf_counter()
        tools = self.collect_all_tools()

        conn = self.vector_index._get_connection()
        indexed_count = 0
        now = time.time()

        try:
            if force_reindex:
                conn.execute("DELETE FROM j_space_vectors WHERE source = 'tool_catalog'")
                conn.execute("DELETE FROM j_space_tool_metadata")

            for tool in tools:
                sig = tool.signature
                # Вычисляем 768D вектор через UnifiedEmbeddingManager (NPU/CPU)
                vec_list = self.embedding_manager.get_embedding(sig)
                vec = np.asarray(vec_list, dtype=np.float32).flatten()
                norm = np.linalg.norm(vec)
                if norm > 1e-6:
                    vec = vec / norm

                # Сохраняем вектор в J-Space
                concept_id = f"tool:{tool.name}"
                record_id = str(uuid.uuid4())
                conn.execute("DELETE FROM j_space_vectors WHERE concept_id = ?", (concept_id,))
                conn.execute(
                    """
                    INSERT INTO j_space_vectors (id, concept_id, semantic_label, salience, vector, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (record_id, concept_id, tool.name, 1.0, vec.tobytes(), "tool_catalog", now),
                )

                # Сохраняем метаданные инструмента
                conn.execute(
                    """
                    INSERT INTO j_space_tool_metadata 
                    (tool_name, module, description, parameters_json, keywords, signature, is_native, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(tool_name) DO UPDATE SET
                        module=excluded.module,
                        description=excluded.description,
                        parameters_json=excluded.parameters_json,
                        keywords=excluded.keywords,
                        signature=excluded.signature,
                        is_native=excluded.is_native,
                        updated_at=excluded.updated_at
                    """,
                    (
                        tool.name,
                        tool.module,
                        tool.description,
                        json.dumps(tool.parameters, ensure_ascii=False),
                        tool.keywords,
                        sig,
                        1 if tool.is_native else 0,
                        now,
                    ),
                )
                self._cached_specs[tool.name] = tool
                indexed_count += 1

            conn.commit()
        finally:
            self.vector_index._release_connection(conn)

        dt = time.perf_counter() - t0
        logger.info(
            "Indexed %d tools in J-Space in %.2f seconds (%.1f ms/tool)",
            indexed_count,
            dt,
            (dt / indexed_count * 1000) if indexed_count else 0.0,
        )

        return {
            "indexed_count": indexed_count,
            "duration_seconds": round(dt, 2),
            "db_path": self.db_path,
        }

    def _load_metadata_map(self) -> Dict[str, Dict[str, Any]]:
        """Загружает карту метаданных инструментов из SQLite базы."""
        conn = self.vector_index._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(j_space_tool_metadata)")
            cols = [r[1] for r in cur.fetchall()]
            has_weight = "weight" in cols
            query = (
                "SELECT tool_name, module, description, parameters_json, keywords, signature, is_native, weight FROM j_space_tool_metadata"
                if has_weight
                else "SELECT tool_name, module, description, parameters_json, keywords, signature, is_native FROM j_space_tool_metadata"
            )
            cur = conn.execute(query)
            rows = cur.fetchall()
            meta = {}
            for r in rows:
                meta[r["tool_name"]] = {
                    "tool_name": r["tool_name"],
                    "module": r["module"],
                    "description": r["description"],
                    "parameters": json.loads(r["parameters_json"]) if r["parameters_json"] else {},
                    "keywords": r["keywords"],
                    "signature": r["signature"],
                    "is_native": bool(r["is_native"]),
                    "weight": float(r["weight"]) if has_weight and r["weight"] is not None else 1.0,
                }
            return meta
        finally:
            self.vector_index._release_connection(conn)

    def find_tools_for_query(
        self,
        query: str,
        top_k: int = 3,
        min_similarity: float = 0.35,
    ) -> List[Dict[str, Any]]:
        """
        Ищет наиболее релевантные инструменты в J-пространстве по естественному языковому запросу.

        Args:
            query: Запрос пользователя (например: 'запусти изолированную песочницу', 'сделай бэкап базы').
            top_k: Максимальное количество возвращаемых инструментов.
            min_similarity: Минимальный порог косинусного сходства (по умолчанию 0.35).

        Returns:
            Список словарей с информацией об инструментах:
            - tool_name: имя инструмента
            - module: имя модуля/сервера (например 'vazus-sandbox', 'db_backup')
            - description: текстовое описание
            - similarity: косинусное сходство (от 0.0 до 1.0)
            - parameters: схема параметров
            - keywords: ключевые слова
            - concept_id: идентификатор в J-Space ('tool:...')
            - source: 'tool_catalog'
        """
        if not query or not query.strip():
            return []

        # 1. Вычисляем 768D эмбеддинг запроса
        q_vec = self.embedding_manager.get_embedding(query)
        q_arr = np.asarray(q_vec, dtype=np.float32)

        # 2. Выполняем векторизованный косинусный поиск в j_space_vectors
        # Берем широкий пул кандидатов (до 60), чтобы лексический буст вывел точные совпадения в топ
        vector_matches = self.vector_index.search_similar(
            query_vector=q_arr,
            top_k=max(top_k * 10, 60),
            min_similarity=min_similarity,
            source="tool_catalog",
        )

        if not vector_matches:
            return []

        # 3. Обогащаем результаты метаданными
        meta_map = self._load_metadata_map()
        results: List[Dict[str, Any]] = []

        query_stems = [stem_word(t) for t in query.replace("_", " ").replace("-", " ").split() if len(t) > 2]

        for m in vector_matches:
            tool_name = m["semantic_label"]
            meta = meta_map.get(tool_name, {})
            module = meta.get("module", tool_name)
            desc = meta.get("description", "")
            kw = meta.get("keywords", "")

            sim = float(m["similarity"])

            # Лексический буст при совпадении основ слов запроса
            # в названии инструмента, названии модуля или ключевых словах
            searchable_text = f"{tool_name} {module} {kw} {desc}".lower()
            name_and_kw_text = f"{tool_name} {module} {kw}".lower()

            lexical_boost = 0.0
            matched_stems = 0
            for st in query_stems:
                if not st:
                    continue
                if st in name_and_kw_text:
                    lexical_boost += 0.06
                    matched_stems += 1
                elif st in searchable_text:
                    lexical_boost += 0.03
                    matched_stems += 1

            if matched_stems >= len(query_stems) and query_stems:
                lexical_boost += 0.05

            weight = float(meta.get("weight", 1.0))
            weight = max(0.6, min(1.4, weight))
            raw_score = sim + lexical_boost
            total_sim = round(min(1.0, max(0.0, raw_score * weight)), 4)

            results.append(
                {
                    "tool_name": tool_name,
                    "module": module,
                    "description": desc,
                    "similarity": total_sim,
                    "raw_similarity": sim,
                    "weight": weight,
                    "parameters": meta.get("parameters", {}),
                    "keywords": kw,
                    "concept_id": m["concept_id"],
                    "source": m["source"],
                    "is_native": meta.get("is_native", False),
                }
            )

        # Сортируем по итоговому сходству
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def reweight_tools_from_activations(self, min_proposals: int = 2) -> Dict[str, Any]:
        """
        Calculates tool hit rates from j_space_tool_activations and adaptively re-weights tools in J-Space:
          hit_rate = used / proposed
          weight = 1.0 + (hit_rate - 0.5) * 0.4 (bounded to [0.7, 1.3])
        """
        conn = self.vector_index._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(j_space_tool_metadata)")
            meta_cols = [r[1] for r in cur.fetchall()]
            if "weight" not in meta_cols:
                try:
                    conn.execute("ALTER TABLE j_space_tool_metadata ADD COLUMN weight REAL DEFAULT 1.0")
                except Exception:
                    pass

            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='j_space_tool_activations'")
            if not cur.fetchone():
                return {"reweighted_count": 0, "message": "No activations table found", "tools": {}}

            cur.execute("PRAGMA table_info(j_space_tool_activations)")
            act_cols = [r[1] for r in cur.fetchall()]
            if "was_used" not in act_cols:
                return {"reweighted_count": 0, "message": "was_used column missing", "tools": {}}

            cur.execute("""
                SELECT tool_name,
                       COUNT(*) as proposed,
                       SUM(CASE WHEN was_used = 1 THEN 1 ELSE 0 END) as used
                FROM j_space_tool_activations
                GROUP BY tool_name
            """)
            stats = cur.fetchall()

            reweighted = {}
            for row in stats:
                tool_name = row[0]
                proposed = row[1]
                used = row[2] or 0

                if proposed < min_proposals:
                    continue

                hit_rate = used / proposed
                new_weight = round(max(0.7, min(1.3, 1.0 + (hit_rate - 0.5) * 0.4)), 3)

                conn.execute("UPDATE j_space_tool_metadata SET weight = ? WHERE tool_name = ?", (new_weight, tool_name))
                reweighted[tool_name] = {
                    "proposed": proposed,
                    "used": used,
                    "hit_rate": round(hit_rate, 3),
                    "weight": new_weight,
                }

            conn.commit()
            return {
                "reweighted_count": len(reweighted),
                "tools": reweighted,
                "status": "SUCCESS",
            }
        finally:
            self.vector_index._release_connection(conn)


def get_tool_indexer(db_path: Optional[str] = None) -> JSpaceToolIndexer:
    """Фабричная функция синглтона индексатора инструментов."""
    return JSpaceToolIndexer(db_path=db_path)


def record_j_space_tool_activation(
    tool_name: str,
    prompt: str = "",
    invocation_num: int = 1,
    db_path: Optional[str] = None,
) -> bool:
    """Records that a tool was activated/suggested to the agent (was_used=0)."""
    target_db = db_path or os.environ.get("VAZUS_DB_PATH") or str(DEFAULT_DB_PATH)
    try:
        conn = sqlite3.connect(target_db, timeout=3.0)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS j_space_tool_activations (
                tool_name TEXT,
                prompt TEXT,
                invocation_num INTEGER,
                timestamp TEXT,
                was_used INTEGER DEFAULT 0
            )
        """)
        conn.execute(
            """INSERT INTO j_space_tool_activations (tool_name, prompt, invocation_num, timestamp, was_used)
               VALUES (?, ?, ?, datetime('now'), 0)""",
            (tool_name, prompt, invocation_num),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.debug("Failed recording tool activation for %s: %s", tool_name, e)
        return False


def record_j_space_tool_usage(tool_name: str, db_path: Optional[str] = None) -> bool:
    """Marks the latest activation of tool_name as used (was_used=1)."""
    target_db = db_path or os.environ.get("VAZUS_DB_PATH") or str(DEFAULT_DB_PATH)
    try:
        conn = sqlite3.connect(target_db, timeout=3.0)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS j_space_tool_activations (
                tool_name TEXT,
                prompt TEXT,
                invocation_num INTEGER,
                timestamp TEXT,
                was_used INTEGER DEFAULT 0
            )
        """)
        cur = conn.execute(
            """SELECT rowid FROM j_space_tool_activations
               WHERE tool_name = ? AND was_used = 0
               ORDER BY rowid DESC LIMIT 1""",
            (tool_name,),
        )
        row = cur.fetchone()
        if row:
            conn.execute("UPDATE j_space_tool_activations SET was_used = 1 WHERE rowid = ?", (row[0],))
            conn.commit()
            conn.close()
            return True
        conn.close()
        return False
    except Exception as e:
        logger.debug("Failed recording tool usage for %s: %s", tool_name, e)
        return False



if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    indexer = JSpaceToolIndexer()

    args = sys.argv[1:]
    if "--index" in args or not args:
        print("[JSpaceToolIndexer] Indexing all tools...")
        stats = indexer.index_tools(force_reindex=True)
        print(f"[JSpaceToolIndexer] Index complete: {stats}")

    test_queries = [
        "запусти изолированную песочницу",
        "сделай бэкап базы",
        "найди фрагмент кода функции",
        "профилируй производительность",
        "запусти консолидацию памяти",
    ]

    print("\n--- Running Test Queries in J-Space ---")
    for q in test_queries:
        res = indexer.find_tools_for_query(q, top_k=2)
        print(f"\nQuery: '{q}'")
        for idx_r, r in enumerate(res, 1):
            print(f"  [{idx_r}] tool: {r['tool_name']} (module: {r['module']}, sim: {r['similarity']:.4f})")
            print(f"      desc: {r['description'][:90]}...")
