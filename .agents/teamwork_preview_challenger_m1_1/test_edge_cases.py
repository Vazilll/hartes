import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, r"C:\vazus")
from vazus_core.multimodal_knowledge import normalize_russian_text, is_garbage_transcript

def test_garbage_edge_cases():
    print("=== Testing is_garbage_transcript Edge Cases ===")
    cases = [
        "Субтитры сделал Илья",
        "Субтитры сделала Мария",
        "Субтитры от Vlad",
        "Редактор субтитров: Иван",
        "Перевод: Анна",
        "Сообщество VK / group",
        "Подпишитесь на наш канал и ставьте лайки",
        "Продолжение следует...",
        "Продолжение следует!",
        "Продолжение следует",
        "Копирайт yandex 2026",
        "Amara.org subtitles",
        "Спасибо за внимание!",
        "Благодарю за внимание",
        "да да да",
        "да да да да",
        "нет нет нет нет",
        "субтитры",
        "СУБТИТРЫ",
        "Субтитры.",
    ]

    for c in cases:
        res = is_garbage_transcript(c)
        print(f"Text: '{c}' -> Garbage: {res}")

def test_normalization_edge_cases():
    print("\n=== Testing normalize_russian_text Edge Cases ===")
    cases = [
        "Привет [МУЗЫКА], как дела?",
        "Слово (пояснение), продолжение.",
        "Число 100 (сто) и (двести) 200.",
        "[ ] [ ] Текст [ ]",
        "( ) ( ) Текст ( )",
        "  Много \t  пробелов \n  и   переносов   ",
        "Текст с \xa0 неразрывным и \u200b скрытым",
    ]

    for c in cases:
        res = normalize_russian_text(c)
        print(f"Original:  '{c}'\nNormalized:'{res}'\n")

if __name__ == "__main__":
    test_garbage_edge_cases()
    test_normalization_edge_cases()
