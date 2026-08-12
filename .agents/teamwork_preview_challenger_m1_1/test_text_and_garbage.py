import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Ensure vazus root is in sys.path
sys.path.insert(0, r"C:\vazus")

from vazus_core.multimodal_knowledge import normalize_russian_text, is_garbage_transcript

def test_normalization():
    print("=== Testing normalize_russian_text ===")
    test_cases = [
        ("[МУЗЫКА] Привет мир!", "Привет мир!"),
        ("[АПЛОДИСМЕНТЫ] (смех) Отличная речь", "Отличная речь"),
        ("Текст (шум) [МУЗЫКА] с \xa0 неразрывными \u200b пробелами", "Текст с пробелами"),
        ("[MUSIC] Hello (laughter) world", "Hello world"),
        ("", ""),
        (None, ""),
        ("[ ] ( )  \n\t ", ""),
        ("Привет, [МУЗЫКА] как дела?", "Привет, как дела?"),
        ("Раз (два) три", "Раз три"),
        ("Цена 100 (сто) рублей", "Цена 100 рублей"),
    ]
    
    passed = 0
    failed = 0
    for idx, (inp, expected) in enumerate(test_cases, 1):
        res = normalize_russian_text(inp)
        if res == expected:
            print(f"[PASS] Case {idx}: In='{inp}' -> Out='{res}'")
            passed += 1
        else:
            print(f"[FAIL] Case {idx}: In='{inp}' -> Expected='{expected}', Got='{res}'")
            failed += 1
    print(f"Normalization Results: {passed} passed, {failed} failed.\n")
    return passed, failed

def test_garbage_filtering():
    print("=== Testing is_garbage_transcript ===")
    test_cases = [
        # Should be identified as garbage (True)
        ("Субтитры", True),
        ("Субтитры сделал Илья", True),  # Challenging case
        ("Субтитры добавил...", True),
        ("субтитры сделала", True),
        ("Перевод", True),
        ("Редактор субтитров", True),
        ("Продолжение следует", True),
        ("Подпишитесь на канал", True),
        ("Ставьте лайки", True),
        ("Спасибо за просмотр!", True),
        ("До новых встреч", True),
        ("Копирайт yandex 2025", True),
        ("Благодарю за внимание", True),
        ("да да да да", True),
        ("так так так так так", True),
        ("привет мир привет мир привет мир привет мир", True),
        ("", True),
        (" ", True),
        ("a", True),

        # Should NOT be identified as garbage (False)
        ("Привет всем, сегодня мы обсудим графы знаний.", False),
        ("Курс по машинному обучению и нейронным сетям.", False),
        ("Да, это действительно так.", False),
        ("Вот три главных правила архитектуры.", False),
    ]

    passed = 0
    failed = 0
    for idx, (inp, expected_garbage) in enumerate(test_cases, 1):
        is_g = is_garbage_transcript(inp)
        if is_g == expected_garbage:
            print(f"[PASS] Case {idx}: Text='{inp}' -> is_garbage={is_g} (Expected {expected_garbage})")
            passed += 1
        else:
            print(f"[FAIL] Case {idx}: Text='{inp}' -> is_garbage={is_g} (Expected {expected_garbage})")
            failed += 1
    print(f"Garbage Filter Results: {passed} passed, {failed} failed.\n")
    return passed, failed

if __name__ == "__main__":
    p1, f1 = test_normalization()
    p2, f2 = test_garbage_filtering()
    print(f"TOTAL: {p1+p2} Passed, {f1+f2} Failed")
