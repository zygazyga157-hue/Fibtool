# Admin Dashboard Documentation

## Overview

The admin dashboard provides comprehensive system monitoring and management capabilities for administrators of the Fibtool platform.

## Access Control

Admin access is controlled by the `is_admin` flag on the User model. Only users with `is_admin=True` can access admin endpoints and pages.

### Default Admin Account
- **Email**: `admin@fibtool.com`
- **Password**: `admin123`
- **Admin Status**: `is_admin=True`

## Admin Features

### 1. Dashboard Overview (`/dashboard/admin`)

The main admin dashboard provides at-a-glance statistics:

#### Revenue Overview
- **Total Revenue**: All-time revenue from paid transactions
- **Today**: Revenue generated today
- **This Week**: Revenue from the last 7 days
- **This Month**: Revenue from the last 30 days

#### Key Metrics
- **Users**: Total, active, new today, new this week
- **Payments**: Total, paid, pending, failed, success rate
- **Subscriptions**: Total, active, inactive
- **Deliveries**: Total, pending, processing, sent, failed, success rate

#### Plans Performance
Shows purchases and revenue for each subscription plan

#### Failed Deliveries
- Lists recent failed deliveries with error messages
- **Retry Button**: Trigger re-delivery for failed plots
- Shows user email, symbol, error, and timestamp

#### Recent Activity
- **Recent Payments**: Last 5 payments with amounts and status
- **Recent Deliveries**: Last 5 deliveries with symbols and status

### 2. Users Management (`/dashboard/admin/users`)

Comprehensive user management interface:

#### Features
- **Search**: Search users by email or name
- **Pagination**: Browse through all users (20 per page)
- **User Information**:
  - Name and email
  - Admin status badge
  - Active/Inactive status
  - Payment count
  - Active subscriptions count
  - Join date

#### Actions
- **View Details**: Click eye icon to view full user profile
- **Activate/Deactivate**: Toggle user account status
- **Grant/Revoke Admin**: Manage admin privileges

### 3. Payments Management (`/dashboard/admin/payments`)

Monitor all payment transactions:

#### Features
- **Filter by Status**:
  - All payments
  - Paid only
  - Pending only
  - Failed only
- **Pagination**: 20 payments per page
- **Payment Information**:
  - Payment ID
  - User email
  - Amount and currency
  - Status with color coding
  - Provider reference (PayNow transaction ID)
  - Created date
  - Paid date (if completed)

## API Endpoints

### Dashboard Statistics
```
GET /api/v1/admin/dashboard
```
Returns comprehensive system statistics including users, payments, revenue, subscriptions, deliveries, and recent activity.

### Users Management
```
GET /api/v1/admin/users?skip=0&limit=50&search=query
GET /api/v1/admin/users/{user_id}
PATCH /api/v1/admin/users/{user_id}
  Body: { "is_active": true/false, "is_admin": true/false }
```

### Payments Management
```
GET /api/v1/admin/payments?skip=0&limit=50&status_filter=paid
```

### Deliveries Management
```
GET /api/v1/admin/deliveries/pending?limit=10
GET /api/v1/admin/deliveries/failed?limit=10
POST /api/v1/admin/deliveries/{delivery_id}/retry
```

### Revenue Statistics
```
GET /api/v1/admin/stats/revenue?days=30
```
Returns daily revenue breakdown for the specified number of days.

## Security

### Admin Access Check
All admin endpoints require:
1. Valid JWT authentication token
2. User account with `is_admin=True`

If either requirement is not met, the API returns:
```json
{
  "detail": "Admin access required"
}
```
Status code: 403 Forbidden

### Frontend Protection
The admin dashboard checks user permissions on load:
- If user is not admin, redirects to `/dashboard`
- Admin panel link only shows for admin users in navigation

## Navigation

### Access Admin Dashboard
1. Log in with admin credentials
2. From user dashboard, click **Admin Panel** button (golden crown icon)
3. Navigate between:
   - Main dashboard: `/dashboard/admin`
   - Users management: `/dashboard/admin/users`
   - Payments overview: `/dashboard/admin/payments`

### Quick Links
The main admin dashboard includes three quick-access cards:
1. **Users Management** - View and manage all users
2. **Payments Overview** - Monitor all transactions
3. **Refresh Data** - Reload dashboard statistics

## Delivery Management

### Failed Delivery Handling
When a delivery fails (plot generation or email sending):

1. **Automatic Detection**: System marks delivery as FAILED and stores error message
2. **Admin Review**: Failed deliveries appear in dashboard with:
   - User email
   - Trading symbol
   - Error message
   - Timestamp
3. **Manual Retry**: Admin can click "Retry" button to:
   - Reset delivery status to PENDING
   - Trigger new plot generation attempt
   - Send email if successful

### Delivery Statuses
- **PENDING**: Waiting to be processed
- **PROCESSING**: Plot generation in progress
- **SENT**: Successfully delivered via email
- **FAILED**: Error occurred (with error_message field)

## User Management

### Activating/Deactivating Users
```typescript
// Deactivate user (prevent login)
PATCH /admin/users/{user_id}
{ "is_active": false }

// Reactivate user
PATCH /admin/users/{user_id}
{ "is_active": true }
```

### Granting Admin Access
```typescript
// Grant admin privileges
PATCH /admin/users/{user_id}
{ "is_admin": true }

// Revoke admin privileges
PATCH /admin/users/{user_id}
{ "is_admin": false }
```

## Design Features

### Modern UI Elements
- **Gradient backgrounds**: Purple-to-slate theme
- **Glass morphism**: Backdrop blur effects
- **Color-coded status badges**: Green (success), yellow (pending), red (failed)
- **Animated transitions**: Framer Motion for smooth UX
- **Font Awesome icons**: Consistent iconography throughout

### Responsive Layout
- Mobile-friendly tables with horizontal scroll
- Adaptive grid layouts for different screen sizes
- Touch-friendly buttons and controls

## Best Practices

### For Administrators
1. **Regular Monitoring**: Check dashboard daily for failed deliveries
2. **Retry Failed Deliveries**: Use retry button for temporary failures
3. **User Management**: Deactivate suspicious accounts promptly
4. **Revenue Tracking**: Monitor daily/weekly revenue trends

### For Developers
1. **Error Logging**: All admin actions are logged server-side
2. **Permission Checks**: Always use `require_admin` dependency
3. **Pagination**: Use for large datasets to prevent performance issues
4. **Transactions**: Wrap critical operations in database transactions

## Troubleshooting

### Admin Panel Not Visible
- Verify `is_admin=True` in database
- Clear browser cache and reload
- Check JWT token is valid

### Failed Delivery Won't Retry
- Check error message for root cause
- Verify email service configuration
- Ensure plot generation script is executable
- Check `horizontal_lines_plot.py` dependencies

### Slow Dashboard Loading
- Consider implementing caching for statistics
- Optimize database queries with proper indexes
- Reduce `limit` parameter in API calls

## Future Enhancements

Potential features for future development:
- **Analytics Dashboard**: Charts and graphs for trends
- **Email Templates Manager**: Customize delivery emails
- **Bulk Actions**: Process multiple users/deliveries at once
- **Audit Log**: Track all admin actions
- **Report Generator**: Export data as CSV/PDF
- **Real-time Notifications**: WebSocket for live updates
- **Advanced Filtering**: Date ranges, amount ranges, etc.
- **User Details Page**: Complete user profile with full history
