# SLOTTING RULES & LOGIC - UPDATED VERSION

## IMPORTANT: SLOTTING IS RECOMMENDATION ONLY
- Auto slotting dan manual slotting bersifat **REKOMENDASI**
- User tetap bisa memilih rak lain jika diperlukan
- Tidak ada paksaan untuk mengikuti rekomendasi
- Tujuan: Memberikan informasi rak mana yang bisa menampung produk

## CAPACITY VALIDATION RULES

### 1. AVAILABLE SLOTS CALCULATION
- **Available slots** = `int(rak.available_front / product.lebar_cm)`
- Jika `available_slots = 0` → **HILANGKAN** dari filter rak
- Available slots menentukan berapa slot kosong yang tersedia

### 2. RAK BARU (belum ada produk yang sama)
- Hitung `available_slots = int(available_front / product_width)`
- Hitung `slots_needed = ceil(quantity / products_per_slot)`
- **Validasi**: `available_slots >= slots_needed`
- Jika tidak cukup → masuk ke "Kapasitas Tidak Cukup"

### 3. RAK SAME (sudah ada produk yang sama)
- Hitung `current_slots_used = slots` untuk existing_stock
- Hitung `total_slots_available = int(rak_width / product_width)`
- Hitung `remaining_slots = total_slots_available - current_slots_used`
- Hitung `remaining_capacity = remaining_slots * products_per_slot`
- **Validasi**: `quantity <= remaining_capacity`
- **KUNCI**: Meskipun `available_slots = 0`, jika `remaining_capacity >= quantity` → **BISA MASUK**

### 4. PRIORITY SORTING
```
Priority 1: SAME_PRODUCT_EXISTS (bonus 1000)
Priority 2: CAPACITY (higher capacity gets higher priority)
Priority 3: LOCATION (DEKAT > SEDANG > JAUH > BEDA_GUDANG)
```

### 5. FILTER CATEGORIES
- **"Kapasitas Cukup"**: `capacity_valid = true`
- **"Kapasitas Tidak Cukup"**: `capacity_valid = false`
- **"Rak yang Sama"**: `has_same_product = true`

## EXAMPLE SCENARIOS

### Scenario 1: Rak A2 dengan produk ABC
```
- Existing: 35pcs, 1 slot muat 40pcs
- Available slots = 0 (tidak ada tempat kosong)
- Remaining capacity = 28pcs (40-12 = 28)
- Quantity putaway: 20pcs
- Result: BISA MASUK karena 28 > 20
```

### Scenario 2: Rak baru dengan available_front = 10cm
```
- Product width = 5cm
- Available slots = int(10/5) = 2 slots
- Products per slot = 40
- Quantity putaway: 50pcs
- Slots needed = ceil(50/40) = 2 slots
- Result: BISA MASUK karena 2 >= 2
```

## IMPLEMENTATION DETAILS

### Backend Logic (`inventory/putaway.py`)
```python
# RAK SAME
if existing_stock:
    current_slots_used = _calculate_width_slots_needed_for_product(rak, product, current_quantity)
    total_slots_available = int(rak_width / product_width)
    remaining_slots = max(0, total_slots_available - current_slots_used)
    remaining_capacity = remaining_slots * products_per_slot
    available_slots = remaining_slots

# RAK BARU
else:
    available_slots = int(capacity.available_front / product_width)
    remaining_capacity = available_slots * products_per_slot

# VALIDASI
if existing_stock:
    capacity_valid = quantity <= remaining_capacity
else:
    slots_needed = _calculate_width_slots_needed_for_product(rak, product, quantity)
    capacity_valid = available_slots >= slots_needed
```

### Frontend Logic (`templates/inventory/putaway.html`)
```javascript
// Gunakan validasi kapasitas dari backend
if (rak.available_front > 0 && rak.fit_score > 0 && rak.capacity_valid) {
    rakCukup.push(rak);
} else {
    rakTidakCukup.push(rak);
}
```

### API Endpoint (`inventory/views.py`)
```python
def slotting_options(request):
    sku = request.GET.get('sku')
    quantity = request.GET.get('quantity')  # Quantity untuk validasi
    
    rak_options_result = SlottingService.get_rak_options(product, quantity_int)
```

## DISPLAY INFORMATION

### Rak yang Sudah Ada Produk yang Sama
```
🔥 SAME
Sudah ada: 35 pcs
Bisa tambah: 28 pcs
Available slots: 1 slots
```

### Rak Baru
```
Available: 10.0cm
Used: 90.0cm
Fit: 10.0%
Slots: 2 slots
```

## FUTURE ENHANCEMENTS
- ✅ **Slotting by Location** (IMPLEMENTED) - Priority: DEKAT(4) > SEDANG(3) > JAUH(2) > BEDA_GUDANG(1)
- **Slotting by Sales** (Priority: High) 
- **Slotting by Brand** (Priority: Medium)
- **Slotting by Seasonality** (Priority: Medium)
- **Slotting by Weight** (Priority: Low)
- **Slotting by Expiry Date** (Priority: Low)

## KEY POINTS TO REMEMBER

1. **Rak SAME bisa masuk meskipun available_slots = 0** jika remaining_capacity cukup
2. **Validasi kapasitas dilakukan di backend** untuk akurasi
3. **Quantity dikirim ke backend** untuk validasi yang tepat
4. **Sorting berdasarkan SAME > CAPACITY > LOCATION**
5. **Icon detail tersedia** untuk melihat produk di dalam rak
6. **Slotting bersifat rekomendasi**, user bisa override
