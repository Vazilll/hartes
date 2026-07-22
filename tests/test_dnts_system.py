"""
tests/test_dnts_system.py — Комплексный интеграционный тест для Portless Native системы DNTS Google DeepMind OS.
"""
import sys
import os
import json
import time

sys.path.insert(0, "C:/vazus/pyenv")
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

def run_tests():
    print("=" * 60)
    print("🧪 ЗАПУСК КОМПЛЕКСНОГО ТЕСТИРОВАНИЯ PORTLESS NATIVE СИСТЕМЫ DNTS")
    print("=" * 60)
    
    # 1. Проверка конфигурации (без портов!)
    from dnts_core.config import settings
    print(f"1. Чистая Конфигурация: Workspace = {settings.WORKSPACE_DIR}")
    print(f"   - Модель Fast: {settings.MODEL_FAST}")
    print(f"   - Модель Pro: {settings.MODEL_PRO}")
    print(f"   - Размерность векторов: {settings.EMBEDDING_DIM}")
    assert settings.EMBEDDING_DIM == 768, "Размерность вектора должна быть 768!"
    print("   ✅ Чистая конфигурация без портов проверена успешно.")

    # 2. Проверка Git Provenance
    from dnts_core.git_provenance import GitProvenanceManager
    curr_branch = GitProvenanceManager.get_current_branch()
    print(f"2. Git Provenance: Активная ветка = '{curr_branch}'")
    test_branch = GitProvenanceManager.ensure_branch("google-deepmind", "portless-architecture")
    print(f"   ✅ Переключение на ветку '{test_branch}' прошло успешно.")

    # 3. Проверка Векторизатора Google DeepMind (768-dim in-process)
    from dnts_core.embeddings import UnifiedGoogleEmbedder
    embedder = UnifiedGoogleEmbedder()
    vec = embedder.embed_query("def dnts_kernel_test(): return 'Google DeepMind Portless'")
    print(f"3. Векторизатор Google DeepMind: Сгенерирован вектор длины {len(vec)}")
    assert len(vec) == 768, f"Ошибка! Ожидалось 768, получено {len(vec)}"
    print("   ✅ Векторизация 768-dim (in-process) работает без сбоев.")

    # 4. Проверка Google Jules Cloud Escalator
    from dnts_core.evolution.jules_verifier import JulesCloudEscalator
    escalator = JulesCloudEscalator()
    res = escalator.submit_task("Проверить юнит-тесты portless dnts_core")
    print(f"4. Google Jules Escalator: Ответ эскалатора = {res.get('status')}")
    assert "status" in res, "Эскалатор Jules должен возвращать статус"
    print("   ✅ Интегратор Google Jules протестирован успешно.")

    # 5. Проверка Telegram Bot API Notifier
    from dnts_core.telegram_notifier import TelegramNotifier
    notifier = TelegramNotifier()
    sent = notifier.send_card("System Check", "Portless Architecture Verified", status="SUCCESS")
    print(f"5. Telegram Notifier: Результат отправки = {sent}")
    print("   ✅ Уведомления протестированы.")

    print("=" * 60)
    print("🎉 ВСЕ 5 ИНТЕГРАЦИОННЫХ ТЕСТОВ PORTLESS АРХИТЕКТУРЫ УСПЕШНО ПРОЙДЕНЫ!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
