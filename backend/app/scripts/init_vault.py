import os
import sqlite3
import json
from datetime import datetime
import shutil

VAULT_DIR = r'E:\OpenClaw-Base\RetirementVault'
os.makedirs(VAULT_DIR, exist_ok=True)

db_path = os.path.join(VAULT_DIR, 'index.sqlite')
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS archived_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_path TEXT NOT NULL,
        vault_filename TEXT NOT NULL,
        archived_at TEXT NOT NULL,
        deletion_condition TEXT NOT NULL
    )
''')
conn.commit()

files_to_archive = [
    (r'E:\OpenClaw-Base\.openclaw\core\dynamic-platform-binding.js', '最终调试结束且M07功能全覆盖后可删除'),
    (r'E:\OpenClaw-Base\.openclaw\core\universal-evolution-framework.js', '最终调试结束且M08学习复盘系统验证无丢失后可删除'),
    (r'E:\OpenClaw-Base\.openclaw\core\self-hardening.js', '最终调试结束且M03系统接管完成后可删除'),
    (r'E:\OpenClaw-Base\.openclaw\core\token-optimizer.js', '最终调试结束且M09完成迁移后可删除')
]

for orig, cond in files_to_archive:
    if os.path.exists(orig):
        basename = os.path.basename(orig)
        vault_name = f'{datetime.now().strftime("%Y%m%d%H%M%S")}_{basename}'
        vault_path = os.path.join(VAULT_DIR, vault_name)
        shutil.copy2(orig, vault_path)
        c.execute('INSERT INTO archived_files (original_path, vault_filename, archived_at, deletion_condition) VALUES (?, ?, ?, ?)',
                  (orig, vault_name, datetime.now().isoformat(), cond))
        print(f'Archived {orig} -> {vault_name}')
    else:
        print(f'File not found: {orig}')

conn.commit()
conn.close()
print('RetirementVault initialized successfully.')
