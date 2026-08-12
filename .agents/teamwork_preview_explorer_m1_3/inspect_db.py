import sqlite3, json, sys

sys.stdout.reconfigure(encoding='utf-8')

for db_path in [r'C:\vazus\vazus.db', r'C:\vazus\memory\dnts.db']:
    print('==================================================')
    print('DB:', db_path)
    print('==================================================')
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cur.fetchall()]
        print('Tables:', tables)
        for t in tables:
            cur.execute(f"SELECT count(*) FROM [{t}]")
            cnt = cur.fetchone()[0]
            print(f'  Table [{t}]: {cnt} rows')
            # inspect columns
            cur.execute(f"PRAGMA table_info([{t}])")
            cols = [col[1] for col in cur.fetchall()]
            print(f'    Columns: {cols}')
        conn.close()
    except Exception as e:
        print('Error:', e)
