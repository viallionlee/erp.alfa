# Purchasing Permissions Documentation

## Permission Structure

Purchasing module menggunakan 5 permissions yang terorganisir berdasarkan role dan module:

### 1. **PO (Purchase Order) Permissions**

#### `purchasing.po_view`
- **Module:** Purchase Order List
- **Access:** View PO List & Detail
- **Views:**
  - `po_list` - List all Purchase Orders
  - `po_detail` - View Purchase Order detail
- **Menu:** Purchase Order List (in sidebar)

#### `purchasing.po_marketing`
- **Module:** Purchase Order Management (Marketing)
- **Access:** Create, Edit, Detail PO
- **Views:**
  - `po_create` - Create new Purchase Order
  - `po_edit` - Edit Purchase Order
  - `po_detail` - View Purchase Order detail
- **Menu:** Buat PO Baru (in sidebar)

---

### 2. **Purchase Permissions**

#### `purchasing.purchase_view`
- **Module:** Purchase List
- **Access:** View Purchase List & Detail
- **Views:**
  - `purchase_list` - List all Purchases
  - `purchase_detail` - View Purchase detail
- **Menu:** Purchase List (in sidebar)

#### `purchasing.purchase_warehouse`
- **Module:** Purchase Management (Warehouse)
- **Access:** Create, Edit, Receive, Delete Purchase
- **Views:**
  - `purchase_create` - Create new Purchase
  - `purchase_edit` - Edit Purchase
  - `purchase_receive` - Receive Purchase (update stock)
  - `purchase_delete` - Delete Purchase
  - `purchase_detail` - View Purchase detail
- **Menu:** Buat Purchase Baru (in sidebar)
- **Templates:**
  - `purchase_list.html` - Edit & Delete buttons
  - `mobile_purchase_list.html` - Edit, Receive & Delete buttons
  - `mobile_purchase_edit.html` - Edit & Save buttons
  - `mobile_purchase_detail.html` - View only

#### `purchasing.purchase_finance`
- **Module:** Purchase Finance (Finance)
- **Access:** Verify Purchase, Payment, Tax Invoice
- **Views:**
  - `purchase_verify` - Verify Purchase
  - `purchase_payment` - Manage Purchase Payment (future)
  - `purchase_tax_invoice` - Manage Tax Invoice (future)
- **Menu:** 
  - Purchase Payment (in sidebar)
  - Tax Invoice (in sidebar)
- **Templates:**
  - `purchase_list.html` - Verify button
  - `mobile_purchase_list.html` - Verify button

---

## Permission Mapping

| Permission | PO List | PO Detail | PO Create | PO Edit | Purchase List | Purchase Detail | Purchase Create | Purchase Edit | Purchase Receive | Purchase Verify | Purchase Delete | Payment | Tax Invoice |
|------------|---------|-----------|-----------|---------|---------------|-----------------|-----------------|---------------|------------------|-----------------|-----------------|---------|-------------|
| `po_view` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `po_marketing` | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `purchase_view` | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `purchase_warehouse` | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| `purchase_finance` | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ |

---

## Role-Based Access

### **Marketing Role**
- `purchasing.po_view` - View PO List
- `purchasing.po_marketing` - Create & Edit PO

**Access:**
- ✅ View PO List
- ✅ View PO Detail
- ✅ Create PO
- ✅ Edit PO (draft & pending)
- ❌ Purchase List
- ❌ Purchase Create/Edit

---

### **Warehouse Role**
- `purchasing.purchase_view` - View Purchase List
- `purchasing.purchase_warehouse` - Manage Purchases

**Access:**
- ❌ PO List
- ✅ View Purchase List
- ✅ View Purchase Detail
- ✅ Create Purchase
- ✅ Edit Purchase (draft & pending)
- ✅ Receive Purchase (update stock)
- ✅ Delete Purchase (draft & pending)
- ❌ Verify Purchase
- ❌ Payment
- ❌ Tax Invoice

---

### **Finance Role**
- `purchasing.purchase_view` - View Purchase List
- `purchasing.purchase_finance` - Finance Operations

**Access:**
- ❌ PO List
- ✅ View Purchase List
- ✅ View Purchase Detail
- ✅ Verify Purchase
- ✅ Manage Payment
- ✅ Manage Tax Invoice
- ❌ Create/Edit Purchase
- ❌ Receive Purchase
- ❌ Delete Purchase

---

### **Superuser / Admin**
- All permissions

**Access:**
- ✅ All PO operations
- ✅ All Purchase operations
- ✅ Finance operations

---

## Implementation Details

### 1. **Models** (`purchasing/models.py`)

```python
# PurchaseOrder
class Meta:
    permissions = [
        ('po_view', 'Can view Purchase Order'),
        ('po_marketing', 'Can create/edit Purchase Order (Marketing)'),
    ]

# Purchase
class Meta:
    permissions = [
        ('purchase_view', 'Can view Purchase'),
        ('purchase_warehouse', 'Can create/edit/receive Purchase (Warehouse)'),
        ('purchase_finance', 'Can verify/payment/tax invoice Purchase (Finance)'),
    ]
```

