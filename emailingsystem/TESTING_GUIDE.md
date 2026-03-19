# Report Delivery System Testing Guide

This guide provides step-by-step instructions to test the complete report generation and delivery system.

## Prerequisites

- Backend server running on `http://localhost:8000`
- Frontend running on `http://localhost:3000`
- Database migrated with new deliveries columns
- Test user account created
- Test symbols configured in database

## Test Plan Overview

1. **Payment → Multi-Symbol Report Generation**
2. **Dashboard Reports Display**
3. **Report Download**
4. **Report Content Viewing**
5. **Symbol Filtering**
6. **Scheduled Deliveries**
7. **Download Tracking**
8. **Cleanup Tasks**

---

## Test 1: Payment to Report Generation Flow

### Objective
Verify that after payment, reports are generated for all user's selected symbols.

### Steps

1. **Login to Dashboard**
   ```
   Navigate to: http://localhost:3000/login
   Login with test credentials
   ```

2. **Configure Symbol Preferences**
   ```
   Go to: Dashboard → Symbol Preferences section
   Select multiple symbols (e.g., XAUUSD, EURUSD, GBPUSD)
   Click "Save Preferences"
   ```

3. **Make a Purchase**
   ```
   Go to: http://localhost:3000/pricing
   Select a plan (e.g., Premium - 4 symbols)
   Fill payment form
   Submit payment
   ```

4. **Verify Backend Processing**
   ```bash
   # Check backend logs
   tail -f backend/logs/app.log
   
   # Should see:
   # - Payment confirmed
   # - create_deliveries_for_payment called
   # - Multiple deliveries created (one per symbol)
   # - Report generation started for each
   ```

5. **Check Database**
   ```bash
   cd backend
   sqlite3 fibtool.db
   
   # View created deliveries
   SELECT id, symbol, symbol_id, status, report_type, created_at 
   FROM deliveries 
   ORDER BY created_at DESC 
   LIMIT 10;
   
   # Expected: One delivery per selected symbol
   ```

6. **Verify Files Created**
   ```bash
   # Check outputs/reports directory
   ls -la outputs/reports/
   
   # Expected: PNG files for each symbol
   # Example: xauusd_horizontal_lines.png
   ```

### Expected Results
- ✅ One delivery record created per selected symbol
- ✅ Each delivery has unique `symbol_id`
- ✅ PNG chart files generated in `outputs/reports/`
- ✅ `report_content` populated with markdown
- ✅ Email sent for each delivery
- ✅ `status` = "SENT" for successful deliveries

---

## Test 2: Dashboard Reports Display

### Objective
Verify reports are displayed correctly in the dashboard.

### Steps

1. **Navigate to Dashboard**
   ```
   Go to: http://localhost:3000/dashboard
   Scroll to "My Reports" section
   ```

2. **Verify Report Cards**
   - Each report should show:
     - Symbol name (e.g., "XAUUSD")
     - Status badge (color-coded)
     - Report type ("Confluence Analysis")
     - Creation date
     - Download count (if downloaded before)
     - Download button (if file exists)
     - View button (if content exists)

3. **Check Visual Elements**
   - Icons appear correctly
   - Status colors match status (green=sent, yellow=pending, red=failed)
   - Cards animate on load
   - Responsive layout works on mobile

### Expected Results
- ✅ All reports displayed in grid layout
- ✅ Correct information shown for each report
- ✅ Buttons enabled/disabled based on availability
- ✅ Visual polish (icons, colors, animations)

---

## Test 3: Report Download

### Objective
Verify users can download report chart files.

### Steps

1. **Click Download Button**
   ```
   In dashboard, click "Download" on any report
   ```

2. **Verify Download**
   - Browser should download PNG file
   - Filename format: `{SYMBOL}_2025-11-08.png`
   - File should open and display chart

3. **Check Download Tracking**
   ```bash
   # Query database
   sqlite3 backend/fibtool.db
   
   SELECT id, symbol, download_count, last_downloaded_at 
   FROM deliveries 
   WHERE id = <report_id>;
   
   # Expected: download_count incremented, last_downloaded_at updated
   ```

4. **Refresh Dashboard**
   - Reload page
   - Check report card shows updated download count

### Expected Results
- ✅ File downloads successfully
- ✅ PNG chart displays correctly
- ✅ `download_count` incremented in database
- ✅ `last_downloaded_at` timestamp updated
- ✅ Dashboard shows new download count

---

## Test 4: Report Content Viewing

### Objective
Verify users can view analysis text in modal.

### Steps

1. **Click View Button**
   ```
   In dashboard, click "View" on any report
   Modal should open
   ```

