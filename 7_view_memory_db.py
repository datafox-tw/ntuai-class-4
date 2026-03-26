"""
View user memories directly from PostgreSQL.

Usage:
1) Run memory example first: python 6_agent_with_memory.py
2) Inspect DB memories:      python 7_view_memory_db.py

Optional:
- python 7_view_memory_db.py --user-id john_doe@example.com
- python 7_view_memory_db.py --limit 10
"""

import argparse
import json
import os

import psycopg
from psycopg import sql
from dotenv import load_dotenv

DEFAULT_DB_URL = "postgresql://ai:ai@localhost:5532/ai"
DEFAULT_USER_ID = "john_doe@example.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect agent memories in PostgreSQL")
    parser.add_argument("--user-id", default=DEFAULT_USER_ID, help="User ID to inspect")
    parser.add_argument("--limit", type=int, default=5, help="Rows to preview per table")
    return parser.parse_args()


def fetch_user_schemas_tables(cur) -> list[tuple[str, str]]:
    cur.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
          AND table_schema NOT IN ('information_schema', 'pg_catalog')
        ORDER BY table_schema, table_name
        """
    )
    return [(row[0], row[1]) for row in cur.fetchall()]


def fetch_tables_with_user_id(cur) -> list[tuple[str, str]]:
    cur.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.columns
        WHERE column_name = 'user_id'
          AND table_schema NOT IN ('information_schema', 'pg_catalog')
        ORDER BY table_schema, table_name
        """
    )
    return [(row[0], row[1]) for row in cur.fetchall()]


def table_count(cur, schema_name: str, table_name: str) -> int:
    query = sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
        sql.Identifier(schema_name), sql.Identifier(table_name)
    )
    cur.execute(query)
    return int(cur.fetchone()[0])


def fetch_columns(cur, schema_name: str, table_name: str) -> list[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
        """,
        (schema_name, table_name),
    )
    return [row[0] for row in cur.fetchall()]


def preview_rows_for_user(
    cur,
    schema_name: str,
    table_name: str,
    user_id: str,
    limit: int,
    selected_columns: list[str],
) -> list[dict]:
    columns_sql = sql.SQL(", ").join([sql.Identifier(col) for col in selected_columns])
    query = sql.SQL("SELECT {} FROM {}.{} WHERE user_id = %s LIMIT %s").format(
        columns_sql, sql.Identifier(schema_name), sql.Identifier(table_name)
    )
    cur.execute(query, (user_id, limit))
    rows = cur.fetchall()
    return [dict(zip(selected_columns, row)) for row in rows]


def main() -> None:
    load_dotenv()
    args = parse_args()

    db_url = os.getenv("MEMORY_DB_URL", DEFAULT_DB_URL)
    print(f"Connecting to: {db_url}")
    print(f"Inspecting user: {args.user_id}\n")

    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                all_tables = fetch_user_schemas_tables(cur)
                print("=== Tables (all non-system schemas) ===")
                if not all_tables:
                    print("No tables found. Run 6_agent_with_memory.py first.")
                    return

                for schema_name, table_name in all_tables:
                    count = table_count(cur, schema_name, table_name)
                    print(f"- {schema_name}.{table_name}: {count} rows")

                print("\n=== Tables with user_id column ===")
                user_tables = fetch_tables_with_user_id(cur)
                if not user_tables:
                    print("No user_id tables found yet.")
                    return

                key_column_priority = [
                    "memory_id",
                    "memory",
                    "topics",
                    "input",
                    "user_id",
                    "created_at",
                    "updated_at",
                    "feedback",
                ]

                for schema_name, table_name in user_tables:
                    columns = fetch_columns(cur, schema_name, table_name)

                    is_memory_like = (
                        "memory" in table_name.lower() or "memory" in columns
                    )
                    if not is_memory_like:
                        continue

                    selected_columns = [
                        col for col in key_column_priority if col in columns
                    ]
                    if not selected_columns:
                        selected_columns = ["user_id"]

                    rows = preview_rows_for_user(
                        cur,
                        schema_name,
                        table_name,
                        args.user_id,
                        args.limit,
                        selected_columns,
                    )
                    print(
                        f"\n[{schema_name}.{table_name}] user_id={args.user_id} rows: {len(rows)}"
                    )
                    if not rows:
                        print("(No rows for this user)")
                        continue

                    for row in rows:
                        print(json.dumps(row, ensure_ascii=False, default=str, indent=2))

    except psycopg.OperationalError as exc:
        print("Database connection failed.")
        print("Start DB first: ./run_pgvector.sh")
        print(f"Detail: {exc}")


if __name__ == "__main__":
    main()
