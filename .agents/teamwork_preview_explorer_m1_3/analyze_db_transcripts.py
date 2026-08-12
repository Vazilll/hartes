import sqlite3, json, sys, re
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r'C:\vazus\vazus.db')
cur = conn.cursor()

# 1. Node types count
cur.execute("SELECT node_type, count(*) FROM kg_nodes GROUP BY node_type")
print("=== Node Types in kg_nodes ===")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

# 2. Inspect nodes with text/descriptions
cur.execute("SELECT id, name, domain, node_type, description, properties FROM kg_nodes")
rows = cur.fetchall()

print(f"\nTotal nodes: {len(rows)}")

media_scenes = []
transcripts = []
known_hallucinations = [
    r'субтитры', r'редактор', r'перевод', r'продолжение следует', r'спасибо за просмотр',
    r'подписывайтесь', r'ставите лайк', r'ставьте лайки', r'музыка', r'гитара',
    r'thank you for watching', r'subscribe', r'you', r'bye', r'applause', r'cheering',
    r'аудиоклип', r'создано в программе', r'amara.org', r'www\.', r'http'
]

garbage_matches = Counter()
repetitive_nodes = []
short_hallucinations = []
empty_descriptions = 0
all_texts = []

for r in rows:
    nid, name, domain, ntype, desc, props = r
    desc_str = desc if desc else ""
    
    # check properties JSON if present
    prop_data = {}
    if props:
        try:
            prop_data = json.loads(props)
        except:
            pass
    
    text_content = desc_str + " " + json.dumps(prop_data, ensure_ascii=False)
    all_texts.append((nid, name, ntype, desc_str, prop_data))

    if not desc_str.strip():
        empty_descriptions += 1

    # Check for hallucination patterns
    for pat in known_hallucinations:
        if re.search(pat, text_content, re.IGNORECASE):
            garbage_matches[pat] += 1

    # Check for character/word repetition (e.g. "да да да да", "так так так", repeated lines)
    words = re.findall(r'\w+', text_content.lower())
    if len(words) >= 4:
        for i in range(len(words)-3):
            if words[i] == words[i+1] == words[i+2] == words[i+3]:
                repetitive_nodes.append((nid, name, words[i], desc_str[:100]))
                break

print(f"\nEmpty descriptions: {empty_descriptions}")
print("\n=== Garbage Pattern Match Frequencies in Existing DB ===")
for pat, cnt in garbage_matches.most_common():
    print(f"  Pattern '{pat}': {cnt} nodes matched")

print(f"\nRepetitive phrase loops detected in {len(repetitive_nodes)} nodes:")
for item in repetitive_nodes[:10]:
    print(f"  ID: {item[0]} | Word repeated: '{item[2]}' | Preview: {item[3]}")

# Inspect a sample of actual transcript / node content
print("\n=== Sample Node Content (First 10) ===")
for item in all_texts[:10]:
    print(f"[{item[2]}] {item[0]} - {item[1]}")
    print(f"   Desc: {item[3][:150]}...")
    if item[4]:
        print(f"   Props: {list(item[4].keys())}")

conn.close()
