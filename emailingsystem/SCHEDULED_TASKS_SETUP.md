# FibTool Scheduled Tasks Setup

This document explains how to set up automated scheduled tasks for the FibTool system.

## Overview

The `scheduled_tasks.py` script performs three automated tasks:

1. **Daily Report Deliveries** - Creates confluence analysis reports for all users with active subscriptions
2. **Report Cleanup** - Removes report files older than 30 days to save storage (keeps database records)
3. **Email Retry** - Retries sending emails for recent deliveries that failed

## Prerequisites

- Python environment with all backend dependencies installed
- Database properly configured
- Email service configured

## Setup Instructions

### Windows Task Scheduler

1. **Open Task Scheduler**
   - Press `Win + R`, type `taskschd.msc`, press Enter

2. **Create New Task**
   - Click "Create Task" in the right panel
   - Name: `FibTool Daily Reports`
   - Description: `Creates daily confluence reports for active subscribers`

3. **Configure Trigger**
   - Go to "Triggers" tab, click "New..."
   - Begin the task: `On a schedule`
   - Settings: `Daily`
   - Start time: `01:00:00` (1:00 AM)
   - Recur every: `1 days`
   - Click OK

4. **Configure Action**
   - Go to "Actions" tab, click "New..."
   - Action: `Start a program`
   - Program/script: Browse to `run_scheduled_tasks.bat`
     - Example: `C:\Users\DELL\Development\Telegram2\Signals\Fibtool\emailingsystem\backend\run_scheduled_tasks.bat`
   - Start in: `C:\Users\DELL\Development\Telegram2\Signals\Fibtool\emailingsystem\backend`
   - Click OK

5. **Configure Settings**
   - Go to "Settings" tab
   - Check: `Allow task to be run on demand`
   - Check: `Run task as soon as possible after scheduled start is missed`
   - Check: `If task fails, restart every: 10 minutes`
   - Attempt to restart up to: `3 times`
   - Click OK

6. **Test the Task**
   - Right-click the task in the list
   - Select "Run"
   - Check the logs at: `backend/logs/scheduled_tasks.log`

### Linux/Mac Cron Job

1. **Edit Crontab**
   ```bash
   crontab -e
   ```

2. **Add Cron Job**
   ```bash
   # Run FibTool scheduled tasks daily at 1:00 AM
   0 1 * * * cd /path/to/emailingsystem/backend && /path/to/python scheduled_tasks.py >> logs/cron.log 2>&1
   ```

3. **Example with Virtual Environment**
   ```bash
   0 1 * * * cd /path/to/emailingsystem/backend && /path/to/venv/bin/python scheduled_tasks.py >> logs/cron.log 2>&1
   ```

4. **Save and Exit**
   - Press `Esc`, type `:wq`, press Enter (vim)
   - Or `Ctrl + X`, `Y`, `Enter` (nano)

5. **Verify Cron Job**
   ```bash
   crontab -l
   ```

## Manual Testing

### Test All Tasks
```bash
cd backend
python scheduled_tasks.py
```

### Test Individual Tasks
```python
import asyncio
from scheduled_tasks import create_daily_deliveries, cleanup_old_reports, send_pending_emails

# Test daily deliveries
asyncio.run(create_daily_deliveries())

# Test cleanup (7 days for testing)
asyncio.run(cleanup_old_reports(days=7))

# Test email retry
asyncio.run(send_pending_emails())
```

## Monitoring

### Check Logs
```bash
# View recent logs
tail -f backend/logs/scheduled_tasks.log

# Windows PowerShell
Get-Content backend\logs\scheduled_tasks.log -Tail 50 -Wait
```

