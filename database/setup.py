"""
Database setup script.
Run the schema.sql in the Supabase SQL Editor at:
https://supabase.com/dashboard/project/grgtxcvpqwzxglrbkgro/sql

Or run this script with a direct database connection:
    python database/setup.py --db-url "postgresql://postgres:PASSWORD@db.grgtxcvpqwzxglrbkgro.supabase.co:5432/postgres"
"""
import argparse
import sys
import os


def run_with_psycopg2(db_url: str, sql: str):
    import psycopg2
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql)
    cur.close()
    conn.close()
    print("Schema applied successfully!")


def main():
    parser = argparse.ArgumentParser(description="Apply database schema to Supabase")
    parser.add_argument("--db-url", help="Direct PostgreSQL connection URL")
    args = parser.parse_args()

    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        sql = f.read()

    if args.db_url:
        run_with_psycopg2(args.db_url, sql)
    else:
        print("No --db-url provided.")
        print(f"\nPlease run the SQL from {schema_path} in the Supabase SQL Editor:")
        print(f"https://supabase.com/dashboard/project/grgtxcvpqwzxglrbkgro/sql")
        print(f"\nOr provide a direct DB connection:")
        print(f'  python database/setup.py --db-url "postgresql://postgres:PASSWORD@db.grgtxcvpqwzxglrbkgro.supabase.co:5432/postgres"')


if __name__ == "__main__":
    main()
