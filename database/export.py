import sqlite3
db = sqlite3.connect('discourse.db')
db.execute("DELETE FROM posts WHERE posted_at < '2026-01-01'")
db.commit()
rows = db.execute("SELECT platform, COUNT(*), MIN(posted_at), MAX(posted_at) FROM posts GROUP BY platform").fetchall()
for r in rows:
    print(r)
print("Old posts removed!")