---

### 2. **Views** (`purchasing/views.py`)

```python
# PO Views
@login_required
def po_list(request):
    if not request.user.has_perm('purchasing.po_view'):
        raise PermissionDenied("You don't have permission to view Purchase Orders.")
    # ...

@login_required
def po_create(request):
    if not request.user.has_perm('purchasing.po_marketing'):
        raise PermissionDenied("You don't have permission to create Purchase Orders.")
    # ...

@login_required
def po_edit(request, pk):
    if not request.user.has_perm('purchasing.po_marketing'):
        raise PermissionDenied("You don't have permission to edit Purchase Orders.")
    # ...

# Purchase Views
@login_required
def purchase_list(request):
    if not request.user.has_perm('purchasing.purchase_view'):
        raise PermissionDenied("You don't have permission to view Purchases.")
    # ...

@login_required
def purchase_create(request):
    if not request.user.has_perm('purchasing.purchase_warehouse'):
        raise PermissionDenied("You don't have permission to create Purchases.")
    # ...

@login_required
def purchase_edit(request, purchase_id):
    if not request.user.has_perm('purchasing.purchase_warehouse'):
        raise PermissionDenied("You don't have permission to edit Purchases.")
    # ...

@login_required
def purchase_receive(request, purchase_id):
    if not request.user.has_perm('purchasing.purchase_warehouse'):
        raise PermissionDenied("You don't have permission to receive Purchases.")
    # ...

@login_required
def purchase_verify(request, purchase_id):
    if not request.user.has_perm('purchasing.purchase_finance'):
        raise PermissionDenied("You don't have permission to verify Purchases.")
    # ...

@login_required
def purchase_delete(request, purchase_id):
    if not request.user.has_perm('purchasing.purchase_warehouse'):
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    # ...
```

---

### 3. **Context Processor** (`erp_alfa/context_processors.py`)

```python
def purchasing_permissions(request):
    """
    Context processor untuk menyediakan purchasing permissions ke semua template
    """
    context = {}
    
    if request.user.is_authenticated:
        context['purchasing_po_view'] = request.user.has_perm('purchasing.po_view')
        context['purchasing_po_marketing'] = request.user.has_perm('purchasing.po_marketing')
        context['purchasing_purchase_view'] = request.user.has_perm('purchasing.purchase_view')
        context['purchasing_purchase_warehouse'] = request.user.has_perm('purchasing.purchase_warehouse')
        context['purchasing_purchase_finance'] = request.user.has_perm('purchasing.purchase_finance')
    else:
        context['purchasing_po_view'] = False
        context['purchasing_po_marketing'] = False
        context['purchasing_purchase_view'] = False
        context['purchasing_purchase_warehouse'] = False
        context['purchasing_purchase_finance'] = False
    
    return context
```

---

### 4. **Templates**

#### **Base Template** (`templates/base.html`)

```django
{% if perms.purchasing.view_purchaseorder %}
<li class="nav-item dropdown">
    <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
        Purchasing
    </a>
    <ul class="dropdown-menu">
        <!-- PO Menu -->
        <li><a class="dropdown-item" href="{% url 'purchasing:po_list' %}">Purchase Order List</a></li>
        <li><a class="dropdown-item" href="{% url 'purchasing:po_create' %}">Buat PO Baru</a></li>
        
        <!-- Purchase Menu -->
        {% if perms.purchasing.view_purchase %}
        <li><a class="dropdown-item" href="{% url 'purchasing:purchase_list' %}">Purchase List</a></li>
        
        {% if perms.purchasing.purchase_warehouse %}
        <li><a class="dropdown-item" href="{% url 'purchasing:purchase_create' %}">Buat Purchase Baru</a></li>
        {% endif %}
        
        {% if perms.purchasing.purchase_finance %}
        <li><a class="dropdown-item" href="{% url 'purchasing:purchase_payment_list' %}">Purchase Payment</a></li>
        <li><a class="dropdown-item" href="{% url 'purchasing:purchase_taxinvoice_list' %}">Tax Invoice</a></li>
        {% endif %}
        {% endif %}
    </ul>
</li>
{% endif %}
```

#### **Purchase List Template** (`templates/purchasing/purchase_list.html`)

```javascript
<script>
    // Pass permissions to JavaScript
    window.PERMISSIONS = {
        finance: {% if perms.purchasing.purchase_finance %}true{% else %}false{% endif %},
        warehouse: {% if perms.purchasing.purchase_warehouse %}true{% else %}false{% endif %}
    };
</script>
```

