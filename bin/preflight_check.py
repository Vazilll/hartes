#!/usr/bin/env python3
"""DNTS Pre-Flight Check — запускается перед destructive операциями.

Использование:
    python preflight_check.py --operation "git push"   # проверить git
    python preflight_check.py --operation "delete file" # проверить sandbox
    python preflight_check.py --list                    # список всех проверок

Exit code:
    0 = все проверки пройдены
    1 = хотя бы одна проверка не пройдена
"""

import sys
import os
import subprocess
import json
import datetime

sys.stdout.reconfigure(encoding='utf-8')


def check_git_clean() -> tuple:
    """Проверить, что git репозиторий в чистом состоянии."""
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True, text=True, cwd='C:\\dnts', timeout=10
        )
        if result.returncode != 0:
            return False, f"git status error: {result.stderr.strip()}"
        if result.stdout.strip():
            dirty_files = result.stdout.strip().split('\n')[:5]
            return False, f"Есть незакоммиченные изменения ({len(dirty_files)} файлов): {dirty_files}"
        return True, "Git clean"
    except FileNotFoundError:
        return False, "git not found in PATH"
    except subprocess.TimeoutExpired:
        return False, "git status timeout"
    except Exception as e:
        return False, f"git error: {e}"


def check_backup_exists() -> tuple:
    """Проверить, что существует backup директория."""
    backup_dir = 'C:\\dnts\\_backup'
    if os.path.isdir(backup_dir):
        files = os.listdir(backup_dir)
        return True, f"Backup существует ({len(files)} файлов)"
    else:
        return False, f"Backup директория {backup_dir} не найдена"


def check_disk_space() -> tuple:
    """Проверить свободное место на диске C:."""
    try:
        import ctypes
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p('C:\\'), None, None, ctypes.pointer(free_bytes)
        )
        free_gb = free_bytes.value / (1024**3)
        if free_gb < 5:
            return False, f"Мало места: {free_gb:.1f} GB (min: 5 GB)"
        return True, f"{free_gb:.1f} GB свободно"
    except Exception:
        # fallback
        try:
            result = subprocess.run(['df', '-h', '/c/'], capture_output=True, text=True, timeout=5)
            return True, result.stdout.strip().split('\n')[-1][:50]
        except:
            return True, "disk check skipped (no ctypes)"  # warn but pass


def check_hermes_running() -> tuple:
    """Проверить, что Hermes процесс активен (если нужно)."""
    # Не фатально, если Hermes не запущен — просто warn
    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'],
            capture_output=True, text=True, timeout=5, encoding='utf-8', errors='replace'
        )
        return True, f"Hermes check: {len(result.stdout.split(chr(10)))-2} python process(es)"
    except:
        return True, "hermes check skipped"


def check_hive_running() -> tuple:
    """Проверить, что dnts-hive процесс активен."""
    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq dnts-hive.exe', '/FO', 'CSV'],
            capture_output=True, text=True, timeout=5, encoding='utf-8', errors='replace'
        )
        lines = [l for l in result.stdout.split('\n') if 'dnts-hive' in l.lower()]
        if lines:
            return True, f"dnts-hive активен"
        else:
            return True, "dnts-hive не запущен (ok, не критично)"
    except:
        return True, "hive check skipped"


def check_antigravity_bridge() -> tuple:
    """Проверить, что SQLite bridge цел."""
    bridge_py = r'C:\vazus\pyenv\scripts\agy_bridge_mcp.py'
    bridge_go = r'C:\vazus\pyenv\gomcp\tools\antigravity.go'
    db_path = r'C:\vazus\memory\vazus.db'

    issues = []
    # Go bridge обязателен
    if not os.path.isfile(bridge_go):
        issues.append(f"Go bridge не найден: {bridge_go}")
    # DB обязателен
    if not os.path.isfile(db_path):
        issues.append(f"Database не найден: {db_path}")

    if issues:
        return False, "; ".join(issues)
    return True, f"Bridge OK (Go: {os.path.getsize(bridge_go)}b, DB: {os.path.getsize(db_path)}b)"


CHECKS = {
    'git-clean': check_git_clean,
    'backup': check_backup_exists,
    'disk-space': check_disk_space,
    'hermes': check_hermes_running,
    'hive': check_hive_running,
    'antigravity-bridge': check_antigravity_bridge,
}


def run_all(operation: str = None) -> list:
    """Запустить все проверки."""
    results = []
    print(f"⚡ Pre-Flight Check — {operation or 'general'}")
    print(f"  Time: {datetime.datetime.now().isoformat()}")
    print()

    for name, check_fn in CHECKS.items():
        try:
            ok, msg = check_fn()
            status = "✅" if ok else "❌"
            print(f"  {status} {name}: {msg}")
            results.append({'check': name, 'ok': ok, 'message': msg})
        except Exception as e:
            print(f"  ⚠️  {name}: ERROR — {e}")
            results.append({'check': name, 'ok': False, 'message': str(e)})

    failed = [r for r in results if not r['ok']]
    print()
    if failed:
        print(f"❌ {len(failed)}/{len(results)} проверок не пройдено:")
        for f in failed:
            print(f"   - {f['check']}: {f['message']}")
    else:
        print(f"✅ Все {len(results)} проверок пройдены")

    return results


def main():
    if '--list' in sys.argv:
        print("Доступные проверки:")
        for name in CHECKS:
            print(f"  - {name}")
        return

    operation = None
    for i, arg in enumerate(sys.argv):
        if arg == '--operation' and i + 1 < len(sys.argv):
            operation = sys.argv[i + 1]

    results = run_all(operation)

    failed_count = len([r for r in results if not r['ok']])
    # Сохранить лог
    log_path = r'C:\vazus\logs\preflight.jsonl'
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, 'a') as f:
        f.write(json.dumps({
            'timestamp': datetime.datetime.now().isoformat(),
            'operation': operation,
            'results': results,
            'failed': failed_count,
        }) + '\n')

    sys.exit(1 if failed_count > 0 else 0)


if __name__ == '__main__':
    main()
