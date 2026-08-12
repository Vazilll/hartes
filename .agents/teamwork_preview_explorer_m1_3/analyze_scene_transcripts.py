import sqlite3, json, sys, re
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r'C:\vazus\vazus.db')
cur = conn.cursor()

cur.execute("SELECT id, name, properties FROM kg_nodes WHERE node_type='MediaScene'")
scenes = cur.fetchall()

print(f"Total MediaScene nodes: {len(scenes)}")

transcripts = []
empty_transcripts = 0
short_transcripts = 0
hallucination_candidates = []
filler_word_counter = Counter()

# Common Russian filler words & hesitation artifacts
fillers = ['э-э', 'ээ', 'эм', 'ну', 'как бы', 'типа', 'короче', 'в общем', 'значит', 'понимаешь', 'собственно']

for nid, name, props_str in scenes:
    props = json.loads(props_str) if props_str else {}
    t = props.get('transcript', '')
    if not t or not t.strip():
        empty_transcripts += 1
        continue
    
    t_clean = t.strip()
    if len(t_clean) < 15:
        short_transcripts += 1
        hallucination_candidates.append((nid, name, t_clean, 'Very short (<15 chars)'))

    # Check repetition in transcript
    words = re.findall(r'[а-яА-Яa-zA-Z0-9]+', t_clean.lower())
    if len(words) >= 4:
        for i in range(len(words)-3):
            if words[i] == words[i+1] == words[i+2] == words[i+3]:
                hallucination_candidates.append((nid, name, t_clean, f"4x Repetition of '{words[i]}'"))
                break

    # Count filler words
    for f in fillers:
        cnt = len(re.findall(r'\b' + re.escape(f) + r'\b', t_clean.lower()))
        if cnt > 0:
            filler_word_counter[f] += cnt

    # Check typical Whisper hallucination phrases (Russian & English subtitles/credits/looping)
    whisper_artifacts = [
        'субтитры', 'редактор', 'перевод', 'продолжение следует', 'спасибо за просмотр',
        'подписывайтесь', 'ставьте лайк', 'музыка', 'thank you for watching', 'subscribe',
        'amara.org', 'привод', 'продолжение', 'аудиоклип', 'не забудьте', 'лайк'
    ]
    for art in whisper_artifacts:
        if re.search(r'\b' + re.escape(art) + r'\b', t_clean, re.IGNORECASE):
            hallucination_candidates.append((nid, name, t_clean, f"Whisper artifact '{art}'"))

    transcripts.append((nid, name, t_clean))

print(f"Empty transcripts: {empty_transcripts}")
print(f"Short transcripts (<15 chars): {short_transcripts}")
print(f"\nDetected Hallucination & Garbage Candidates ({len(hallucination_candidates)}):")
for hc in hallucination_candidates[:20]:
    print(f"  [{hc[0]}] Reason: {hc[3]}")
    print(f"     Text: \"{hc[2]}\"")

print("\n=== Filler Word Frequencies in Existing Transcripts ===")
for f, cnt in filler_word_counter.most_common():
    print(f"  '{f}': {cnt} occurrences")

print("\n=== Sample Transcripts from Real Media Scenes (10 items) ===")
real_scenes = [item for item in transcripts if not item[0].startswith('test_') and not item[0].startswith('scene_synth_')]
print(f"Total non-synthetic media scenes: {len(real_scenes)}")
for rs in real_scenes[:15]:
    print(f"[{rs[0]}] {rs[1]}")
    print(f"   \"{rs[2]}\"")

conn.close()
