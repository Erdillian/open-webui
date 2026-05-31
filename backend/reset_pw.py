import sqlite3
import bcrypt

new_password = "admin"
hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
print('New hash:', hashed)

conn = sqlite3.connect(r'D:\Assistant\open-webui-fork\backend\data\webui.db')
cursor = conn.cursor()
cursor.execute(
    "UPDATE auth SET password = ? WHERE email = ?",
    (hashed, 'admin@local.dev')
)
conn.commit()
print('Rows updated:', cursor.rowcount)
conn.close()
