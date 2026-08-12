import re
from collections import Counter

def normalize_russian_text(text: str) -> str:
    if not text:
        return ""
    # 1. Remove hallucinated bracket tags
    text = re.sub(r'\[.*?\]|\(.*?\)|<.*?>', ' ', text)
    # 2. Replace 'Ё'/'ё' with 'Е'/'е' for search uniformity
    text = text.replace('Ё', 'Е').replace('ё', 'е')
    # 3. Clean zero-width spaces and unicode controls
    text = re.sub(r'[\u200b\ufeff\u200e\u200f]', '', text)
    # 4. Standardize quotes and dashes
    text = re.sub(r'[«»“”]', '"', text)
    text = re.sub(r'[—–]', '-', text)
    # 5. Fix repetitive punctuation (e.g. ..... -> .)
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'!{2,}', '!', text)
    text = re.sub(r'\?{2,}', '?', text)
    # 6. Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_garbage_transcript(text: str, avg_logprob: float = 0.0, no_speech_prob: float = 0.0, compression_ratio: float = 1.0) -> bool:
    if not text or len(text.strip()) == 0:
        return True
    
    clean_text = normalize_russian_text(text)
    letters_only = re.sub(r'[^a-zA-Zа-яА-Я0-9]', '', clean_text)
    if len(letters_only) < 3:
        return True
    
    # Known Whisper hallucination patterns
    hallucination_patterns = [
        r'спасибо за просмотр',
        r'субтитры',
        r'подписывайтесь на канал',
        r'до скорой встречи',
        r'продолжение следует',
        r'редактор субтитров',
        r'переводчик',
        r'ставьте лайк',
        r'сообщество',
        r'бай бай',
        r'thank you for watching',
        r'subscribe',
        r'amara\.org'
    ]
    low_text = clean_text.lower()
    for pat in hallucination_patterns:
        if re.search(pat, low_text):
            return True
            
    # Repetitive loop detection
    words = low_text.split()
    if len(words) >= 4:
        counts = Counter(words)
        most_common_word, max_c = counts.most_common(1)[0]
        if max_c / len(words) > 0.5 and len(words) >= 6:
            return True
            
        bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
        bi_counts = Counter(bigrams)
        most_common_bi, bi_c = bi_counts.most_common(1)[0]
        if bi_c >= 3 and bi_c / len(bigrams) >= 0.4:
            return True

    # Whisper confidence scores
    if no_speech_prob > 0.6:
        return True
    if avg_logprob < -1.2:
        return True
    if compression_ratio > 2.4:
        return True

    return False

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    samples = [
        ("[Музыка] Спасибо за просмотр! Подписывайтесь на канал! [Смех]", 0.0, 0.0, 1.0),
        ("Привет всем, сегодня мы обсудим архитектуру vazus SuperGraph OS.", -0.2, 0.05, 1.2),
        ("Да да да да да да да да да да", -0.5, 0.1, 1.1),
        ("....", -1.5, 0.8, 3.0),
        ("Ёжик вышел из тумана: «Привет, мир!» — сказал он.", -0.1, 0.01, 1.0)
    ]

    for s, logprob, nsp, cr in samples:
        norm = normalize_russian_text(s)
        garb = is_garbage_transcript(s, logprob, nsp, cr)
        print(f"Original:   {s}")
        print(f"Normalized: {norm}")
        print(f"Is Garbage: {garb}\n")
