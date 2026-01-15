#!/usr/bin/env python3
"""
Generate SQLite database from database.json

Creates a CRM/project management database with realistic data that can be
queried independently or cross-referenced with document content.

Usage:
    uv run generate-db [--output-dir OUTPUT_DIR]
"""

import argparse
import json
import sqlite3
from pathlib import Path


def create_schema(conn: sqlite3.Connection, schema: dict) -> None:
    """Create database tables from schema definition."""
    cursor = conn.cursor()

    # Define table creation order to handle foreign keys
    table_order = [
        "employees",
        "clients",
        "contacts",
        "projects",
        "project_assignments",
        "time_entries",
        "invoices",
        "expenses",
    ]

    for table_name in table_order:
        if table_name not in schema:
            continue

        table_def = schema[table_name]
        columns = table_def["columns"]

        # Build CREATE TABLE statement
        col_defs = []
        for col_name, col_type in columns.items():
            col_defs.append(f"{col_name} {col_type}")

        create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n  "
        create_sql += ",\n  ".join(col_defs)
        create_sql += "\n)"

        cursor.execute(create_sql)

    conn.commit()


def insert_data(conn: sqlite3.Connection, data: dict) -> dict:
    """Insert data into tables. Returns count of rows inserted per table."""
    cursor = conn.cursor()
    counts = {}

    # Insert order matters for foreign keys
    table_order = [
        "employees",
        "clients",
        "contacts",
        "projects",
        "project_assignments",
        "time_entries",
        "invoices",
        "expenses",
    ]

    for table_name in table_order:
        if table_name not in data:
            continue

        rows = data[table_name]
        if not rows:
            continue

        # Get column names from first row
        columns = list(rows[0].keys())
        placeholders = ", ".join(["?" for _ in columns])
        col_names = ", ".join(columns)

        insert_sql = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"

        for row in rows:
            values = [row.get(col) for col in columns]
            cursor.execute(insert_sql, values)

        counts[table_name] = len(rows)

    conn.commit()
    return counts


def create_indexes(conn: sqlite3.Connection) -> None:
    """Create useful indexes for common queries."""
    cursor = conn.cursor()

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_contacts_client ON contacts(client_id)",
        "CREATE INDEX IF NOT EXISTS idx_projects_client ON projects(client_id)",
        "CREATE INDEX IF NOT EXISTS idx_time_entries_project ON time_entries(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_time_entries_employee ON time_entries(employee_id)",
        "CREATE INDEX IF NOT EXISTS idx_invoices_client ON invoices(client_id)",
        "CREATE INDEX IF NOT EXISTS idx_invoices_project ON invoices(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_expenses_project ON expenses(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_clients_code ON clients(code)",
        "CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number)",
    ]

    for idx_sql in indexes:
        cursor.execute(idx_sql)

    conn.commit()


def create_views(conn: sqlite3.Connection) -> None:
    """Create useful views for common queries."""
    cursor = conn.cursor()

    views = [
        """
        CREATE VIEW IF NOT EXISTS v_project_summary AS
        SELECT
            p.id,
            p.name AS project_name,
            c.name AS client_name,
            c.code AS client_code,
            p.type,
            p.status,
            p.budget_net,
            p.start_date,
            p.end_date,
            e.name AS lead_name,
            COALESCE(SUM(t.hours), 0) AS total_hours,
            COALESCE(SUM(exp.amount_net), 0) AS total_expenses
        FROM projects p
        LEFT JOIN clients c ON p.client_id = c.id
        LEFT JOIN employees e ON p.lead_employee_id = e.id
        LEFT JOIN time_entries t ON p.id = t.project_id
        LEFT JOIN expenses exp ON p.id = exp.project_id
        GROUP BY p.id
        """,
        """
        CREATE VIEW IF NOT EXISTS v_client_revenue AS
        SELECT
            c.id,
            c.code,
            c.name,
            c.industry,
            c.status,
            COUNT(DISTINCT i.id) AS invoice_count,
            COALESCE(SUM(i.amount_net), 0) AS total_revenue_net,
            COALESCE(SUM(i.amount_gross), 0) AS total_revenue_gross
        FROM clients c
        LEFT JOIN invoices i ON c.id = i.client_id AND i.status = 'paid'
        GROUP BY c.id
        """,
        """
        CREATE VIEW IF NOT EXISTS v_employee_hours AS
        SELECT
            e.id,
            e.name,
            e.role,
            e.hourly_rate,
            COALESCE(SUM(t.hours), 0) AS total_hours,
            COALESCE(SUM(t.hours * e.hourly_rate), 0) AS total_value
        FROM employees e
        LEFT JOIN time_entries t ON e.id = t.employee_id
        GROUP BY e.id
        """,
    ]

    for view_sql in views:
        cursor.execute(view_sql)

    conn.commit()


def verify_database(conn: sqlite3.Connection, expected_counts: dict) -> bool:
    """Verify database was created correctly."""
    cursor = conn.cursor()
    all_ok = True

    for table_name, expected in expected_counts.items():
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        actual = cursor.fetchone()[0]
        if actual != expected:
            print(f"  ERROR: {table_name} has {actual} rows, expected {expected}")
            all_ok = False

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Generate SQLite database from database.json")
    parser.add_argument("--output-dir", "-o", default="output", help="Output directory")
    parser.add_argument("--input", "-i", default="dataset/database.json", help="Input JSON file")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load database definition
    with open(args.input, "r", encoding="utf-8") as f:
        db_def = json.load(f)

    db_name = db_def["meta"]["database_name"]
    db_path = output_dir / db_name

    # Remove existing database
    if db_path.exists():
        db_path.unlink()

    print(f"Creating database: {db_path}")

    # Create database
    conn = sqlite3.connect(str(db_path))

    try:
        # Create schema
        print("  Creating schema...")
        create_schema(conn, db_def["schema"])

        # Insert data
        print("  Inserting data...")
        counts = insert_data(conn, db_def["data"])
        for table, count in counts.items():
            print(f"    {table}: {count} rows")

        # Create indexes
        print("  Creating indexes...")
        create_indexes(conn)

        # Create views
        print("  Creating views...")
        create_views(conn)

        # Verify
        print("  Verifying...")
        if verify_database(conn, counts):
            print(f"\nDatabase created successfully: {db_path}")
            print(f"  Tables: {len(counts)}")
            print(f"  Total rows: {sum(counts.values())}")
        else:
            print("\nERROR: Database verification failed")
            raise SystemExit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
