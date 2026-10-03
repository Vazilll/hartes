"""
Unit tests for vazus_core Universal Multi-Language AST Pruner (Python, Go, C).
"""

import pytest
from vazus_core.verification.ast_pruner import (
    ASTPruner,
    DocstringAndBodyPruner,
    GoTreeSitterPruner,
    CTreeSitterPruner,
    UniversalASTPruner,
    prune_go_code,
    prune_c_code,
    prune_universal_code,
)


def test_python_ast_pruning_basic():
    py_code = '''
def calculate_metrics(data: list[int], factor: float = 1.5) -> dict:
    """Calculates summary metrics with multiplier factor."""
    total = sum(data) * factor
    avg = total / max(1, len(data))
    return {"total": total, "avg": avg}

class DataProcessor:
    """Processes pipeline data streams."""
    def __init__(self, name: str):
        self.name = name

    def process(self, items: list[str]) -> list[str]:
        return [i.strip().lower() for i in items if i]
'''
    pruned, stats = ASTPruner.prune_code_string(py_code)
    assert stats["is_valid"] is True
    assert stats["language"] == "python"
    assert stats["reduction_percentage"] > 20.0
    assert "def calculate_metrics" in pruned
    assert "class DataProcessor" in pruned
    assert "def process" in pruned


def test_go_tree_sitter_pruning():
    go_code = '''package main

import (
\t"context"
\t"fmt"
\t"sync"
)

// BotConfig holds configuration parameters
type BotConfig struct {
\tToken   string
\tTimeout int
}

// TelegramBot interface
type TelegramBot interface {
\tStart(ctx context.Context) error
\tSendMessage(chatID int64, text string) error
}

type BotService struct {
\tmu sync.Mutex
\tcfg BotConfig
}

func NewBotService(cfg BotConfig) *BotService {
\treturn &BotService{cfg: cfg}
}

func (b *BotService) Start(ctx context.Context) error {
\tb.mu.Lock()
\tdefer b.mu.Unlock()
\tfmt.Printf("Starting bot with token prefix: %s\\n", b.cfg.Token[:4])
\tfor i := 0; i < 10; i++ {
\t\tfmt.Println("Warming up connections...", i)
\t}
\treturn nil
}

func (b *BotService) SendMessage(chatID int64, text string) error {
\tb.mu.Lock()
\tdefer b.mu.Unlock()
\tfmt.Printf("Sending message to %d: %s\\n", chatID, text)
\treturn nil
}
'''
    pruned, stats = GoTreeSitterPruner.prune_code_string(go_code)
    assert stats["is_valid"] is True
    assert stats["language"] == "go"
    assert stats["pruned_functions"] == 3
    assert stats["nodes_removed"] > 0
    assert "type BotConfig struct" in pruned
    assert "type TelegramBot interface" in pruned
    assert "func NewBotService(cfg BotConfig) *BotService" in pruned
    assert "func (b *BotService) Start(ctx context.Context) error" in pruned
    assert "func (b *BotService) SendMessage(chatID int64, text string) error" in pruned
    assert 'panic("skeleton")' in pruned


def test_go_signature_extraction():
    go_code = '''package service

type Handler struct {
    ID string
}

func HandleRequest(w string, r int) error {
    return nil
}
'''
    sigs = GoTreeSitterPruner.extract_signatures(go_code)
    assert sigs["language"] == "go"
    assert "package service" in sigs["package"]
    assert len(sigs["types"]) >= 1
    assert len(sigs["functions"]) >= 1


def test_c_tree_sitter_pruning():
    c_code = '''#include <stdio.h>
#include <stdlib.h>

typedef struct {
    int id;
    char name[32];
} Worker;

int process_task(Worker* w, int priority) {
    if (!w) return -1;
    printf("Processing task for worker %d\\n", w->id);
    return 0;
}

int main(int argc, char** argv) {
    Worker w = {1, "WorkerA"};
    return process_task(&w, 10);
}
'''
    pruned, stats = CTreeSitterPruner.prune_code_string(c_code)
    assert stats["is_valid"] is True
    assert stats["language"] == "c"
    assert stats["pruned_functions"] == 2
    assert "typedef struct" in pruned
    assert "int process_task(Worker* w, int priority)" in pruned
    assert "int main(int argc, char** argv)" in pruned


def test_universal_ast_pruner_dispatch():
    go_snippet = 'package main\nfunc Run() int { return 42 }\n'
    pruned_go, stats_go = UniversalASTPruner.prune_code(go_snippet, language="go")
    assert stats_go["language"] == "go"
    assert "func Run() int" in pruned_go

    py_snippet = 'def run() -> int:\n    return 42\n'
    pruned_py, stats_py = UniversalASTPruner.prune_code(py_snippet, language="python")
    assert stats_py["language"] == "python"
    assert "def run() -> int:" in pruned_py

    assert UniversalASTPruner.detect_language("main.go") == "go"
    assert UniversalASTPruner.detect_language("script.py") == "python"
    assert UniversalASTPruner.detect_language("core.c") == "c"
    assert UniversalASTPruner.detect_language("header.h") == "c"
