# Admin Quick Reference Card

## 🔑 Admin Credentials
```
Email: admin@fibtool.com
Password: admin123
```

## 🚀 Quick Start
1. Log in at `http://localhost:3000/login`
2. Click golden **Admin Panel** button
3. You're in! 👑

## 📍 Admin Routes
| Page | URL | Purpose |
|------|-----|---------|
| Main Dashboard | `/dashboard/admin` | System overview & stats |
| Users | `/dashboard/admin/users` | Manage user accounts |
| Payments | `/dashboard/admin/payments` | Monitor transactions |

## 🎯 Common Tasks

### View System Stats
→ Go to `/dashboard/admin`  
→ See revenue, users, payments, deliveries at a glance

### Search for a User
→ Go to `/dashboard/admin/users`  
→ Type email or name in search box

### Deactivate Suspicious User
→ Go to `/dashboard/admin/users`  
→ Click red 🚫 button next to user

### Grant Admin to User
→ Go to `/dashboard/admin/users`  
→ Click yellow 👑 button next to user

### Retry Failed Delivery
→ Go to `/dashboard/admin`  
→ Scroll to "Failed Deliveries" section  
→ Click blue "Retry" button

### View All Paid Transactions
→ Go to `/dashboard/admin/payments`  
→ Click green "Paid" filter button

### Check Today's Revenue
→ Go to `/dashboard/admin`  
→ Look at "Revenue Overview" → "Today" card

## 🎨 Status Color Guide
| Color | Meaning |
|-------|---------|
| 🟢 Green | Paid, Sent, Active, Success |
| 🟡 Yellow | Pending, Warning |
| 🔴 Red | Failed, Error, Inactive |
| 🔵 Blue | Processing, Info |

## 🔧 Keyboard Shortcuts
| Action | Keys |
|--------|------|
| Search Users | Focus search → Type |
| Navigate | Arrow keys in tables |
| Next Page | Click pagination → |
| Previous Page | Click pagination ← |

## 📊 Key Metrics Explained

### Payment Success Rate
```
Paid Payments / Total Payments × 100%
```
Target: >90%

### Delivery Success Rate
```
Sent Deliveries / Total Deliveries × 100%
```
Target: >95%

### Active Users
Users with `is_active = true`

### New Users Today
Users who joined today (UTC timezone)

## 🚨 When to Take Action

### High Failed Deliveries
1. Check "Failed Deliveries" table
2. Read error messages
3. Retry individual deliveries
4. Contact tech support if pattern emerges

### Many Pending Payments
- Normal: Users haven't completed payment
- Action: Monitor for >24 hours

### User Complaints
1. Search user by email
2. Click 👁️ view details
3. Check payment history
4. Check delivery status

## 💰 Revenue Tracking

### Daily Check
Look at "Today" revenue card each morning

### Weekly Review
Compare "This Week" to last week's data

### Monthly Report
Review "This Month" at end of month

## 🛡️ Security Best Practices

### ✅ DO
- Regularly review new users
- Monitor failed transactions
- Deactivate suspicious accounts
- Grant admin carefully
- Check delivery errors

### ❌ DON'T
- Share admin credentials
- Leave admin panel open unattended
- Grant admin to unverified users
- Ignore failed delivery patterns

## 🆘 Troubleshooting

### "Admin access required" error
- Verify you're logged in as admin
- Check `is_admin` flag in database
- Clear browser cache

### Dashboard won't load
- Check backend server is running
- Verify database connection
- Check browser console for errors

### Retry button not working
- Check delivery exists
- Verify delivery status is FAILED
- Check backend logs

### Search returns no results
- Try partial email/name
- Check search is not case-sensitive
- Verify users exist in database

## 📞 Support Contacts

### Technical Issues
Contact: Dev Team  
Priority: High for admin panel issues

### User Complaints
Contact: Support Team  
Use admin panel to investigate first

### Payment Issues
Contact: Finance Team  
Provide payment ID from admin panel

## 📈 Performance Targets

| Metric | Target | Action if Below |
|--------|--------|-----------------|
| Payment Success Rate | >90% | Investigate PayNow integration |
| Delivery Success Rate | >95% | Check email service |
| Active Subscriptions | Growing | Review marketing |
| Daily Revenue | $X+ | Analyze pricing |

## 🎁 Pro Tips

1. **Bookmark** `/dashboard/admin` for quick access
2. **Check failed deliveries** first thing daily
3. **Use search** instead of scrolling through pages
4. **Filter payments** by status for faster review
5. **Click 👁️** for detailed user info before action
6. **Retry** failed deliveries immediately (often temporary)
7. **Monitor** new user signups for fraud patterns

## 📋 Daily Admin Checklist

Morning:
- [ ] Check today's revenue
- [ ] Review new users
- [ ] Retry failed deliveries

Midday:
- [ ] Monitor pending payments
- [ ] Check delivery queue

Evening:
- [ ] Review day's statistics
- [ ] Handle any user issues

Weekly:
- [ ] Compare week-over-week growth
- [ ] Review failed delivery patterns
- [ ] Audit admin access

## 🔐 Admin Privileges

As admin, you can:
✅ View all system statistics  
✅ Search all users  
✅ View any user's full profile  
✅ Activate/deactivate accounts  
✅ Grant/revoke admin access  
✅ View all payments  
✅ Retry failed deliveries  
✅ Access revenue analytics  

You CANNOT:
❌ Delete users (deactivate instead)  
❌ Refund payments (contact finance)  
❌ Edit payment amounts  
❌ Change user passwords (use reset)  

## 📱 Mobile Access

The admin panel is mobile-responsive:
- ✅ Works on phones/tablets
- ✅ Tables scroll horizontally
- ✅ Touch-friendly buttons
- ✅ Readable on small screens

Tip: Use landscape for tables

## 🎓 Learning Resources

- **ADMIN_GUIDE.md** - Full documentation
- **ADMIN_IMPLEMENTATION.md** - Technical details
- **Backend API** - `/api/v1/admin/*` endpoints

## 🎉 You're Ready!

You now have everything you need to effectively manage the Fibtool platform. 

Happy administrating! 👑
