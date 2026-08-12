import sqlite3

def main():
    conn = sqlite3.connect('C:/vazus/vazus.db')
    cursor = conn.cursor()
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    print("Tables in vazus.db:")
    for t in tables:
        print(" -", t[0])
        cols = cursor.execute(f"PRAGMA table_info({t[0]});").fetchall()
        for col in cols:
            print(f"     {col[1]} ({col[2]})")
            
if __name__ == '__main__':
    main()
