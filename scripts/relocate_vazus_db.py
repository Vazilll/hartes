import sys
import os
import shutil

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

print("=" * 70)
print("📦 СИНХРОНИЗАЦИЯ И УПОРЯДОЧИВАНИЕ ПУТЕЙ DB И ОКРУЖЕНИЯ VAZUS")
print("=" * 70)

target_dir = r"C:\vazus\services\memory"
os.makedirs(target_dir, exist_ok=True)

target_db = os.path.join(target_dir, "vazus.db")
root_db = r"C:\vazus\vazus.db"
mem_db = r"C:\vazus\memory\vazus.db"

if os.path.exists(root_db):
    print(f"1. Копирование основного vazus.db из {root_db} -> {target_db}...")
    shutil.copy2(root_db, target_db)
    print("   ✅ vazus.db успешно помещён в C:\\vazus\\services\\memory\\vazus.db")

if os.path.exists(target_db):
    os.makedirs(r"C:\vazus\memory", exist_ok=True)
    shutil.copy2(target_db, mem_db)
    print("   ✅ vazus.db засинхронен в C:\\vazus\\memory\\vazus.db")

print("\n2. Статус папок окружений:")
print("   • C:\\vazus\\.venv — Единственное ЕДИНОЕ виртуальное окружение Python.")
print("   • C:\\vazus\\bin   — Набор C/C++ компиляторов и утилит (w64devkit, GCC, Rizin, Radare2). НЕ является python venv.")
print("   • C:\\vazus\\pyenv — Служебная папка конфигурации pyenv-win.")
