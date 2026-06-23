import sqlite3
conn = sqlite3.connect(r'D:\Assistant\open-webui-fork\backend\data\webui.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM auth WHERE email='admin@local.dev'")
row = cursor.fetchone()
print('Values:', row)
conn.close()
