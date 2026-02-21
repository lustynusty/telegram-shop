# migrate_add_hidden.py
import sqlite3

conn = sqlite3.connect("shop.db")
cur = conn.cursor()
cur.execute("PRAGMA table_info(categories)")
cols = [c[1] for c in cur.fetchall()]
if 'is_hidden' not in cols:
    cur.execute("ALTER TABLE categories ADD COLUMN is_hidden INTEGER DEFAULT 0")
    print("Колонка is_hidden добавлена")
else:
    print("Уже есть")
conn.commit()
conn.close()