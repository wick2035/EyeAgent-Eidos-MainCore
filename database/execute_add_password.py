"""
Execute migration to add password columns to doctor and patient tables
Date: 2025-11-21
"""

import pymysql
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME', 'medical_db'),
    'charset': 'utf8mb4'
}

def execute_migration():
    """Execute the password column migration"""
    connection = None
    try:
        # Connect to database
        print("Connecting to database...")
        connection = pymysql.connect(**DB_CONFIG)
        cursor = connection.cursor()

        print(f"\n{'='*60}")
        print(f"Migration: Add Password Columns")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

        # Read SQL migration file
        sql_file_path = os.path.join(os.path.dirname(__file__), 'migrations', 'add_password_columns.sql')

        if not os.path.exists(sql_file_path):
            print(f"Error: SQL file not found at {sql_file_path}")
            return False

        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # Split SQL statements
        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip() and not stmt.strip().startswith('--')]

        # Execute each statement
        for i, statement in enumerate(statements, 1):
            if statement.upper().startswith('USE'):
                print(f"[{i}] Using database medical_db...")
                cursor.execute(statement)
            elif statement.upper().startswith('ALTER'):
                table_name = 'doctor' if 'doctor' in statement.lower() else 'patient'
                print(f"[{i}] Adding password column to {table_name} table...")
                cursor.execute(statement)
                print(f"    [OK] Password column added to {table_name}")
            elif statement.upper().startswith('SELECT'):
                cursor.execute(statement)
                result = cursor.fetchone()
                if result:
                    print(f"\n{result[0]}\n")
            elif statement.upper().startswith('DESCRIBE'):
                table_name = statement.split()[-1]
                print(f"\n{'='*60}")
                print(f"Updated structure of {table_name} table:")
                print(f"{'='*60}")
                cursor.execute(statement)
                columns = cursor.fetchall()

                # Print header
                print(f"{'Field':<30} {'Type':<20} {'Null':<6} {'Key':<6} {'Default':<15}")
                print("-" * 77)

                # Print rows
                for col in columns:
                    field = col[0][:29] if len(col[0]) > 29 else col[0]
                    type_str = col[1][:19] if len(str(col[1])) > 19 else str(col[1])
                    null_str = col[2]
                    key = col[3] if col[3] else ''
                    default = str(col[4])[:14] if col[4] is not None else 'NULL'

                    # Highlight password column
                    if col[0] == 'password':
                        print(f">>> {field:<26} {type_str:<20} {null_str:<6} {key:<6} {default:<15} <<<")
                    else:
                        print(f"{field:<30} {type_str:<20} {null_str:<6} {key:<6} {default:<15}")

                print()

        # Commit changes
        connection.commit()

        # Verify the changes
        print(f"\n{'='*60}")
        print("Verification: Check password columns")
        print(f"{'='*60}\n")

        cursor.execute("SELECT COUNT(*) FROM doctor")
        doctor_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM patient")
        patient_count = cursor.fetchone()[0]

        print(f"[OK] Doctor table: {doctor_count} records with password column added")
        print(f"[OK] Patient table: {patient_count} records with password column added")

        print(f"\n{'='*60}")
        print("Migration completed successfully!")
        print(f"{'='*60}\n")

        print("Note: Default passwords have been set:")
        print("  - Doctor accounts: 'Doctor@123'")
        print("  - Patient accounts: 'Patient@123'")
        print("\nIMPORTANT: In production, implement password hashing (bcrypt/argon2)")

        return True

    except pymysql.Error as e:
        print(f"\nDatabase error: {e}")
        if connection:
            connection.rollback()
        return False

    except Exception as e:
        print(f"\nUnexpected error: {e}")
        if connection:
            connection.rollback()
        return False

    finally:
        if connection:
            cursor.close()
            connection.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    success = execute_migration()
    exit(0 if success else 1)