### Log Format
```
2025-11-08 01:00:01 - __main__ - INFO - Starting FibTool Scheduled Tasks
2025-11-08 01:00:02 - __main__ - INFO - Starting daily delivery creation task...
2025-11-08 01:00:05 - __main__ - INFO - ✅ Created 15 deliveries for active subscriptions
2025-11-08 01:00:06 - __main__ - INFO - Starting cleanup of reports older than 30 days...
2025-11-08 01:00:07 - __main__ - INFO - ✅ Cleanup complete: 23 files deleted, 0 errors
2025-11-08 01:00:08 - __main__ - INFO - Checking for pending email deliveries...
2025-11-08 01:00:09 - __main__ - INFO - Email retry complete: 2 sent, 0 failed
2025-11-08 01:00:10 - __main__ - INFO - ✅ All scheduled tasks completed successfully
```

## Task Details

### 1. Daily Report Deliveries

**What it does:**
- Queries all active subscriptions
- For each subscription, fetches user's selected symbols
- Creates delivery records for each symbol
- Triggers report generation and email sending

**Expected behavior:**
- Runs once per day
- Creates one delivery per symbol per user
- Only processes active subscriptions
- Logs count of deliveries created

### 2. Report Cleanup

**What it does:**
- Finds delivery records older than 30 days
- Deletes physical PNG files from disk
- Updates database to set `file_path = NULL`
- Keeps `report_content` (markdown analysis) in database

**Expected behavior:**
- Frees up disk space
- Users can still view analysis text
- Download button disabled for old reports
- Logs count of files deleted

### 3. Email Retry

**What it does:**
- Finds recent deliveries (last 24 hours) where:
  - Report was generated successfully
  - Email wasn't sent
  - File exists
- Attempts to send email again
- Updates `email_sent_at` timestamp on success

**Expected behavior:**
- Catches failed email sends
- Only retries recent deliveries
- Logs success/failure for each attempt

## Customization

### Change Schedule

Edit the cron expression or Task Scheduler trigger time.

Common cron schedules:
```bash
# Every day at 2:00 AM
0 2 * * *

# Every 6 hours
0 */6 * * *

# Every Monday at 9:00 AM
0 9 * * 1

# First day of every month at midnight
0 0 1 * *
```

### Change Cleanup Period

Edit `scheduled_tasks.py`:
```python
# Keep reports for 60 days instead of 30
tasks_results["cleanup"] = await cleanup_old_reports(days=60)
```

### Disable Specific Tasks

Comment out tasks in `run_all_tasks()`:
```python
# Don't run cleanup
# tasks_results["cleanup"] = await cleanup_old_reports(days=30)
```

## Troubleshooting

### Task Not Running

1. **Check Task Scheduler Status** (Windows)
   - Open Task Scheduler
   - Check "Last Run Result" column
   - 0x0 = Success, other codes = Error

2. **Check Cron Logs** (Linux/Mac)
   ```bash
   grep CRON /var/log/syslog
   ```

3. **Check Python Path**
   - Make sure Python is in system PATH
   - Or use absolute path to Python executable

### Permission Errors

**Windows:**
- Run Task Scheduler as Administrator
- Check task runs with correct user account

**Linux/Mac:**
- Check file permissions: `chmod +x scheduled_tasks.py`
- Check log directory permissions

### Database Connection Errors

- Ensure database file exists
- Check file permissions
- Verify database path in configuration

### Email Sending Errors

- Check SMTP configuration
- Verify email credentials
- Check network connectivity
- Review email service logs

## Production Recommendations

1. **Use a Virtual Environment**
   - Isolate dependencies
   - Easier Python path management

2. **Set Up Monitoring**
   - Log aggregation service (e.g., Papertrail, Loggly)
   - Alert on failed tasks
   - Monitor disk space

3. **Database Backups**
   - Schedule before running tasks
   - Keep multiple backup versions

4. **Error Notifications**
   - Add email/SMS alerts for failures
   - Integrate with monitoring service

5. **Resource Management**
   - Monitor CPU/memory usage
   - Limit concurrent report generations
   - Consider queue system for high load

## Support

For issues or questions:
- Check logs first: `backend/logs/scheduled_tasks.log`
- Review error messages
- Verify configuration
- Test manually before scheduling
