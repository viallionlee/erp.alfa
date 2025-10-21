# Sistem Draft - Purchase Order & Purchase

## Konsep Dasar

Sistem draft memungkinkan user untuk membuat dan menyimpan draft Purchase Order (PO) dan Purchase di database, bukan di localStorage. 

**Fitur Auto-Save:**
- Setiap perubahan **langsung tersimpan otomatis** ke database (2 detik setelah perubahan terakhir)
- Tidak perlu klik "Simpan" untuk menyimpan perubahan
- Tombol "Simpan" hanya untuk **mengubah status** dari 'draft' ke 'pending' (menandakan sudah sah/final)
- Auto-save berlaku untuk **create** dan **edit** draft/pending

## Status Flow

### Purchase Order (PO)
```
1. Buat PO → status = 'draft'
2. Simpan PO → status = 'pending'
3. Buat Purchase dari PO → status = 'received'
4. Cancel PO → status = 'cancelled' (hanya untuk pending)
5. Hapus Draft → delete dari database (hanya untuk draft)
```

### Purchase (Goods Receipt)
```
1. Buat Purchase → status = 'draft'
2. Simpan Purchase → status = 'pending'
3. Receive Purchase → status = 'received' + update stock + trigger putaway
4. Cancel Purchase → status = 'cancelled' (hanya untuk pending)
5. Hapus Draft → delete dari database (hanya untuk draft)
```

## Implementasi

### 1. Model Changes

**File:** `purchasing/models.py`

```python
class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

class Purchase(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
```

### 2. View Logic

#### Create View (PO & Purchase)

**GET Request:**
- Create draft baru di database dengan status='draft'
- Pass draft object ke template
- Form langsung terbuka tanpa modal

**POST Request:**
- Get po_id/purchase_id dari form
- Get existing draft dari database
- Update draft dengan data baru
- Change status dari 'draft' ke 'pending'
- Delete old items, create new items

**File:** `purchasing/views.py`

```python
@login_required
def po_create(request):
    if request.method == 'POST':
        po_id = request.POST.get('po_id')
        po = get_object_or_404(PurchaseOrder, id=po_id, status='draft')
        
        # Update PO
        po.nomor_po = request.POST.get('nomor_po')
        po.supplier_id = request.POST.get('supplier_id')
        po.status = 'pending'  # Change status
        po.save()
        
        # Delete old items, create new items
        po.items.all().delete()
        for sku, qty, harga in zip(...):
            PurchaseOrderItem.objects.create(...)
        
        return redirect('purchasing:po_detail', pk=po.pk)
    
    # GET request - Create new draft
    draft_po = PurchaseOrder.objects.create(
        nomor_po=f"PO/{...}",
        supplier=Supplier.objects.first(),
        created_by=request.user,
        status='draft',
    )
    
    return render(request, 'purchasing/po_create.html', {'po': draft_po})
```

#### Cancel View (PO & Purchase)

**Logic:**
- Jika status = 'draft' → delete dari database
- Jika status = 'pending' → ubah status ke 'cancelled'
- Jika status = 'received' → tidak bisa dicancel

```python
@login_required
def po_cancel(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    
    if po.status == 'draft':
        po.delete()
        messages.success(request, f'Draft {po.nomor_po} berhasil dihapus!')
        return redirect('purchasing:po_list')
    
    if request.method == 'POST':
        po.status = 'cancelled'
        po.save()
        messages.success(request, f'PO {po.nomor_po} berhasil dibatalkan.')
    
    return redirect('purchasing:po_list')
```

#### Receive View (Purchase only)

**Logic:**
- Draft tidak bisa di-receive
- Update status ke 'received'
- Update stock (quantity, quantity_ready, quantity_putaway)
- Trigger putaway slotting recommendation

