# Database Management Guide

## Overview

This guide covers database initialization, migrations, and management for the Fibtool application.

## Database Files

- **`fibtool.db`** - SQLite database file (created automatically)
- **`init_db.py`** - Initial database setup with seed data
- **`migrate.py`** - Comprehensive migration script

## Quick Start

### First Time Setup

```bash
# Navigate to backend directory
cd backend

# Initialize database with tables and seed data
python init_db.py
```

This will:
- Create all tables (users, plans, payments, subscriptions, deliveries)
- Seed 3 subscription plans
- Create admin user (admin@fibtool.com / admin123)

### Apply Migrations

```bash
# Run all pending migrations
python migrate.py

# Check database status
python migrate.py status
```

## Migration System

### How It Works

The migration system tracks which schema changes have been applied using a `schema_migrations` table. Each migration:

1. Checks if it has already been applied
2. Verifies table/column existence
3. Applies changes if needed
4. Marks itself as applied with timestamp

### Current Migrations

| Migration | Description |
|-----------|-------------|
| `001_add_error_message_to_deliveries` | Add error_message column to deliveries |
| `002_add_processing_status_to_deliveries` | Document PROCESSING status support |
| `003_add_is_admin_to_users` | Add is_admin column to users |
| `004_add_provider_reference_to_payments` | Add provider_reference column to payments |
| `005_add_paid_at_to_payments` | Add paid_at column to payments |

### Adding New Migrations

1. Open `migrate.py`
2. Add a new migration function:

```python
def migration_006_your_migration_name(self):
    """Description of what this migration does."""
    migration_name = "006_your_migration_name"
    
    if self.is_migration_applied(migration_name):
        print(f"⏭️  Skipping {migration_name} (already applied)")
        return
    
    print(f"🔄 Applying {migration_name}...")
    
    # Your migration code here
    if not self.column_exists('table_name', 'column_name'):
        self.cursor.execute("ALTER TABLE table_name ADD COLUMN column_name TEXT")
        self.conn.commit()
        print("   ✅ Added column_name column")
    
    self.mark_migration_applied(migration_name)
```

3. Add it to the migrations list in `run_all_migrations()`:

```python
migrations = [
    # ... existing migrations ...
    self.migration_006_your_migration_name,
]
```

## Database Schema

### Tables

#### users
- `id` (STRING, PK)
- `email` (STRING, UNIQUE)
- `password_hash` (STRING)
- `name` (STRING)
- `is_active` (BOOLEAN)
- `is_admin` (BOOLEAN)
- `created_at` (DATETIME)

#### plans
- `id` (STRING, PK)
- `name` (STRING)
- `type` (ENUM: ONE_OFF, SUBSCRIPTION)
- `price` (INTEGER) - cents
- `currency` (STRING)
- `interval` (ENUM: MONTHLY, YEARLY)
- `description` (TEXT)
- `is_active` (BOOLEAN)
- `created_at` (DATETIME)

#### payments
- `id` (STRING, PK)
- `user_id` (STRING, FK → users.id)
- `plan_id` (STRING, FK → plans.id)
- `amount` (INTEGER) - cents
- `currency` (STRING)
- `status` (ENUM: PENDING, PAID, FAILED, CANCELLED)
- `payment_url` (STRING)
- `poll_url` (STRING)
- `provider_reference` (STRING) - PayNow transaction ID
- `paid_at` (DATETIME)
- `created_at` (DATETIME)

#### subscriptions
- `id` (STRING, PK)
- `user_id` (STRING, FK → users.id)
- `plan_id` (STRING, FK → plans.id)
- `payment_id` (STRING, FK → payments.id)
- `status` (ENUM: ACTIVE, CANCELLED, EXPIRED)
- `started_at` (DATETIME)
- `ended_at` (DATETIME)
- `created_at` (DATETIME)

#### deliveries
- `id` (STRING, PK)
- `payment_id` (STRING, FK → payments.id)
- `user_id` (STRING, FK → users.id)
- `symbol` (STRING)
- `timeframe` (STRING)
- `file_path` (STRING)
- `status` (ENUM: PENDING, PROCESSING, SENT, FAILED)
- `error_message` (STRING)
- `email_sent_at` (DATETIME)
- `created_at` (DATETIME)

#### schema_migrations (tracking table)
- `id` (INTEGER, PK, AUTOINCREMENT)
- `migration_name` (STRING, UNIQUE)
- `applied_at` (TEXT)

## Common Operations

