# Purchase Permissions Guide

## 📋 Overview

Sistem Purchase menggunakan 2 jenis permission utama untuk mengontrol akses:

1. **`purchase_finance`** - Untuk Finance Team
2. **`purchase_warehouse`** - Untuk Warehouse Team

---

## 🔐 Permission Details

### 1. **purchase_finance**
**Role:** Finance Team  
**Access Level:** Finance Operations

**Permissions:**
- ✅ Verify Purchase (ubah status `received` → `verified`)
- ✅ View Purchase Payment
- ✅ Record Payment
- ✅ View Tax Invoice
- ✅ Add Tax Invoice Number
- ✅ Download Tax Invoice Reports
- ✅ Upload Tax Invoice Massal

**Views:**
- `purchase_verify` - Verify purchase
- `purchase_payment_list` - List payments
- `purchase_payment_update` - Record payment
- `purchase_taxinvoice_list` - List tax invoices
- `purchase_taxinvoice_download_excel` - Download Excel
- `purchase_taxinvoice_upload` - Upload massal

**Submenu Access:**
- Purchase Payment
- Tax Invoice

---

### 2. **purchase_warehouse**
**Role:** Warehouse Team  
**Access Level:** Warehouse Operations

**Permissions:**
- ✅ Create Purchase
- ✅ Edit Purchase (draft & pending)
- ✅ Receive Purchase (ubah status `pending` → `received`)
- ✅ Delete Purchase (draft & pending only)
- ✅ View Purchase List
- ✅ View Purchase Detail
- ✅ View Purchase Print

**Views:**
- `purchase_create` - Create new purchase
- `purchase_edit` - Edit purchase
- `purchase_receive` - Receive purchase
- `purchase_cancel` - Delete purchase

**Submenu Access:**
- Buat Purchase Baru

---

## 🎯 Action Button Rules

### Purchase List Action Buttons

| Action | Status | Permission | Button Color |
|--------|--------|------------|--------------|
| **Detail** | All | None (always visible) | Info (Blue) |
| **Verify** | Received | `purchase_finance` | Success (Green) |
| **Receive** | Pending | `purchase_warehouse` | Warning (Yellow) |
| **Edit** | Draft/Pending | `purchase_warehouse` | Primary (Blue) |
| **Hapus** | Draft/Pending | `purchase_warehouse` | Danger (Red) |

**Button Order:** Detail → Verify → Receive → Edit → Hapus

---

## 📊 Flow Diagram

```
┌─────────────┐
│   DRAFT     │ (Warehouse: Create, Edit, Delete)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   PENDING   │ (Warehouse: Edit, Receive, Delete)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  RECEIVED   │ (Finance: Verify)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  VERIFIED   │ (Finance: Payment, Tax Invoice)
└─────────────┘
```

---

## 🛠️ Setup Instructions

### 1. Create Permissions

```bash
python manage.py create_purchase_permissions
```

**Output:**
```
[OK] Created permission: purchase_finance
[OK] Created permission: purchase_warehouse
```

### 2. Assign Permissions to Users

#### Via Django Admin:
1. Go to **Django Admin** → **Users**
2. Select a user
3. Go to **Permissions** section
4. Add permission:
   - `purchasing | purchase | Can manage purchase finance`
   - `purchasing | purchase | Can manage purchase warehouse`

#### Via Django Shell:
```python
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from purchasing.models import Purchase

# Get permissions
content_type = ContentType.objects.get_for_model(Purchase)
finance_perm = Permission.objects.get(codename='purchase_finance', content_type=content_type)
warehouse_perm = Permission.objects.get(codename='purchase_warehouse', content_type=content_type)

# Assign to user
user = User.objects.get(username='finance_user')
user.user_permissions.add(finance_perm)

user = User.objects.get(username='warehouse_user')
user.user_permissions.add(warehouse_perm)

# Or assign both
user = User.objects.get(username='admin_user')
user.user_permissions.add(finance_perm, warehouse_perm)
```

### 3. Assign Permissions to Groups (Recommended)