2. **Verify Modal Content**
   - Header shows symbol and date
   - Analysis text displayed (markdown format)
   - Close button works
   - Download button available in modal

3. **Test Modal Interactions**
   - Click outside modal → closes
   - Click X button → closes
   - Click "Download Chart" in modal → downloads file
   - Scroll through long content

### Expected Results
- ✅ Modal opens with smooth animation
- ✅ Content displays formatted correctly
- ✅ All buttons functional
- ✅ Modal closes properly

---

## Test 5: Symbol Filtering

### Objective
Verify filter dropdown works correctly.

### Steps

1. **Locate Filter Dropdown**
   ```
   Top right of "My Reports" section
   Dropdown showing "All Symbols"
   ```

2. **Test Filtering**
   ```
   Select "XAUUSD" from dropdown
   → Only XAUUSD reports should display
   
   Select "EURUSD"
   → Only EURUSD reports should display
   
   Select "All Symbols"
   → All reports should display
   ```

3. **Verify Empty States**
   - Filter to symbol with no reports
   - Should show "No Reports Yet" message

### Expected Results
- ✅ Dropdown populates with user's symbols
- ✅ Filtering works instantly
- ✅ "All Symbols" option shows everything
- ✅ Empty state displays when no matches

---

## Test 6: Scheduled Deliveries

### Objective
Test automated daily delivery creation for subscriptions.

### Steps

1. **Create Active Subscription**
   ```bash
   # Via API or database
   sqlite3 backend/fibtool.db
   
   INSERT INTO subscriptions (user_id, plan_id, status, start_date, end_date)
   VALUES (1, 1, 'active', datetime('now'), datetime('now', '+30 days'));
   ```

2. **Run Scheduled Task**
   ```bash
   cd backend
   python scheduled_tasks.py
   ```

3. **Check Logs**
   ```bash
   cat logs/scheduled_tasks.log
   
   # Expected output:
   # Starting daily delivery creation task...
   # Created X deliveries for active subscriptions
   # ✅ All scheduled tasks completed successfully
   ```

4. **Verify Database**
   ```bash
   sqlite3 fibtool.db
   
   SELECT COUNT(*) FROM deliveries 
   WHERE DATE(created_at) = DATE('now');
   
   # Expected: New deliveries created today
   ```

### Expected Results
- ✅ Script runs without errors
- ✅ Deliveries created for each subscription
- ✅ One delivery per symbol per user
- ✅ Reports generated and emails sent
- ✅ Logs show success messages

---

## Test 7: Download Tracking

### Objective
Verify download statistics are accurate.

### Steps

1. **Download Report Multiple Times**
   ```
   Download same report 3 times
   ```

2. **Check Database After Each Download**
   ```bash
   sqlite3 backend/fibtool.db
   
   SELECT download_count, last_downloaded_at 
   FROM deliveries WHERE id = <report_id>;
   
   # After 1st: download_count = 1
   # After 2nd: download_count = 2
   # After 3rd: download_count = 3
   # last_downloaded_at should update each time
   ```

3. **Verify Dashboard Display**
   - Refresh dashboard after downloads
   - Report card should show "Downloaded 3 times"

### Expected Results
- ✅ Each download increments counter
- ✅ Timestamp updates on each download
- ✅ Dashboard displays accurate count
- ✅ No race conditions with concurrent downloads

---

## Test 8: Cleanup Task

### Objective
Test automatic deletion of old report files.

### Steps

1. **Create Old Test Deliveries**
   ```bash
   sqlite3 backend/fibtool.db
   
   UPDATE deliveries 
   SET created_at = datetime('now', '-35 days')
   WHERE id IN (1, 2, 3);
   ```

2. **Run Cleanup Task**
   ```bash
   cd backend
   python -c "
   import asyncio
   from scheduled_tasks import cleanup_old_reports
   asyncio.run(cleanup_old_reports(days=30))
   "
   ```

3. **Verify Files Deleted**
   ```bash
   # Check outputs/reports directory
   ls outputs/reports/
   
   # Old files should be gone
   ```

4. **Verify Database Updated**
   ```bash
   sqlite3 fibtool.db
   
   SELECT id, symbol, file_path, report_content 
   FROM deliveries 
   WHERE DATE(created_at) < DATE('now', '-30 days');
   
   # Expected:
   # file_path = NULL
   # report_content still exists
   ```

5. **Check Dashboard**
   - Old reports should still appear
   - Download button disabled (no file)
   - View button still works (content exists)

### Expected Results
- ✅ Files older than 30 days deleted
- ✅ Database updated (`file_path` = NULL)
- ✅ Analysis text preserved
- ✅ Dashboard handles missing files gracefully

---

## API Testing with cURL

