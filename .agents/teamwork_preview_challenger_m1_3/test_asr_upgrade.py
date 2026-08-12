import sys
import os
import sqlite3
import json

# Ensure path to vazus_core is in sys.path
sys.path.insert(0, r"C:\vazus")
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from vazus_core.multimodal_knowledge import (
    is_garbage_transcript,
    normalize_russian_text,
    transcribe_and_chunk_media,
    index_scenes_to_supergraph,
    hybrid_semantic_chunking,
    generate_thumbnail,
)

print("=== CHALLENGER 3 EMPIRICAL TEST HARNESS ===")

# --- Task 1: Challenge is_garbage_transcript ---
print("\n--- TASK 1: Testing is_garbage_transcript ---")

subtitle_credits = [
    ("Субтитры сделал Dima", True),
    ("Редактор субтитров", True),
    ("Перевод на русский", True),
    ("Субтитры", True),
    ("Редактор субтитров Анна", True),
    ("Перевод: Alex", True),
    ("Озвучка студии", True),
    ("Спасибо за просмотр", True),
    ("Продолжение следует", True),
    ("Подпишитесь на канал", True),
    ("Ставьте лайк", True),
    ("До новых встреч!", True),
    ("Благодарю за внимание.", True),
    ("Копирайт 2026", True),
    ("Субтитры добавил amara.org", True),
    ("Сообщество VK", True),
    ("Перевод от Yandex", True),
]

ngram_loops = [
    ("да да да да", True),
    ("так так так так", True),
    ("посмотрим на это посмотрим на это посмотрим на это", True),
    ("это очень важный шаг это очень важный шаг это очень важный шаг", True),
    ("сегодня мы обсудим теорию относительности сегодня мы обсудим теорию относительности сегодня мы обсудим теорию относительности", True),
]

valid_conversations = [
    ("Привет, сегодня мы рассмотрим физику движения и инерцию.", False),
    ("В этом видео уроке объясняется правило Ньютона.", False),
    ("Здравствуйте! Добро пожаловать на лекцию по машинному обучению.", False),
]

borderline_conversations = [
    ("В этом докладе автор делает перевод древнего текста.", False),
    ("Качественные субтитры помогают понимать видео лучше.", False),
    ("Актер дубляжа выполнил отличный перевод диалогов.", False),
]

all_t1_tests = [
    ("Subtitle credits", subtitle_credits),
    ("N-gram loops", ngram_loops),
    ("Valid conversations", valid_conversations),
    ("Borderline conversations (False Positive Stress-Test)", borderline_conversations),
]

task1_failures = []

for category, test_set in all_t1_tests:
    print(f"\nCategory: {category}")
    for text, expected in test_set:
        res = is_garbage_transcript(text)
        passed = (res == expected)
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] '{text}' -> expected {expected}, got {res}")
        if not passed:
            task1_failures.append((category, text, expected, res))

# --- Task 2: Test normalize_russian_text ---
print("\n--- TASK 2: Testing normalize_russian_text ---")

t2_cases = [
    ("закон сохранения (инерции) работает", "закон сохранения (инерции) работает"),
    ("Привет [МУЗЫКА] всем", "Привет всем"),
    ("Текст [АПЛОДИСМЕНТЫ] продолжение", "Текст продолжение"),
    ("город (Пятигорск) расположен на Кавказе", "город (Пятигорск) расположен на Кавказе"),
    ("Привет (смех) друзья [АПЛОДИСМЕНТЫ]", "Привет друзья"),
    ("Речь [МУЗЫКА] (инерции) и (смех) результат", "Речь (инерции) и результат"),
    ("Текст с неразрывными пробелами", "Текст с неразрывными пробелами"),
    ("Текст\xa0с\xa0неразрывными\u200bпробелами", "Текст с неразрывными пробелами"),
]

task2_failures = []

for text, expected in t2_cases:
    res = normalize_russian_text(text)
    passed = (res == expected)
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] In:  '{text}'")
    print(f"         Out: '{res}'")
    if not passed:
        print(f"         Exp: '{expected}'")
        task2_failures.append((text, expected, res))

# --- Task 3: Verify transcribe_and_chunk_media & index_scenes_to_supergraph ---
print("\n--- TASK 3: Testing transcribe_and_chunk_media & index_scenes_to_supergraph ---")

sample_file = r"C:\vazus\knowledge\telegram_courses\Курс _Покоритель Наташек 6_0_\media_174.oga"
print(f"Checking sample file: {sample_file} (Exists: {os.path.exists(sample_file)})")

task3_failures = []

# Mock segments test
mock_segments = [
    {"start": 0.0, "end": 65.0, "text": "Привет всем! Сегодня мы поговорим про закон инерции. [МУЗЫКА]"},
    {"start": 66.0, "end": 130.0, "text": "Инерция (в физике) определяет сопротивление изменению движения. (смех)"},
    {"start": 131.0, "end": 195.0, "text": "Рассмотрим (Пятигорск) пример с катящимся шаром."},
]

test_thumb_dir = r"C:\vazus\.agents\teamwork_preview_challenger_m1_3\test_thumbnails"
os.makedirs(test_thumb_dir, exist_ok=True)