```python
@login_required
def purchase_receive(request, purchase_id):
    purchase = get_object_or_404(Purchase, id=purchase_id)
    
    if purchase.status == 'draft':
        messages.error(request, 'Draft tidak bisa di-receive!')
        return redirect('purchasing:purchase_list')
    
    if request.method == 'POST':
        purchase.status = 'received'
        purchase.tanggal_received = timezone.now()
        purchase.received_by = request.user
        purchase.save()
        
        # Update stock for each item
        for item in purchase.items.all():
            stock = item.product.stock_set.first()
            if not stock:
                stock = Stock.objects.create(...)
            
            stock.quantity += item.quantity
            stock.quantity_ready += item.quantity
            stock.quantity_putaway += item.quantity  # Stock siap untuk putaway
            stock.save()
            
            # Trigger auto putaway slotting
            PutawayService.create_slotting_recommendation(
                product=item.product,
                quantity=item.quantity,
                user=request.user,
                source_type='purchase',
                source_id=purchase.id
            )
        
        messages.success(request, f'Purchase {purchase.nomor_purchase} berhasil diterima!')
        return redirect('purchasing:purchase_detail', purchase_id=purchase.id)
    
    return redirect('purchasing:purchase_list')
```

### 3. Template Changes

#### Form Template (po_create.html, purchase_create.html)

**Hidden Input:**
```html
<form method="post" id="add-po-form">
    {% csrf_token %}
    <input type="hidden" name="po_id" value="{{ po.id }}">
    <!-- atau untuk purchase -->
    <input type="hidden" name="purchase_id" value="{{ draft_purchase.id }}">
    ...
</form>
```

**Title:**
```html
<h5 class="mb-0">Buat Purchase Order</h5>
<!-- atau untuk edit -->
<h5 class="mb-0">Edit Purchase Order: {{ po.nomor_po }}</h5>
```

**Submit Button:**
```html
<button type="submit" class="btn btn-success">
    <i class="bi bi-save"></i> Simpan Purchase Order
</button>
```

### 4. List View Changes

#### PO List (po_list.html)

**Tombol Aksi:**
- **Draft:** Detail, Edit, Hapus, Print
- **Pending:** Detail, Print
- **Received:** Detail, Print
- **Cancelled:** Detail, Print

#### Purchase List (purchase_list.html)

**Tombol Aksi:**
- **Draft:** Detail, Edit, Hapus
- **Pending:** Detail, Edit, Receive, Cancel
- **Received:** Detail
- **Cancelled:** Detail

**File:** `purchasing/views.py` (po_data API)

```python
if po.status == 'draft':
    aksi_html += f'<a href="/purchasing/{po.id}/edit/" class="btn btn-sm btn-warning"><i class="bi bi-pencil"></i> Edit</a> '
    aksi_html += f'<a href="/purchasing/{po.id}/cancel/" class="btn btn-sm btn-danger" onclick="return confirm(\'Yakin ingin menghapus draft ini?\')"><i class="bi bi-trash"></i> Hapus</a> '
```

## Auto-Save Implementation

### 1. Auto-Save saat Create

**Flow:**
```
1. User klik "Buat PO/Purchase" → create draft di database (status='draft')
2. User isi form → auto-save setiap 2 detik
3. User tambah produk → auto-save
4. User ubah qty/harga → auto-save
5. User klik "Simpan" → ubah status ke 'pending' (final)
```

**Endpoint:**
- PO: `/purchasing/<pk>/auto-save/`
- Purchase: `/purchasing/purchase/<purchase_id>/auto-save/`

### 2. Auto-Save saat Edit

**Flow:**
```
1. User klik "Edit" draft/pending → buka form
2. User ubah data → auto-save setiap 2 detik
3. User tambah/kurang produk → auto-save
4. User ubah qty/harga → auto-save
5. User klik "Simpan" → ubah status ke 'pending' (final)
```

**Endpoint:**
- PO: `/purchasing/<pk>/auto-save/`
- Purchase: `/purchasing/purchase/<purchase_id>/auto-save/`

### 3. JavaScript Auto-Save Logic

