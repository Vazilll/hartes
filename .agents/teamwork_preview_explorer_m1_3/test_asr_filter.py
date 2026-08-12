import sys, re

sys.stdout.reconfigure(encoding='utf-8')

def normalize_russian_text(text: str) -> str:
    if not text:
        return ''
    # Filter control characters
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Remove filler hesitation words: э-э, эээ, ммм, гм
    text = re.sub(r'\b(э-э|эээ|ээ|ммм|мм|эм|гм|а-а|ааа)\b', '', text, flags=re.IGNORECASE)
    # Collapse multi-spaces
    text = re.sub(r'\s+', ' ', text).strip()
    # Normalize punctuation spacing
    text = re.sub(r'\s+([.,!?:;])', r'\1', text)
    # Capitalize first letter of sentence
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text

def is_garbage_transcript(text: str) -> bool:
    if not text or len(text.strip()) < 3:
        return True
    
    t_lower = text.lower().strip()
    
    # 1. Known Whisper hallucination strings (subtitles, credits, URLs)
    hallucination_patterns = [
        r'субтитры', r'редактор', r'перевод', r'продолжение следует', r'спасибо за просмотр',
        r'подписывайтесь', r'ставите лайк', r'ставьте лайк', r'музыка', r'гитара',
        r'thank you for watching', r'subscribe', r'amara\.org', r'www\.', r'http',
        r'до скорой встречи', r'увидимся в следующем видео', r'до новых встреч',
        r'не забудьте подписаться', r'аудиоклип', r'создано в программе'
    ]
    for pat in hallucination_patterns:
        if re.search(pat, t_lower):
            return True

    # 2. Infinite repetition check (e.g. word repeated 4+ times)
    words = re.findall(r'[a-zA-Zа-яА-Я0-9]+', t_lower)
    if len(words) >= 4:
        for i in range(len(words) - 3):
            if words[i] == words[i+1] == words[i+2] == words[i+3]:
                return True

    # 3. High ratio of repeated words overall (e.g. 70%+ identical words)
    if len(words) >= 6:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.25:
            return True

    return False

test_samples = [
    'Газ газ газ газ',
    'Субтитры создал А.С.',
    'В этом уроке мы разбираем гибридную сегментацию и векторы 768D в SuperGraph OS.',
    'эээ ну как бы   мыслими на теме того , что мышцы Феналу ...',
    'Thank you for watching! Subscribe to the channel.',
    'Привет! Качал поделиться мыслими на теме того, когда фильм года мы с главными выпустили мышцы Феналу.'
]

print("=== TESTING RUSSIAN TEXT NORMALIZATION & GARBAGE FILTER ===")
for s in test_samples:
    is_garb = is_garbage_transcript(s)
    norm = normalize_russian_text(s)
    print(f"Original: \"{s}\"")
    print(f"  Garbage: {is_garb} | Normalized: \"{norm}\"\n")