```python
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from purchasing.models import Purchase

# Get permissions
content_type = ContentType.objects.get_for_model(Purchase)
finance_perm = Permission.objects.get(codename='purchase_finance', content_type=content_type)
warehouse_perm = Permission.objects.get(codename='purchase_warehouse', content_type=content_type)

# Create Finance Group
finance_group, _ = Group.objects.get_or_create(name='Finance Team')
finance_group.permissions.add(finance_perm)

# Create Warehouse Group
warehouse_group, _ = Group.objects.get_or_create(name='Warehouse Team')
warehouse_group.permissions.add(warehouse_perm)

# Assign users to groups
from django.contrib.auth.models import User

finance_user = User.objects.get(username='finance_user')
finance_user.groups.add(finance_group)

warehouse_user = User.objects.get(username='warehouse_user')
warehouse_user.groups.add(warehouse_group)
```

---

## 🧪 Testing

### Test Finance Permission

```python
from django.contrib.auth.models import User

# Test finance user
finance_user = User.objects.get(username='finance_user')

# Should return True
print(f"Can verify: {finance_user.has_perm('purchasing.purchase_finance')}")

# Should return False
print(f"Can edit: {finance_user.has_perm('purchasing.purchase_warehouse')}")
```

### Test Warehouse Permission

```python
from django.contrib.auth.models import User

# Test warehouse user
warehouse_user = User.objects.get(username='warehouse_user')

# Should return False
print(f"Can verify: {warehouse_user.has_perm('purchasing.purchase_finance')}")

# Should return True
print(f"Can edit: {warehouse_user.has_perm('purchasing.purchase_warehouse')}")
```

---

## 🔒 Security Notes

1. **Backend Protection:** All views check permissions using `@login_required` and `PermissionDenied`
2. **Frontend Protection:** Buttons are hidden based on `window.PERMISSIONS` object
3. **Submenu Protection:** Submenu items are hidden based on `{% if perms.purchasing.purchase_* %}`

**Important:** Frontend hiding is for UX only. Always rely on backend permission checks for security.

---

## 📝 Permission Matrix

| Feature | Finance | Warehouse | Admin |
|---------|---------|-----------|-------|
| View Purchase List | ✅ | ✅ | ✅ |
| View Purchase Detail | ✅ | ✅ | ✅ |
| Create Purchase | ❌ | ✅ | ✅ |
| Edit Purchase (Draft/Pending) | ❌ | ✅ | ✅ |
| Receive Purchase | ❌ | ✅ | ✅ |
| Verify Purchase | ✅ | ❌ | ✅ |
| Delete Purchase (Draft/Pending) | ❌ | ✅ | ✅ |
| View Payment | ✅ | ❌ | ✅ |
| Record Payment | ✅ | ❌ | ✅ |
| View Tax Invoice | ✅ | ❌ | ✅ |
| Add Tax Invoice Number | ✅ | ❌ | ✅ |
| Download Tax Invoice | ✅ | ❌ | ✅ |
| Upload Tax Invoice | ✅ | ❌ | ✅ |

---

## 🚀 Quick Start

1. **Create permissions:**
   ```bash
   python manage.py create_purchase_permissions
   ```

2. **Create groups:**
   ```python
   # Finance Team
   finance_group = Group.objects.create(name='Finance Team')
   finance_group.permissions.add(Permission.objects.get(codename='purchase_finance'))
   
   # Warehouse Team
   warehouse_group = Group.objects.create(name='Warehouse Team')
   warehouse_group.permissions.add(Permission.objects.get(codename='purchase_warehouse'))
   ```

3. **Assign users:**
   ```python
   User.objects.get(username='finance_user').groups.add(Group.objects.get(name='Finance Team'))
   User.objects.get(username='warehouse_user').groups.add(Group.objects.get(name='Warehouse Team'))
   ```

4. **Test:**
   - Login as finance user → Should see Verify, Payment, Tax Invoice
   - Login as warehouse user → Should see Create, Edit, Receive, Delete

---

## 📞 Support

If you encounter permission issues:
1. Check if permissions are created: `python manage.py create_purchase_permissions`
2. Check if user has permission: `user.has_perm('purchasing.purchase_finance')`
3. Check if user is in correct group: `user.groups.all()`
4. Clear browser cache and cookies
5. Restart Django server






