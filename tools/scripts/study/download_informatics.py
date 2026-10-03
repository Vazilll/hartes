import os
import sys
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding='utf-8')

target_dir = r"C:\Users\Vaz\Documents\mirea_study_os\01_Disciplines\14_Informatics"
os.makedirs(target_dir, exist_ok=True)

cookie = "MoodleSession=a0tf0vrhkh6lebuan0gl9oos1q"

files = [
    ("Практическая_работа_1.pdf", "https://online-edu.mirea.ru/pluginfile.php/2244202/mod_assign/introattachment/0/%D0%9F%D1%80%D0%B0%D0%BA%D1%82%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B0%D1%8F%20%D1%80%D0%B0%D0%B1%D0%BE%D1%82%D0%B0%201.pdf?forcedownload=1"),
    ("Практическая_работа_5.pdf", "https://online-edu.mirea.ru/pluginfile.php/2244202/mod_assign/introattachment/0/%D0%9F%D1%80%D0%B0%D0%BA%D1%82%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B0%D1%8F%20%D1%80%D0%B0%D0%B1%D0%BE%D1%82%D0%B0%205.pdf?forcedownload=1"),
    ("Практическая_работа_6.pdf", "https://online-edu.mirea.ru/pluginfile.php/2244202/mod_assign/introattachment/0/%D0%9F%D1%80%D0%B0%D0%BA%D1%82%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%B0%D1%8F%20%D1%80%D0%B0%D0%B1%D0%BE%D1%82%D0%B0%206.pdf?forcedownload=1"),
    ("Титульный_лист.docx", "https://online-edu.mirea.ru/pluginfile.php/2244202/mod_assign/introattachment/0/%D0%A2%D0%B8%D1%82%D1%83%D0%BB%D1%8C%D0%BD%D1%8B%D0%B8%CC%86_%D0%BB%D0%B8%D1%81%D1%82_%D0%B4%D0%BB%D1%8F_%D0%BE%D1%82%D1%87%D0%B5%D1%82%D0%BE%D0%B2_%D0%BF%D0%BE_%D0%BF%D1%80%D0%B0%D0%BA%D1%82%D0%B8%D0%BA%D0%B5.docx?forcedownload=1")
]

opener = urllib.request.build_opener()
opener.addheaders = [
    ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
    ('Cookie', cookie)
]
urllib.request.install_opener(opener)

for name, url in files:
    dest = os.path.join(target_dir, name)
    try:
        print(f"Downloading {name}...")
        urllib.request.urlretrieve(url, dest)
        size = os.path.getsize(dest)
        print(f"Saved {name}, size: {size} bytes")
    except Exception as e:
        print(f"Error downloading {name}: {e}")