### Get All Reports
```bash
TOKEN="<your_jwt_token>"

curl -X GET "http://localhost:8000/api/v1/reports" \
  -H "Authorization: Bearer $TOKEN"
```

### Get Specific Report
```bash
curl -X GET "http://localhost:8000/api/v1/reports/1" \
  -H "Authorization: Bearer $TOKEN"
```

### Download Report
```bash
curl -X GET "http://localhost:8000/api/v1/reports/1/download" \
  -H "Authorization: Bearer $TOKEN" \
  --output report.png
```

### Get Report Content
```bash
curl -X GET "http://localhost:8000/api/v1/reports/1/content" \
  -H "Authorization: Bearer $TOKEN"
```

### Filter by Symbol
```bash
curl -X GET "http://localhost:8000/api/v1/reports/symbol/XAUUSD" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Error Handling Tests

### Test 1: Missing File
```bash
# Delete a report file manually
rm outputs/reports/xauusd_horizontal_lines.png

# Try to download via API
curl -X GET "http://localhost:8000/api/v1/reports/<id>/download" \
  -H "Authorization: Bearer $TOKEN"

# Expected: 404 Not Found
```

### Test 2: Unauthorized Access
```bash
# Try without token
curl -X GET "http://localhost:8000/api/v1/reports"

# Expected: 401 Unauthorized
```

### Test 3: Access Other User's Report
```bash
# Login as User A, try to access User B's report
curl -X GET "http://localhost:8000/api/v1/reports/<user_b_report_id>" \
  -H "Authorization: Bearer $USER_A_TOKEN"

# Expected: 404 Not Found (security through obscurity)
```

### Test 4: Report Generation Failure
```bash
# Cause plot script to fail (e.g., invalid symbol)
# Check that:
# - status = "FAILED"
# - error_message populated
# - Email not sent
# - Dashboard shows error state
```

---

## Performance Testing

### Load Test: Multiple Concurrent Downloads
```bash
# Use Apache Bench or similar
ab -n 100 -c 10 -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/reports/1/download
```

### Test: Large Number of Reports
```bash
# Create 50+ reports for one user
# Verify dashboard loads quickly
# Test pagination if implemented
```

### Test: Scheduled Task with Many Subscriptions
```bash
# Create 100 active subscriptions
# Run scheduled_tasks.py
# Measure execution time
# Check memory usage
```

---

## Checklist

### Database
- [ ] Migration applied successfully
- [ ] New columns exist (symbol_id, report_content, report_type, download_count, last_downloaded_at)
- [ ] Foreign keys working
- [ ] Indexes created if needed

### Backend
- [ ] Delivery service creates multiple reports
- [ ] Each symbol gets separate delivery
- [ ] Plot generation works for all symbols
- [ ] Report content generated correctly
- [ ] Emails sent successfully
- [ ] API endpoints return correct data
- [ ] Download tracking increments
- [ ] Error handling works

### Frontend
- [ ] Reports section displays on dashboard
- [ ] Report cards show correct information
- [ ] Download button triggers download
- [ ] View button opens modal
- [ ] Modal displays content correctly
- [ ] Symbol filter works
- [ ] Empty states display
- [ ] Animations smooth
- [ ] Responsive on mobile

### Scheduled Tasks
- [ ] Script runs without errors
- [ ] Daily deliveries created
- [ ] Cleanup deletes old files
- [ ] Email retry works
- [ ] Logs written correctly
- [ ] Task scheduler configured

### Integration
- [ ] Payment → report generation flow works
- [ ] Webhooks trigger deliveries
- [ ] Preferences affect report generation
- [ ] Subscriptions get daily reports
- [ ] End-to-end workflow complete

---

## Troubleshooting

### Reports Not Appearing
1. Check payment was confirmed
2. Verify user has symbol preferences
3. Check backend logs for errors
4. Query deliveries table directly

### Download Not Working
1. Verify file exists in outputs/reports/
2. Check file permissions
3. Review API logs
4. Test with cURL

### Modal Not Opening
1. Check browser console for errors
2. Verify report has report_content
3. Test click handler
4. Check z-index issues

### Scheduled Task Failing
1. Check Python path
2. Verify database accessible
3. Review logs/scheduled_tasks.log
4. Test manually first

---

## Success Criteria

All tests pass when:
- ✅ Payment creates deliveries for all selected symbols
- ✅ Dashboard displays all reports correctly
- ✅ Downloads work and tracking accurate
- ✅ Content viewing functional
- ✅ Filtering works as expected
- ✅ Scheduled tasks run successfully
- ✅ Cleanup preserves data appropriately
- ✅ Error handling graceful
- ✅ Performance acceptable
- ✅ No security issues