**Debounce:**
- Tunggu 2 detik setelah perubahan terakhir
- Prevent multiple simultaneous saves

**Triggers:**
- Input/textarea/select berubah
- Produk ditambah/dihapus
- Qty/harga berubah

**Indicator:**
- Tampilkan "Saved" di pojok kanan atas
- Hilang setelah 2 detik

**Code Example:**
```javascript
// Auto-save functionality
let autoSaveTimeout;
let isAutoSaving = false;

function autoSave() {
    if (isAutoSaving) return;
    
    clearTimeout(autoSaveTimeout);
    autoSaveTimeout = setTimeout(function() {
        isAutoSaving = true;
        
        // Serialize form data
        const formData = $('#add-po-form').serialize();
        
        // Send AJAX request
        $.ajax({
            url: '/purchasing/{{ po.id }}/auto-save/',
            type: 'POST',
            data: formData,
            success: function(response) {
                if (response.success) {
                    console.log('✅ Auto-saved:', response.message);
                    showAutoSaveIndicator('Saved');
                }
            },
            complete: function() {
                isAutoSaving = false;
            }
        });
    }, 2000); // Wait 2 seconds after last change
}

// Trigger auto-save on input changes
$('#add-po-form input, #add-po-form textarea, #add-po-form select').on('input change', function() {
    autoSave();
});
```

### 4. Backend Auto-Save Logic

**Validation:**
- Hanya draft dan pending yang bisa di-auto-save
- Received dan cancelled tidak bisa di-edit

**Update Logic:**
- Update PO/Purchase fields
- Update existing items (quantity, harga_beli)
- Create new items
- Delete removed items

**Code Example:**
```python
@login_required
def po_auto_save(request, pk):
    """Auto-save PO changes via AJAX"""
    po = get_object_or_404(PurchaseOrder, pk=pk)
    
    # Only allow auto-save for draft and pending status
    if po.status not in ['draft', 'pending']:
        return JsonResponse({'success': False, 'error': 'Cannot auto-save received or cancelled PO'})
    
    with transaction.atomic():
        # Update PO fields
        po.nomor_po = request.POST.get('nomor_po', po.nomor_po)
        po.supplier_id = request.POST.get('supplier_id', po.supplier_id)
        po.tanggal_po = request.POST.get('tanggal_po', po.tanggal_po)
        po.notes = request.POST.get('notes', po.notes)
        po.save()
        
        # Update items (smart update: create/update/delete)
        # ... (see full implementation in purchasing/views.py)
        
        return JsonResponse({'success': True, 'message': 'PO berhasil disimpan otomatis'})
```

## Keuntungan Sistem Draft

1. **Multiple Drafts:** User bisa membuat banyak draft sekaligus
2. **Database Storage:** Draft tersimpan di database, tidak hilang saat browser ditutup
3. **No localStorage:** Tidak perlu manage localStorage, lebih reliable
4. **Auto-save:** Setiap perubahan langsung tersimpan ke database (2 detik debounce)
5. **No Manual Save:** User tidak perlu klik "Simpan" untuk save perubahan
6. **Status Management:** Tombol "Simpan" hanya untuk mengubah status (draft → pending)
7. **Consistent:** Logic sama antara PO dan Purchase

## Perbedaan dengan Sistem Lama

| Aspek | Sistem Lama (localStorage) | Sistem Baru (Database) |
|-------|---------------------------|------------------------|
| Storage | localStorage browser | Database Django |
| Multiple Drafts | ❌ Hanya 1 draft | ✅ Bisa banyak draft |
| Persistence | ❌ Hilang saat clear cache | ✅ Permanen di database |
| Auto-save | ❌ Manual save ke localStorage | ✅ Auto-save ke database (2 detik debounce) |
| Manual Save | ✅ Wajib klik "Simpan" | ❌ Tidak perlu, auto-save |
| Tombol "Simpan" | Untuk save perubahan | Untuk ubah status (draft → pending) |
| Modal | ✅ Ada modal pilih draft | ❌ Tidak ada modal |
| Edit Draft | ❌ Tidak ada | ✅ Bisa edit draft |
| Auto-save saat Create | ❌ Tidak ada | ✅ Auto-save setiap 2 detik |
| Auto-save saat Edit | ❌ Tidak ada | ✅ Auto-save setiap 2 detik |