### Reset Database (Development Only)

```bash
# WARNING: This deletes all data!
cd backend
rm ../fibtool.db
python init_db.py
python migrate.py
```

### Check Database Status

```bash
cd backend
python migrate.py status
```

Output shows:
- All tables with their columns
- Row counts
- Applied migrations with timestamps

### Backup Database

```bash
# Create backup
cp fibtool.db fibtool.db.backup

# Restore from backup
cp fibtool.db.backup fibtool.db
```

### View Database Directly

```bash
# Using sqlite3 command line
sqlite3 fibtool.db

# Common queries
SELECT * FROM users;
SELECT * FROM plans;
SELECT * FROM payments;
SELECT * FROM schema_migrations;

# Exit
.quit
```

## Troubleshooting

### "no such column" Error

**Problem**: Code references a column that doesn't exist in database.

**Solution**:
```bash
cd backend
python migrate.py
```

### "no such table" Error

**Problem**: Tables haven't been created yet.

**Solution**:
```bash
cd backend
python init_db.py
python migrate.py
```

### Migration Failed

**Problem**: Migration script encountered an error.

**Solution**:
1. Check error message
2. Fix the issue (corrupt db, permission, etc.)
3. If needed, manually remove the migration from `schema_migrations` table
4. Run `python migrate.py` again

```sql
-- Remove failed migration
DELETE FROM schema_migrations WHERE migration_name = '001_problematic_migration';
```

### Database Locked

**Problem**: Another process is using the database.

**Solution**:
1. Stop all running backend servers
2. Close any database browser tools
3. Try again

### Check Applied Migrations

```bash
cd backend
python -c "import sqlite3; conn = sqlite3.connect('../fibtool.db'); cursor = conn.cursor(); cursor.execute('SELECT * FROM schema_migrations'); print('\n'.join([str(row) for row in cursor.fetchall()]))"
```

## Development Workflow

### Starting a New Project

```bash
cd backend
python init_db.py      # Create tables and seed data
python migrate.py      # Apply all migrations
```

### After Pulling New Code

```bash
cd backend
python migrate.py      # Apply any new migrations
```

### Before Deploying

```bash
cd backend
python migrate.py status  # Verify migrations
python -m pytest          # Run tests
```

## Production Considerations

### Database File Location

In production, consider:
- Moving database outside of code directory
- Using environment variable for database path
- Setting up proper file permissions

```python
# In app/core/database.py
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./fibtool.db')
```

### Migration Safety

Before running migrations in production:
1. **Backup the database**
2. Test migrations on a copy first
3. Run during low-traffic periods
4. Have rollback plan ready

### Monitoring

Monitor:
- Database file size
- Query performance
- Failed migrations in logs

## Advanced Topics

### Manual Schema Changes

If you need to make manual changes:

```bash
sqlite3 fibtool.db

# Add column manually
ALTER TABLE users ADD COLUMN phone TEXT;

# Record the migration
INSERT INTO schema_migrations (migration_name, applied_at) 
VALUES ('006_add_phone_to_users', datetime('now'));
```

### Data Migrations

For data transformations (not just schema):

```python
def migration_007_migrate_old_data(self):
    """Transform existing data."""
    migration_name = "007_migrate_old_data"
    
    if self.is_migration_applied(migration_name):
        return
    
    # Example: Update all NULL values
    self.cursor.execute("""
        UPDATE users 
        SET is_admin = 0 
        WHERE is_admin IS NULL
    """)
    self.conn.commit()
    
    self.mark_migration_applied(migration_name)
```

### Database Optimization

```sql
-- Analyze database
ANALYZE;

-- Vacuum to reclaim space
VACUUM;

-- Check integrity
PRAGMA integrity_check;
```

## Best Practices

1. **Always backup before migrations**
2. **Test migrations on development database first**
3. **Keep migrations small and focused**
4. **Never modify applied migrations**
5. **Document breaking changes**
6. **Use descriptive migration names**
7. **Add migrations to version control**

## Quick Reference

```bash
# Initialize database
python init_db.py

# Run migrations
python migrate.py

# Check status
python migrate.py status

# View database
sqlite3 fibtool.db

# Backup
cp fibtool.db fibtool.db.backup

# Reset (dev only)
rm fibtool.db && python init_db.py && python migrate.py
```

## Support

If you encounter issues:
1. Check this guide
2. Run `python migrate.py status` to see current state
3. Check error logs
4. Review migration code in `migrate.py`