```javascript
// Verify button (Finance permission)
if (purchase.status_value === 'received' && window.PERMISSIONS.finance) {
    updateBtn = '<a href="/purchaseorder/purchase/' + purchase.id + '/verify/" class="btn btn-sm btn-info">Verify</a>';
}

// Receive button (Warehouse permission)
else if (purchase.status_value === 'pending' && window.PERMISSIONS.warehouse) {
    updateBtn = '<a href="/purchaseorder/purchase/' + purchase.id + '/" class="btn btn-sm btn-success">Receive</a>';
}

// Edit button (Warehouse permission)
if ((purchase.status_value === 'draft' || purchase.status_value === 'pending') && window.PERMISSIONS.warehouse) {
    dropdownItems += '<li><a class="dropdown-item" href="/purchaseorder/purchase/' + purchase.id + '/edit/"><i class="bi bi-pencil"></i> Edit</a></li>';
}

// Delete button (Warehouse permission)
if ((purchase.status_value === 'draft' || purchase.status_value === 'pending') && window.PERMISSIONS.warehouse) {
    dropdownItems += '<li><button class="dropdown-item text-danger btn-delete-purchase">...</button></li>';
}
```

---

## Migration

Permissions dibuat melalui Django migrations:

```bash
python manage.py makemigrations purchasing
python manage.py migrate purchasing
```

Migration file: `purchasing/migrations/0019_alter_purchase_options_alter_purchaseorder_options.py`

---

## Assigning Permissions

### Via Django Admin

1. Go to **Admin** → **Groups**
2. Create/Edit group (e.g., "Marketing", "Warehouse", "Finance")
3. Select permissions:
   - **Marketing Group:**
     - `purchasing | purchase order | Can view Purchase Order`
     - `purchasing | purchase order | Can create/edit Purchase Order (Marketing)`
   
   - **Warehouse Group:**
     - `purchasing | purchase | Can view Purchase`
     - `purchasing | purchase | Can create/edit/receive Purchase (Warehouse)`
   
   - **Finance Group:**
     - `purchasing | purchase | Can view Purchase`
     - `purchasing | purchase | Can verify/payment/tax invoice Purchase (Finance)`

4. Assign users to groups

### Via Python Shell

```python
from django.contrib.auth.models import User, Group, Permission

# Get permissions
po_view = Permission.objects.get(codename='po_view', content_type__app_label='purchasing')
po_marketing = Permission.objects.get(codename='po_marketing', content_type__app_label='purchasing')
purchase_view = Permission.objects.get(codename='purchase_view', content_type__app_label='purchasing')
purchase_warehouse = Permission.objects.get(codename='purchase_warehouse', content_type__app_label='purchasing')
purchase_finance = Permission.objects.get(codename='purchase_finance', content_type__app_label='purchasing')

# Create groups
marketing_group = Group.objects.create(name='Marketing')
warehouse_group = Group.objects.create(name='Warehouse')
finance_group = Group.objects.create(name='Finance')

# Assign permissions
marketing_group.permissions.add(po_view, po_marketing)
warehouse_group.permissions.add(purchase_view, purchase_warehouse)
finance_group.permissions.add(purchase_view, purchase_finance)

# Assign users
user1 = User.objects.get(username='marketing_user')
user2 = User.objects.get(username='warehouse_user')
user3 = User.objects.get(username='finance_user')

user1.groups.add(marketing_group)
user2.groups.add(warehouse_group)
user3.groups.add(finance_group)
```

---

## Testing

### Test Permission Access

```python
# Test PO View
user.has_perm('purchasing.po_view')  # True/False

# Test PO Marketing
user.has_perm('purchasing.po_marketing')  # True/False

# Test Purchase View
user.has_perm('purchasing.purchase_view')  # True/False

# Test Purchase Warehouse
user.has_perm('purchasing.purchase_warehouse')  # True/False

# Test Purchase Finance
user.has_perm('purchasing.purchase_finance')  # True/False
```

---

## Summary

✅ **5 Permissions Created:**
1. `purchasing.po_view` - View PO
2. `purchasing.po_marketing` - Create/Edit PO
3. `purchasing.purchase_view` - View Purchase
4. `purchasing.purchase_warehouse` - Create/Edit/Receive/Delete Purchase
5. `purchasing.purchase_finance` - Verify/Payment/Tax Invoice

✅ **Views Protected:**
- All PO views (list, detail, create, edit)
- All Purchase views (list, detail, create, edit, receive, verify, delete)

✅ **Templates Updated:**
- Base template (menu visibility)
- Purchase list template (button visibility)
- Mobile purchase list template (button visibility)

✅ **Context Processor:**
- `purchasing_permissions` added to provide permissions to all templates

✅ **Migration Applied:**
- `0019_alter_purchase_options_alter_purchaseorder_options.py`

---

## Next Steps

1. ✅ Create permissions in models
2. ✅ Add permission checks in views
3. ✅ Update templates to use permissions
4. ✅ Create context processor
5. ✅ Run migrations
6. 🔄 Assign permissions to groups/users (via Django Admin)
7. 🔄 Test with different user roles

---

**Documentation Created:** 2025-01-20
**Last Updated:** 2025-01-20




