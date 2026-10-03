"""
MIREA Dashboard Launcher
Запускает оба дашборда в режиме Edge App (без браузерной строки, как PWA)
Запуск: python C:\vazus\scripts\launch_dashboard.py
Или двойной клик по ярлыку на рабочем столе
"""
import subprocess, sys, time, os

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(EDGE):
    EDGE = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

DASHBOARDS = [
    ("Академический реестр", "file:///C:/vazus/services/academic_dashboard/index.html"),
    ("Справочник преподавателей", "file:///C:/vazus/services/teachers_directory/index.html"),
]

for name, url in DASHBOARDS:
    print(f"Открываю: {name}")
    subprocess.Popen([EDGE, f"--app={url}", "--window-size=1280,900"])
    time.sleep(0.5)

print("Готово! Оба дашборда открыты.")