## Testing Checklist

### Create & Auto-Save
- [ ] Buat PO → draft terbuat di database (status='draft')
- [ ] Isi form PO → auto-save setelah 2 detik
- [ ] Tambah produk PO → auto-save
- [ ] Ubah qty/harga PO → auto-save
- [ ] Indicator "Saved" muncul → hilang setelah 2 detik
- [ ] Buat Purchase → draft terbuat di database (status='draft')
- [ ] Isi form Purchase → auto-save setelah 2 detik
- [ ] Tambah produk Purchase → auto-save
- [ ] Ubah qty/harga Purchase → auto-save

### Edit & Auto-Save
- [ ] Edit PO draft → buka form
- [ ] Ubah data PO → auto-save setelah 2 detik
- [ ] Tambah/kurang produk PO → auto-save
- [ ] Ubah qty/harga PO → auto-save
- [ ] Edit Purchase draft → buka form
- [ ] Ubah data Purchase → auto-save setelah 2 detik
- [ ] Tambah/kurang produk Purchase → auto-save
- [ ] Ubah qty/harga Purchase → auto-save

### Status Management
- [ ] Simpan PO → status berubah ke 'pending'
- [ ] Simpan Purchase → status berubah ke 'pending'
- [ ] Receive Purchase → status 'received', stock terupdate, putaway ter-trigger

### Delete & Cancel
- [ ] Hapus PO draft → draft terhapus dari database
- [ ] Hapus Purchase draft → draft terhapus dari database
- [ ] Cancel PO pending → status berubah ke 'cancelled'
- [ ] Cancel Purchase pending → status berubah ke 'cancelled'

### Multiple Drafts
- [ ] Buat banyak PO draft → semua tersimpan
- [ ] Buat banyak Purchase draft → semua tersimpan
- [ ] Edit draft mana saja → auto-save draft tersebut

## Notes untuk AI

### Auto-Save Rules
1. **Auto-save WAJIB** saat create dan edit draft/pending
2. **Debounce 2 detik** - tunggu 2 detik setelah perubahan terakhir
3. **AJAX endpoint** - `/purchasing/<pk>/auto-save/` dan `/purchasing/purchase/<purchase_id>/auto-save/`
4. **Indicator "Saved"** - tampilkan di pojok kanan atas, hilang setelah 2 detik
5. **Console log** - untuk debugging: "✅ Auto-saved" atau "❌ Auto-save failed"
6. **Hanya draft & pending** - received dan cancelled tidak bisa di-auto-save

### Draft Management
1. **Draft selalu dibuat saat GET request** di create view
2. **Draft selalu di-update otomatis** via auto-save (setiap 2 detik)
3. **Tombol "Simpan"** hanya untuk mengubah status dari 'draft' ke 'pending'
4. **Draft bisa di-hapus** hanya jika status = 'draft'
5. **Pending bisa di-cancel** hanya jika status = 'pending'
6. **Received tidak bisa di-edit/cancel** (final state)

### Purchase Receive
7. **Purchase receive trigger putaway** untuk auto-assign rak
8. **Stock update** saat receive: quantity, quantity_ready, quantity_putaway

### Storage & UI
9. **No localStorage** - semua di database
10. **No modal** - form langsung terbuka
11. **Multiple drafts** - user bisa buat banyak draft sekaligus
12. **Auto-save saat create** - user tidak perlu klik "Simpan" untuk save perubahan
13. **Auto-save saat edit** - user tidak perlu klik "Simpan" untuk save perubahan
14. **Tombol "Simpan"** - hanya untuk finalisasi (ubah status draft → pending)