print("\nTesting hybrid_semantic_chunking with mock segments...")
scenes = hybrid_semantic_chunking(mock_segments, source_file="test_audio.mp3", output_thumbnail_dir=test_thumb_dir)
print(f"Generated {len(scenes)} scenes.")

full_combined_transcript = " ".join([sc['transcript'] for sc in scenes])

for sc in scenes:
    print(f"  Scene ID: {sc['scene_id']}")
    print(f"    Time: {sc['start_sec']}s -> {sc['end_sec']}s")
    print(f"    Transcript: {sc['transcript']}")
    print(f"    Thumbnail: {sc['thumbnail_path']} (Exists: {os.path.exists(sc['thumbnail_path'])})")
    
    if not os.path.exists(sc['thumbnail_path']):
        task3_failures.append(f"Mock thumbnail missing at {sc['thumbnail_path']}")
        
    if "[МУЗЫКА]" in sc['transcript'] or "(смех)" in sc['transcript']:
        task3_failures.append(f"Mock noise tag not filtered: {sc['transcript']}")

if "(в физике)" not in full_combined_transcript or "(Пятигорск)" not in full_combined_transcript:
    task3_failures.append(f"Mock spoken parentheses erroneously stripped from combined transcript: {full_combined_transcript}")

print("\nTesting index_scenes_to_supergraph with generated mock scenes...")
test_db_path = r"C:\vazus\.agents\teamwork_preview_challenger_m1_3\test_vazus.db"
if os.path.exists(test_db_path):
    os.remove(test_db_path)

indexed_count = index_scenes_to_supergraph(scenes, db_path=test_db_path)
print(f"Indexed count returned: {indexed_count}")

if indexed_count != len(scenes):
    task3_failures.append(f"Indexed count mismatch: expected {len(scenes)}, got {indexed_count}")

if not os.path.exists(test_db_path):
    task3_failures.append(f"Database file not created at {test_db_path}")
else:
    conn = sqlite3.connect(test_db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, name, domain, node_type, tags, properties, embedding_json FROM kg_nodes")
    nodes = cur.fetchall()
    print(f"Found {len(nodes)} kg_nodes in DB.")
    for n in nodes:
        node_id, name, domain, node_type, tags, props_json, emb_json = n
        emb = json.loads(emb_json)
        print(f"  Node [{node_id}] type={node_type}, domain={domain}, emb_dim={len(emb)}")
        if len(emb) != 768:
            task3_failures.append(f"Embedding dimension is {len(emb)}, expected 768")

    cur.execute("SELECT source_id, target_id, relation FROM kg_edges")
    edges = cur.fetchall()
    print(f"Found {len(edges)} kg_edges in DB.")
    for e in edges:
        print(f"  Edge {e[0]} --({e[2]})--> {e[1]}")

    conn.close()

# Live end-to-end transcription test on actual media file
if os.path.exists(sample_file):
    print(f"\nTesting live transcribe_and_chunk_media on real audio file: {sample_file}...")
    try:
        live_scenes = transcribe_and_chunk_media(sample_file, output_thumbnail_dir=test_thumb_dir)
        print(f"Live transcription produced {len(live_scenes)} scenes.")
        for sc in live_scenes:
            print(f"  - [{sc['scene_id']}] ({sc['start_sec']}s -> {sc['end_sec']}s): {sc['transcript'][:80]}...")
            print(f"    Thumbnail: {sc['thumbnail_path']} (Exists: {os.path.exists(sc['thumbnail_path'])})")
            if not os.path.exists(sc['thumbnail_path']):
                task3_failures.append(f"Live scene thumbnail missing at {sc['thumbnail_path']}")
            if not sc['transcript']:
                task3_failures.append(f"Live scene [{sc['scene_id']}] has empty transcript")
        
        # Test supergraph indexing on live scenes
        live_db_path = r"C:\vazus\.agents\teamwork_preview_challenger_m1_3\test_live_vazus.db"
        if os.path.exists(live_db_path):
            os.remove(live_db_path)
        live_indexed = index_scenes_to_supergraph(live_scenes, db_path=live_db_path)
        print(f"Indexed {live_indexed} live scenes into SuperGraph DB.")
        if live_indexed != len(live_scenes):
            task3_failures.append(f"Live indexing mismatch: expected {len(live_scenes)}, got {live_indexed}")
    except Exception as e:
        print(f"Live transcription exception: {e}")
        task3_failures.append(f"Live transcription failed: {e}")

print("\n=== SUMMARY OF EMPIRICAL TEST RESULTS ===")
print(f"Task 1 Failures: {len(task1_failures)}")
for f in task1_failures:
    print(f"  - {f}")

print(f"Task 2 Failures: {len(task2_failures)}")
for f in task2_failures:
    print(f"  - {f}")

print(f"Task 3 Failures: {len(task3_failures)}")
for f in task3_failures:
    print(f"  - {f}")

total_failures = len(task1_failures) + len(task2_failures) + len(task3_failures)
verdict = "PASS" if total_failures == 0 else "FAIL"
print(f"\nOVERALL VERDICT: {verdict}")
