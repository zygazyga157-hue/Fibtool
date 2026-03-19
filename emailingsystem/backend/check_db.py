"""
Database schema inspection script.
"""
import sqlite3
import os

def check_database():
    db_path = os.path.join(os.path.dirname(__file__), 'fibtool.db')
    
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return
    
    print(f"📁 Database: {db_path}")
    print("=" * 80)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        if not tables:
            print("⚠️  No tables found in database!\n")
            print("Run: python init_db.py")
            return
        
        print(f"\n✅ Found {len(tables)} table(s):\n")
        
        for table in tables:
            print(f"\n📋 Table: {table}")
            print("-" * 80)
            
            # Get table structure
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            
            print(f"{'Column':<30} {'Type':<15} {'Nullable':<10} {'Default':<20}")
            print("-" * 80)
            
            for col in columns:
                col_id, name, col_type, not_null, default_val, pk = col
                nullable = "NOT NULL" if not_null else "NULL"
                default = str(default_val) if default_val else "-"
                pk_marker = " [PK]" if pk else ""
                print(f"{name:<30} {col_type:<15} {nullable:<10} {default:<20}{pk_marker}")
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"\n📊 Rows: {count}")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_database()
