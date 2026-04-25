#!/usr/bin/env python3
"""将 SQLite 数据迁移到 PostgreSQL"""
import sqlite3
import psycopg2
from datetime import datetime

# 连接 SQLite
sqlite_conn = sqlite3.connect('test.db')
sqlite_cursor = sqlite_conn.cursor()

# 连接 PostgreSQL
pg_conn = psycopg2.connect(
    host='localhost',
    port=5433,
    dbname='report_db',
    user='zhou'
)
pg_cursor = pg_conn.cursor()

print("=" * 60)
print("数据迁移：SQLite → PostgreSQL")
print("=" * 60)

# 0. 查询 SQLite 中 users 表数据
print("\n0. 检查 SQLite users 表...")
sqlite_cursor.execute('SELECT * FROM users')
rows = sqlite_cursor.fetchall()
print(f"   SQLite 有 {len(rows)} 条用户")
for r in rows:
    print(f"   id={r[0]}, username={r[1]}, email={r[3]}")
print("   (保留 PG 已有用户，不覆盖)")

# 1. 迁移 data_sources
print("\n1. 迁移 data_sources...")
sqlite_cursor.execute('SELECT * FROM data_sources')
rows = sqlite_cursor.fetchall()
print(f"   SQLite 有 {len(rows)} 条")
for row in rows:
    (id, name, type_, host, port, database, username, password_encrypted,
     is_active, created_by, created_at, updated_at) = row
    # created_by=3 在 PG 里不存在，用 admin (1) 兜底
    created_by_pg = created_by if created_by and created_by <= 2 else 1
    pg_cursor.execute("""
        INSERT INTO data_sources (id, name, type, host, port, database, username,
            password_encrypted, is_active, created_by, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            name=EXCLUDED.name, host=EXCLUDED.host, port=EXCLUDED.port,
            password_encrypted=EXCLUDED.password_encrypted
    """, (id, name, type_, host, port, database, username, password_encrypted,
          bool(is_active), created_by_pg, created_at, updated_at))
pg_conn.commit()
print("   ✓ done")

# 2. 迁移 query_history (user_id 不存在的用 admin 兜底)
print("\n2. 迁移 query_history...")
sqlite_cursor.execute('SELECT * FROM query_history')
rows = sqlite_cursor.fetchall()
print(f"   SQLite 有 {len(rows)} 条")
for row in rows:
    (id, user_id, data_source_id, query_type, query_text,
     execution_time_ms, row_count, created_at) = row
    user_id_pg = user_id if user_id and user_id <= 2 else 1
    pg_cursor.execute("""
        INSERT INTO query_history (id, user_id, data_source_id, query_type,
            query_text, execution_time_ms, row_count, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """, (id, user_id_pg, data_source_id, query_type, query_text,
          execution_time_ms, row_count, created_at))
pg_conn.commit()
print("   ✓ done")

# 3. 迁移 templates
print("\n3. 迁移 templates...")
sqlite_cursor.execute('SELECT * FROM templates')
rows = sqlite_cursor.fetchall()
print(f"   SQLite 有 {len(rows)} 条")
for row in rows:
    (id, name, description, config, version, is_public,
     created_by, created_at, updated_at) = row
    created_by_pg = created_by if created_by and created_by <= 2 else 1
    pg_cursor.execute("""
        INSERT INTO templates (id, name, description, config, version,
            is_public, created_by, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            name=EXCLUDED.name, config=EXCLUDED.config, version=EXCLUDED.version
    """, (id, name, description, config, version,
          bool(is_public), created_by_pg, created_at, updated_at))
pg_conn.commit()
print("   ✓ done")

# 4. 迁移 template_shares
print("\n4. 迁移 template_shares...")
sqlite_cursor.execute('SELECT * FROM template_shares')
rows = sqlite_cursor.fetchall()
print(f"   SQLite 有 {len(rows)} 条")
for row in rows:
    (template_id, user_id, shared_by, shared_at) = row
    user_id_pg = user_id if user_id <= 2 else 1
    shared_by_pg = shared_by if shared_by <= 2 else 1
    pg_cursor.execute("""
        INSERT INTO template_shares (template_id, user_id, shared_by, shared_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (template_id, user_id) DO NOTHING
    """, (template_id, user_id_pg, shared_by_pg, shared_at))
pg_conn.commit()
print("   ✓ done")

# 5. 迁移 template_versions
print("\n5. 迁移 template_versions...")
sqlite_cursor.execute('SELECT * FROM template_versions')
rows = sqlite_cursor.fetchall()
print(f"   SQLite 有 {len(rows)} 条")
for row in rows:
    (id, template_id, version, config, created_by, created_at) = row
    created_by_pg = created_by if created_by and created_by <= 2 else 1
    pg_cursor.execute("""
        INSERT INTO template_versions (id, template_id, version, config,
            created_by, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """, (id, template_id, version, config, created_by_pg, created_at))
pg_conn.commit()
print("   ✓ done")

# 6. 迁移 export_tasks
print("\n6. 迁移 export_tasks...")
sqlite_cursor.execute('SELECT * FROM export_tasks')
rows = sqlite_cursor.fetchall()
print(f"   SQLite 有 {len(rows)} 条")
for row in rows:
    (id, user_id, template_id, status, file_path, error_message,
     row_count, created_at, started_at, completed_at, sql_text) = row
    user_id_pg = user_id if user_id and user_id <= 2 else 1
    template_id_pg = template_id if template_id else None
    pg_cursor.execute("""
        INSERT INTO export_tasks (id, user_id, template_id, status,
            file_path, error_message, row_count, created_at, started_at,
            completed_at, sql)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """, (id, user_id_pg, template_id_pg, status, file_path, error_message,
          row_count, created_at, started_at, completed_at, sql_text))
pg_conn.commit()
print("   ✓ done")

# 7. 迁移 roles
print("\n7. 迁移 roles...")
sqlite_cursor.execute('SELECT * FROM roles')
rows = sqlite_cursor.fetchall()
print(f"   SQLite 有 {len(rows)} 条")
for row in rows:
    (id, name, description, permissions, created_at, updated_at) = row
    pg_cursor.execute("""
        INSERT INTO roles (id, name, description, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """, (id, name, description[:255] if description else None, created_at, updated_at))
pg_conn.commit()
print("   ✓ done")

# 验证
print("\n" + "=" * 60)
print("迁移后验证:")
print("=" * 60)
tables = ['data_sources', 'query_history', 'templates', 'template_shares',
          'template_versions', 'export_tasks', 'users', 'roles']
for table in tables:
    pg_cursor.execute(f'SELECT COUNT(*) FROM {table}')
    count = pg_cursor.fetchone()[0]
    sqlite_cursor.execute(f'SELECT COUNT(*) FROM {table}')
    sqlite_count = sqlite_cursor.fetchone()[0]
    match = "✓" if count >= sqlite_count else "✗"
    print(f"  {table}: PG={count}, SQLite={sqlite_count} {match}")

sqlite_conn.close()
pg_conn.close()
print("\n✓ 迁移完成")
