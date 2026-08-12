import sys
import sqlite3
import json

sys.stdout.reconfigure(encoding='utf-8')

def verify():
    for db_path in ['C:/vazus/services/memory/vazus.db', 'C:/vazus/vazus.db']:
        print(f"=== DB: {db_path} ===")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Check node counts
        tg_msgs = cur.execute("SELECT COUNT(*) FROM kg_nodes WHERE domain='telegram_discussion' AND node_type='TelegramMessage'").fetchone()[0]
        tg_channels = cur.execute("SELECT COUNT(*) FROM kg_nodes WHERE domain='telegram_discussion' AND node_type='TelegramChannel'").fetchone()[0]
        print(f"TelegramMessage nodes: {tg_msgs}")
        print(f"TelegramChannel nodes: {tg_channels}")
        
        # Check embedding dimensions
        row = cur.execute("SELECT embedding_json FROM kg_nodes WHERE domain='telegram_discussion' LIMIT 1").fetchone()
        if row and row[0]:
            emb = json.loads(row[0])
            print(f"Embedding sample dim: {len(emb)}, sample first 3: {emb[:3]}")
        
        # Check edge counts
        belongs_to = cur.execute("SELECT COUNT(*) FROM kg_edges WHERE relation='BELONGS_TO'").fetchone()[0]
        replies_to = cur.execute("SELECT COUNT(*) FROM kg_edges WHERE relation='REPLIES_TO'").fetchone()[0]
        ref_media = cur.execute("SELECT COUNT(*) FROM kg_edges WHERE relation='REFERENCES_MEDIA'").fetchone()[0]
        print(f"BELONGS_TO edges: {belongs_to}")
        print(f"REPLIES_TO edges: {replies_to}")
        print(f"REFERENCES_MEDIA edges: {ref_media}")
        
        # Verify sample properties
        msg_row = cur.execute("SELECT id, name, properties FROM kg_nodes WHERE domain='telegram_discussion' AND node_type='TelegramMessage' LIMIT 1").fetchone()
        props = json.loads(msg_row[2])
        print(f"Sample message node ID: {msg_row[0]}")
        print(f"Sample message node Name: {msg_row[1]}")
        print(f"Props keys: {list(props.keys())}")
        print(f"Sample msg text snippet: {props.get('text', '')[:60]}...")
        
        conn.close()

if __name__ == "__main__":
    verify()
