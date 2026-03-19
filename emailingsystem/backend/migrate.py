"""
Comprehensive database migration script.
Handles all schema changes and updates for the Fibtool database.
"""
import sqlite3
import os
from datetime import datetime

class DatabaseMigration:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), 'fibtool.db')
        self.conn = None
        self.cursor = None
        self.migrations_applied = []
        
    def connect(self):
        """Connect to the database."""
        print(f"📁 Connecting to database: {self.db_path}")
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        print("✅ Connected successfully\n")
        
    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            print("\n✅ Database connection closed")
    
    def create_migrations_table(self):
        """Create a migrations tracking table."""
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration_name TEXT UNIQUE NOT NULL,
                    applied_at TEXT NOT NULL
                )
            """)
            self.conn.commit()
            print("✅ Migrations tracking table ready")
        except Exception as e:
            print(f"❌ Failed to create migrations table: {e}")
            raise
    
    def is_migration_applied(self, migration_name):
        """Check if a migration has already been applied."""
        self.cursor.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE migration_name = ?",
            (migration_name,)
        )
        return self.cursor.fetchone()[0] > 0
    
    def mark_migration_applied(self, migration_name):
        """Mark a migration as applied."""
        self.cursor.execute(
            "INSERT INTO schema_migrations (migration_name, applied_at) VALUES (?, ?)",
            (migration_name, datetime.utcnow().isoformat())
        )
        self.conn.commit()
        self.migrations_applied.append(migration_name)
    
    def table_exists(self, table_name):
        """Check if a table exists."""
        self.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return self.cursor.fetchone() is not None
    
    def column_exists(self, table_name, column_name):
        """Check if a column exists in a table."""
        if not self.table_exists(table_name):
            return False
        
        self.cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in self.cursor.fetchall()]
        return column_name in columns
    
    def get_table_info(self, table_name):
        """Get table structure information."""
        if not self.table_exists(table_name):
            return []
        
        self.cursor.execute(f"PRAGMA table_info({table_name})")
        return self.cursor.fetchall()
    
    # ========== MIGRATION FUNCTIONS ==========
    
    def migration_001_add_error_message_to_deliveries(self):
        """Add error_message column to deliveries table."""
        migration_name = "001_add_error_message_to_deliveries"
        
        if self.is_migration_applied(migration_name):
            print(f"⏭️  Skipping {migration_name} (already applied)")
            return
        
        print(f"🔄 Applying {migration_name}...")
        
        if not self.table_exists('deliveries'):
            print("   ⚠️  Deliveries table doesn't exist yet, will be created by init_db.py")
            self.mark_migration_applied(migration_name)
            return
        
        if not self.column_exists('deliveries', 'error_message'):
            self.cursor.execute("ALTER TABLE deliveries ADD COLUMN error_message TEXT")
            self.conn.commit()
            print("   ✅ Added error_message column")
        else:
            print("   ✅ Column already exists")
        
        self.mark_migration_applied(migration_name)
    
    def migration_002_add_processing_status_to_deliveries(self):
        """Ensure PROCESSING status is supported (no schema change, just documentation)."""
        migration_name = "002_add_processing_status_to_deliveries"
        
        if self.is_migration_applied(migration_name):
            print(f"⏭️  Skipping {migration_name} (already applied)")
            return
        
        print(f"🔄 Applying {migration_name}...")
        print("   ✅ PROCESSING status is supported in DeliveryStatus enum")
        
        self.mark_migration_applied(migration_name)
    
    def migration_003_add_is_admin_to_users(self):
        """Add is_admin column to users table."""
        migration_name = "003_add_is_admin_to_users"
        
        if self.is_migration_applied(migration_name):
            print(f"⏭️  Skipping {migration_name} (already applied)")
            return
        
        print(f"🔄 Applying {migration_name}...")
        
        if not self.table_exists('users'):
            print("   ⚠️  Users table doesn't exist yet, will be created by init_db.py")
            self.mark_migration_applied(migration_name)
            return
        
        if not self.column_exists('users', 'is_admin'):
            self.cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
            self.conn.commit()
            print("   ✅ Added is_admin column")
        else:
            print("   ✅ Column already exists")
        
        self.mark_migration_applied(migration_name)
    
    def migration_004_add_provider_reference_to_payments(self):
        """Add provider_reference column to payments table."""
        migration_name = "004_add_provider_reference_to_payments"
        
        if self.is_migration_applied(migration_name):
            print(f"⏭️  Skipping {migration_name} (already applied)")
            return
        
        print(f"🔄 Applying {migration_name}...")
        
        if not self.table_exists('payments'):
            print("   ⚠️  Payments table doesn't exist yet, will be created by init_db.py")
            self.mark_migration_applied(migration_name)
            return
        
        if not self.column_exists('payments', 'provider_reference'):
            self.cursor.execute("ALTER TABLE payments ADD COLUMN provider_reference TEXT")
            self.conn.commit()
            print("   ✅ Added provider_reference column")
        else:
            print("   ✅ Column already exists")
        
        self.mark_migration_applied(migration_name)
    
    def migration_005_add_paid_at_to_payments(self):
        """Add paid_at column to payments table."""
        migration_name = "005_add_paid_at_to_payments"
        
        if self.is_migration_applied(migration_name):
            print(f"⏭️  Skipping {migration_name} (already applied)")
            return
        
        print(f"🔄 Applying {migration_name}...")
        
        if not self.table_exists('payments'):
            print("   ⚠️  Payments table doesn't exist yet, will be created by init_db.py")
            self.mark_migration_applied(migration_name)
            return
        
        if not self.column_exists('payments', 'paid_at'):
            self.cursor.execute("ALTER TABLE payments ADD COLUMN paid_at TEXT")
            self.conn.commit()
            print("   ✅ Added paid_at column")
        else:
            print("   ✅ Column already exists")
        
        self.mark_migration_applied(migration_name)
    
    # ========== MAIN MIGRATION RUNNER ==========
    
    def run_all_migrations(self):
        """Run all pending migrations in order."""
        print("\n" + "="*60)
        print("🚀 DATABASE MIGRATION SCRIPT")
        print("="*60 + "\n")
        
        try:
            self.connect()
            self.create_migrations_table()
            
            # List of all migrations in order
            migrations = [
                self.migration_001_add_error_message_to_deliveries,
                self.migration_002_add_processing_status_to_deliveries,
                self.migration_003_add_is_admin_to_users,
                self.migration_004_add_provider_reference_to_payments,
                self.migration_005_add_paid_at_to_payments,
            ]
            
            print(f"\n📋 Found {len(migrations)} migrations to check\n")
            
            # Run each migration
            for migration in migrations:
                try:
                    migration()
                except Exception as e:
                    print(f"\n❌ Migration failed: {e}")
                    self.conn.rollback()
                    raise
            
            print("\n" + "="*60)
            if self.migrations_applied:
                print(f"✅ Successfully applied {len(self.migrations_applied)} migration(s):")
                for m in self.migrations_applied:
                    print(f"   - {m}")
            else:
                print("✅ All migrations already applied - database is up to date!")
            print("="*60)
            
        except Exception as e:
            print(f"\n❌ Migration process failed: {e}")
            raise
        finally:
            self.disconnect()
    
    def show_database_status(self):
        """Show current database status and table structures."""
        print("\n" + "="*60)
        print("📊 DATABASE STATUS")
        print("="*60 + "\n")
        
        try:
            self.connect()
            
            # Get all tables
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in self.cursor.fetchall()]
            
            print(f"📁 Found {len(tables)} tables:\n")
            
            for table in tables:
                print(f"📋 Table: {table}")
                info = self.get_table_info(table)
                for col in info:
                    col_id, name, type_, notnull, default, pk = col
                    nullable = "NOT NULL" if notnull else "NULL"
                    pk_marker = " [PK]" if pk else ""
                    print(f"   - {name}: {type_} ({nullable}){pk_marker}")
                
                # Count rows
                self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = self.cursor.fetchone()[0]
                print(f"   📊 Rows: {count}\n")
            
            # Show applied migrations
            if self.table_exists('schema_migrations'):
                self.cursor.execute("SELECT migration_name, applied_at FROM schema_migrations ORDER BY applied_at")
                migrations = self.cursor.fetchall()
                
                print(f"\n✅ Applied Migrations ({len(migrations)}):")
                for name, applied_at in migrations:
                    print(f"   - {name} (applied: {applied_at})")
            
        finally:
            self.disconnect()


def main():
    """Main entry point."""
    import sys
    
    migrator = DatabaseMigration()
    
    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        # Show database status
        migrator.show_database_status()
    else:
        # Run migrations
        migrator.run_all_migrations()
        print("\n💡 Tip: Run 'python migrate.py status' to see database structure")


if __name__ == "__main__":
    main()
