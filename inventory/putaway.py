"""
Putaway Service - Centralized logic for putaway and slotting operations
Handles all putaway types: regular, transfer, and return putaway

SLOTTING RECOMMENDATION SYSTEM:
===============================
Slotting auto dan manual saat ini bersifat REKOMENDASI, bukan paksaan.
Hanya menginformasikan rak mana yang bisa menampung produk.

FITUR SLOTTING REKOMENDASI YANG AKAN DIKEMBANGKAN:
==================================================
1. SLOTTING BY LOCATION
   - Rekomendasi rak berdasarkan lokasi/area
   - Contoh: produk A di area FMCG, produk B di area Electronics
   - Priority: Tinggi

2. SLOTTING BY SALES
   - Rekomendasi rak berdasarkan data penjualan
   - Produk fast-moving di rak yang mudah diakses
   - Produk slow-moving di rak yang lebih jauh
   - Priority: Tinggi

3. SLOTTING BY BRAND
   - Rekomendasi rak berdasarkan brand
   - Brand tertentu di rak tertentu untuk kemudahan picking
   - Priority: Sedang

4. SLOTTING BY SEASONALITY
   - Rekomendasi rak berdasarkan musim/trend
   - Produk musiman di rak yang mudah diakses
   - Priority: Sedang

5. SLOTTING BY WEIGHT
   - Rekomendasi rak berdasarkan berat produk
   - Produk berat di rak bawah, ringan di rak atas
   - Priority: Rendah

6. SLOTTING BY EXPIRY DATE
   - Rekomendasi rak berdasarkan tanggal kadaluarsa
   - FIFO (First In First Out) untuk produk dengan expiry
   - Priority: Rendah

IMPLEMENTATION NOTES:
====================
- Semua slotting tetap bersifat rekomendasi
- User tetap bisa memilih rak lain jika diperlukan
- Fit score akan dikombinasikan dengan faktor rekomendasi
- Log slotting akan mencatat alasan rekomendasi
"""

import logging
from django.db import transaction
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from django.http import JsonResponse

from .models import (
    Stock, Rak, InventoryRakStock, InventoryRakStockLog, 
    StockCardEntry, PutawaySlottingLog, RakTransferSession, RakTransferItem
)
from products.models import Product
from .rakcapacity import _calculate_width_slots_needed_for_product, _calculate_products_per_slot

logger = logging.getLogger(__name__)


class PutawayService:
    """
    Centralized service for all putaway operations
    """
    
    @staticmethod
    def process_putaway(request, rak_id, items_to_putaway, putaway_type='regular', **kwargs):
        """
        Main putaway processing method for all putaway types
        
        Args:
            request: Django request object
            rak_id: Target rack ID
            items_to_putaway: List of dicts with product_id and quantity
            putaway_type: 'regular', 'transfer', or 'return'
            **kwargs: Additional parameters (session_id, etc.)
            
        NOTE: Return putaway type tidak lagi digunakan karena return process sudah menambah stock.
        Return items harus menggunakan regular putaway untuk dipindahkan ke rak.
        """
        try:
            rak = get_object_or_404(Rak, id=rak_id)
            logger.info(f"Processing {putaway_type} putaway to rak {rak.kode_rak}")
            
            with transaction.atomic():
                processed_items = []
                
                for item_data in items_to_putaway:
                    product_id = item_data.get('product_id')
                    quantity = int(item_data.get('quantity', 0))
                    
                    if not product_id or quantity <= 0:
                        continue
                    
                    product = get_object_or_404(Product, id=product_id)
                    
                    # Process individual item putaway
                    result = PutawayService._process_item_putaway(
                        product=product,
                        rak=rak,
                        quantity=quantity,
                        user=request.user,
                        putaway_type=putaway_type,
                        **kwargs
                    )
                    
                    if result['success']:
                        processed_items.append(result)
                    else:
                        raise ValueError(result['error'])
                
                # Handle session completion for transfer putaway
                if putaway_type == 'transfer' and kwargs.get('session_id'):
                    PutawayService._complete_transfer_session(kwargs['session_id'], request.user)
                
                return {
                    'success': True,
                    'message': f'{putaway_type.title()} putaway berhasil! {len(processed_items)} item diproses.',
                    'processed_items': processed_items
                }
                
        except Exception as e:
            logger.error(f"Error in putaway processing: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _process_item_putaway(product, rak, quantity, user, putaway_type='regular', **kwargs):
        """
        Process individual item putaway
        
        NOTE: Return putaway type tidak lagi digunakan karena return process sudah menambah stock.
        Return items harus menggunakan regular putaway untuk dipindahkan ke rak.
        """
        try:
            # Get or create stock
            stock, created = Stock.objects.get_or_create(
                product=product,
                defaults={'quantity_putaway': 0, 'quantity': 0}
            )
            
            # Validate quantity for regular putaway
            if putaway_type == 'regular':
                if stock.quantity_putaway < quantity:
                    return {
                        'success': False,
                        'error': f'Quantity putaway ({quantity}) melebihi stok yang tersedia ({stock.quantity_putaway}) untuk {product.sku}'
                    }
            
            # Calculate quantities for logging (hanya untuk InventoryRakStockLog)
            qty_awal_putaway = stock.quantity_putaway
            
            # Update stock based on putaway type
            if putaway_type == 'regular':
                # Regular putaway: hanya kurangi quantity_putaway
                stock.quantity_putaway -= quantity
            elif putaway_type == 'transfer':
                # Transfer putaway: sudah dipindahkan saat transfer, tidak perlu update stock
                pass  # Quantity already moved during transfer
            elif putaway_type == 'return':
                # Return putaway: TIDAK update stock karena sudah diupdate saat return process
                # Return process sudah menambah Stock.quantity dan Stock.quantity_putaway
                # Return items harus menggunakan regular putaway untuk dipindahkan ke rak
                pass
            
            stock.save()
            
            # Update inventory rak stock (for all types except return)
            if putaway_type != 'return':
                inventory_rak_stock, created = InventoryRakStock.objects.get_or_create(
                    product=product,
                    rak=rak,
                    defaults={'quantity': 0}
                )
                
                qty_awal_rak = inventory_rak_stock.quantity
                inventory_rak_stock.quantity += quantity
                inventory_rak_stock.save()
                
                # Create inventory rak stock log
                PutawayService._create_inventory_rak_log(
                    product=product,
                    rak=rak,
                    quantity=quantity,
                    qty_awal=qty_awal_rak,
                    qty_akhir=inventory_rak_stock.quantity,
                    user=user,
                    putaway_type=putaway_type,
                    **kwargs
                )
            
            # Update PutawaySlottingLog saat scan putaway
            if putaway_type == 'regular':
                # Cari slotting log terbaru untuk product ini
                slotting_log = PutawaySlottingLog.objects.filter(
                    product=product,
                    suggested_rak=rak,
                    putaway_by__isnull=True  # Belum di-scan putaway
                ).order_by('-created_at').first()
                
                if slotting_log:
                    # Update slotting log dengan data scan putaway
                    slotting_log.putaway_by = user
                    slotting_log.putaway_time = timezone.now()
                    slotting_log.quantity = quantity
                    slotting_log.save()
            
            # StockCardEntry tidak dibuat untuk putaway
            # Putaway hanya mengupdate InventoryRakStock dan InventoryRakStockLog
            
            return {
                'success': True,
                'product_id': product.id,
                'product_sku': product.sku,
                'quantity': quantity,
                'rak_code': rak.kode_rak
            }
            
        except Exception as e:
            logger.error(f"Error processing item putaway: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _create_inventory_rak_log(product, rak, quantity, qty_awal, qty_akhir, user, putaway_type, **kwargs):
        """
        Create inventory rak stock log
        
        NOTE: Return putaway type tidak lagi digunakan karena return process sudah menambah stock.
        Return items harus menggunakan regular putaway untuk dipindahkan ke rak.
        """
        tipe_pergerakan_map = {
            'regular': 'putaway_masuk',
            'transfer': 'transfer_putaway',
            'return': 'return_putaway'
        }
        
        catatan_map = {
            'regular': f'Putaway {quantity} unit {product.nama_produk} ke rak {rak.kode_rak}',
            'transfer': f'Transfer Putaway {quantity} unit dari {kwargs.get("source_rak", "Unknown")} ke {rak.kode_rak}',
            'return': f'Return Putaway {quantity} unit ke rak {rak.kode_rak}'
        }
        
        InventoryRakStockLog.objects.create(
            produk=product,
            rak=rak,
            tipe_pergerakan=tipe_pergerakan_map.get(putaway_type, 'putaway_masuk'),
            qty=quantity,
            qty_awal=qty_awal,
            qty_akhir=qty_akhir,
            user=user,
            waktu_buat=timezone.now(),
            catatan=catatan_map.get(putaway_type, f'Putaway {quantity} unit ke {rak.kode_rak}'),
        )
    
    @staticmethod
    def _create_stock_card_entry(product, quantity, qty_awal_stock, qty_akhir_stock, 
                                qty_awal_putaway, qty_akhir_putaway, user, putaway_type, rak, **kwargs):
        """
        Create stock card entry
        NOTE: Method ini TIDAK digunakan untuk putaway
        Putaway tidak mengupdate StockCardEntry
        Return putaway juga TIDAK membuat StockCardEntry karena sudah dibuat saat return process
        """
        tipe_pergerakan_map = {
            'regular': 'putaway_selesai',
            'transfer': 'transfer_putaway',
            'return': 'return_putaway'  # TIDAK DIGUNAKAN - Return items harus menggunakan regular putaway
        }
        
        notes_map = {
            'regular': f'Putaway {quantity} unit {product.nama_produk} ke rak {rak.kode_rak}. Stok siap jual bertambah.',
            'transfer': f'Transfer Putaway {quantity} unit ke rak {rak.kode_rak}. Stok siap jual bertambah.',
            'return': f'Return Putaway {quantity} unit ke rak {rak.kode_rak}. (TIDAK DIGUNAKAN - Return items harus menggunakan regular putaway)'
        }
        
        product_content_type = ContentType.objects.get_for_model(product)
        
        StockCardEntry.objects.create(
            product=product,
            qty=quantity,
            tipe_pergerakan=tipe_pergerakan_map.get(putaway_type, 'putaway_selesai'),
            user=user,
            waktu=timezone.now(),
            notes=notes_map.get(putaway_type, f'Putaway {quantity} unit ke {rak.kode_rak}'),
            content_type=product_content_type,
            object_id=product.id,
            qty_awal=qty_awal_stock,
            qty_akhir=qty_akhir_stock,
        )
    
    @staticmethod
    def _complete_transfer_session(session_id, user):
        """Complete transfer session after putaway"""
        try:
            transfer_session = RakTransferSession.objects.select_for_update().get(id=session_id)
            transfer_session.status = 'selesai'
            transfer_session.tanggal_selesai = timezone.now()
            transfer_session.completed_by = user
            transfer_session.save()
            logger.info(f"Transfer session {session_id} marked as completed")
        except Exception as e:
            logger.error(f"Error completing transfer session: {e}")


class SlottingService:
    """
    Centralized service for slotting operations
    Uses rak capacity logic for intelligent rack selection
    
    IMPORTANT: SLOTTING IS RECOMMENDATION ONLY
    ===========================================
    - Auto slotting dan manual slotting bersifat REKOMENDASI
    - User tetap bisa memilih rak lain jika diperlukan
    - Tidak ada paksaan untuk mengikuti rekomendasi
    - Tujuan: Memberikan informasi rak mana yang bisa menampung produk
    
    FUTURE ENHANCEMENTS:
    ====================
    - ✅ Slotting by Location (IMPLEMENTED) - Priority: DEKAT(4) > SEDANG(3) > JAUH(2) > BEDA_GUDANG(1)
    - Slotting by Sales (Priority: High) 
    - Slotting by Brand (Priority: Medium)
    - Slotting by Seasonality (Priority: Medium)
    - Slotting by Weight (Priority: Low)
    - Slotting by Expiry Date (Priority: Low)
    """
    
    @staticmethod
    def get_rak_options(product, quantity=None):
        """
        Get rak options for slotting with capacity validation
        
        Args:
            product: Product object
            quantity: Quantity to putaway (optional, for capacity validation)
            
        Returns:
            Dict with success status and rak options
        """
        try:
            if not (product.lebar_cm and product.panjang_cm and product.tinggi_cm):
                return {
                    'success': False,
                    'error': 'Produk tidak memiliki dimensi lengkap'
                }
            
            # Get all racks with capacity data
            from .models import RakCapacity
            rak_capacities = RakCapacity.objects.select_related('rak').all().order_by('-available_front')
            
            options = []
            for capacity in rak_capacities:
                rak = capacity.rak
                
                # Check if rak has dimensions
                if not (rak.lebar_cm and rak.panjang_cm and rak.tinggi_cm):
                    continue
                
                # Calculate if product can fit
                can_fit = SlottingService._can_product_fit_in_rak(product, rak)
                
                if can_fit['can_fit']:
                    # Calculate products per slot dengan hybrid stacking
                    products_per_slot = SlottingService._calculate_hybrid_products_per_slot(rak, product)
                    
                    # Hanya tampilkan rak yang bisa menampung minimal 1 produk
                    if products_per_slot > 0:
                        # Hitung stackable berdasarkan tinggi
                        stackable_height = SlottingService._calculate_stackable_height(product, rak, can_fit.get('orientation_used', 'normal'))
                        
                        # Hitung cara stacking
                        stacking_method = SlottingService._calculate_stacking_method(product, rak, can_fit.get('orientation_used', 'normal'))
                        
                        # Check existing stock
                        from .models import InventoryRakStock
                        existing_stock = InventoryRakStock.objects.filter(
                            product=product,
                            rak=rak,
                            quantity__gt=0
                        ).first()
                        
                        # Calculate capacity info sesuai SLOTTINGRULES.md
                        available_slots = 0
                        remaining_capacity = 0
                        current_slots_used = 0
                        total_slots_available = 0
                        
                        product_width = float(product.lebar_cm)
                        rak_width = float(rak.lebar_cm)
                        
                        if existing_stock:
                            # RAK SAME (sudah ada produk yang sama)
                            current_quantity = existing_stock.quantity
                            from .rakcapacity import _calculate_width_slots_needed_for_product
                            
                            # Hitung berapa slot yang sudah terpakai
                            current_slots_used = _calculate_width_slots_needed_for_product(rak, product, current_quantity)
                            
                            # Hitung total slot yang tersedia untuk produk ini
                            total_slots_available = int(rak_width / product_width) if product_width > 0 else 0
                            
                            # Hitung berapa slot yang masih tersisa
                            remaining_slots = max(0, total_slots_available - current_slots_used)
                            
                            # Hitung berapa produk yang bisa ditambah
                            remaining_capacity = remaining_slots * products_per_slot
                            
                            # Available slots untuk rak SAME = remaining_slots
                            available_slots = remaining_slots
                        else:
                            # RAK BARU (belum ada produk yang sama)
                            # Hitung available slots berdasarkan available_front
                            if product_width > 0:
                                available_front_float = float(capacity.available_front)
                                available_slots = int(available_front_float / product_width)
                                remaining_capacity = available_slots * products_per_slot
                            else:
                                available_slots = 0
                                remaining_capacity = 0
                        
                        # Validasi kapasitas untuk quantity yang akan diputaway
                        capacity_valid = True
                        if quantity and quantity > 0:
                            if existing_stock:
                                # Untuk rak SAME: cek remaining_capacity
                                if quantity > remaining_capacity:
                                    capacity_valid = False
                            else:
                                # Untuk rak baru: cek available_slots
                                from .rakcapacity import _calculate_width_slots_needed_for_product
                                slots_needed = _calculate_width_slots_needed_for_product(rak, product, quantity)
                                if available_slots < slots_needed:
                                    capacity_valid = False
                        
                        options.append({
                            'rak_id': rak.id,
                            'kode_rak': rak.kode_rak,
                            'nama_rak': rak.nama_rak,
                            'lokasi': rak.lokasi,
                            'lokasi_priority': rak.lokasi_priority_score,
                            'lebar_cm': rak.lebar_cm,
                            'panjang_cm': rak.panjang_cm,
                            'tinggi_cm': rak.tinggi_cm,
                            'available_front': float(capacity.available_front),
                            'used_front': float(capacity.used_front),
                            'utilization': float(capacity.utilization_percentage),
                            'fit_score': can_fit['fit_score'],
                            'reason': can_fit['reason'],
                            'products_per_slot': products_per_slot,
                            'stackable_height': stackable_height,
                            'stacking_method': stacking_method,
                            'orientation_used': can_fit.get('orientation_used', 'normal'),
                            'supports_hybrid': can_fit.get('supports_hybrid', False),
                            'existing_stock': existing_stock.quantity if existing_stock else 0,
                            'available_slots': available_slots,
                            'remaining_capacity': remaining_capacity,
                            'current_slots_used': current_slots_used,
                            'total_slots_available': total_slots_available,
                            'has_same_product': existing_stock is not None,
                            'capacity_valid': capacity_valid
                        })
            
            # Sort by existing product priority first, then by capacity
            # Priority: SAME_PRODUCT_EXISTS > CAPACITY > LOCATION
            def sort_key(option):
                # Check if same product already exists in this rak
                same_product_bonus = 1000 if option['has_same_product'] else 0  # Highest priority
                
                # Capacity priority (higher capacity gets higher priority)
                capacity_priority = option['remaining_capacity'] if option['has_same_product'] else option['available_slots']
                
                # Location priority
                location_priority = option['lokasi_priority'] or 0
                
                # Combine priorities: same product (highest) > capacity > location
                return (same_product_bonus + capacity_priority + location_priority)
            
            options.sort(key=sort_key, reverse=True)
            
            return {
                'success': True,
                'product': {
                    'sku': product.sku,
                    'nama_produk': product.nama_produk,
                    'dimensi': f"{product.lebar_cm}cm x {product.panjang_cm}cm x {product.tinggi_cm}cm",
                    'posisi_tidur': product.posisi_tidur,
                    'supports_hybrid': product.posisi_tidur
                },
                'rak_options': options[:10]  # Return top 10 options
            }
            
        except Exception as e:
            logger.error(f"Error getting rak options: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _can_product_fit_in_rak(product, rak):
        """
        Check if product can fit in rak based on dimensions and capacity
        IMPLEMENTASI GREEDY HYBRID STACKING dengan posisi_tidur
        
        Returns:
            Dict with can_fit (bool), fit_score (float), and reason (str)
        """
        try:
            # Basic dimension check - mempertimbangkan orientasi produk
            product_width = float(product.lebar_cm)
            product_length = float(product.panjang_cm)
            product_height = float(product.tinggi_cm)
            
            rak_width = float(rak.lebar_cm)
            rak_length = float(rak.panjang_cm)
            rak_height = float(rak.tinggi_cm)
            
            # Cek apakah produk bisa masuk dengan orientasi normal
            fits_normal = (product_width <= rak_width and 
                          product_length <= rak_length and 
                          product_height <= rak_height)
            
            # Cek apakah produk bisa masuk dengan orientasi ditidurkan (tinggi jadi panjang)
            # Hanya jika produk mendukung posisi tidur
            fits_rotated = False
            if product.posisi_tidur:
                fits_rotated = (product_width <= rak_width and 
                               product_height <= rak_length and 
                               product_length <= rak_height)
            
            if not fits_normal and not fits_rotated:
                return {
                    'can_fit': False,
                    'fit_score': 0,
                    'reason': 'Produk terlalu besar untuk rak ini (semua orientasi)'
                }
            
            # Calculate products per slot dengan greedy hybrid stacking
            products_per_slot = SlottingService._calculate_hybrid_products_per_slot(rak, product)
            
            if products_per_slot <= 0:
                return {
                    'can_fit': False,
                    'fit_score': 0,
                    'reason': 'Produk tidak dapat masuk ke rak ini'
                }
            
            # Calculate fit score based on best orientation
            # Coba kedua orientasi dan ambil yang terbaik
            fit_scores = []
            
            # Orientasi normal
            if fits_normal:
                width_efficiency = product_width / rak_width
                length_efficiency = product_length / rak_length
                height_efficiency = product_height / rak_height
                normal_score = (width_efficiency + length_efficiency + height_efficiency) / 3
                fit_scores.append(normal_score)
            
            # Orientasi ditidurkan (hanya jika posisi_tidur = True)
            if fits_rotated and product.posisi_tidur:
                width_efficiency = product_width / rak_width
                length_efficiency = product_height / rak_length  # tinggi jadi panjang
                height_efficiency = product_length / rak_height  # panjang jadi tinggi
                rotated_score = (width_efficiency + length_efficiency + height_efficiency) / 3
                fit_scores.append(rotated_score)
            
            # Ambil score terbaik
            fit_score = max(fit_scores) if fit_scores else 0
            
            # Determine orientation used for best fit
            orientation_used = "normal"
            if fits_rotated and product.posisi_tidur and len(fit_scores) > 1:
                if fit_scores[1] > fit_scores[0]:  # rotated score better
                    orientation_used = "hybrid"
            
            return {
                'can_fit': True,
                'fit_score': fit_score,
                'reason': f'Dapat menampung {products_per_slot} produk per slot ({orientation_used} stacking)',
                'orientation_used': orientation_used,
                'supports_hybrid': product.posisi_tidur
            }
            
        except Exception as e:
            logger.error(f"Error checking product fit: {e}")
            return {
                'can_fit': False,
                'fit_score': 0,
                'reason': 'Error dalam perhitungan'
            }
    
    @staticmethod
    def _calculate_stackable_height(product, rak, orientation='normal'):
        """
        Hitung berapa produk yang bisa di-stack berdasarkan tinggi
        
        Args:
            product: Product object
            rak: Rak object
            orientation: 'normal' atau 'hybrid'
            
        Returns:
            int: Jumlah produk yang bisa di-stack berdasarkan tinggi
        """
        try:
            product_height = float(product.tinggi_cm)
            rak_height = float(rak.tinggi_cm)
            
            if orientation == 'hybrid' and product.posisi_tidur:
                # Jika hybrid, gunakan panjang produk sebagai tinggi
                product_height = float(product.panjang_cm)
            
            if product_height <= 0 or rak_height <= 0:
                return 1
            
            # Hitung berapa produk yang bisa di-stack
            stackable = int(rak_height / product_height)
            return max(1, stackable)  # Minimal 1
            
        except Exception as e:
            logger.error(f"Error calculating stackable height: {e}")
            return 1
    
    @staticmethod
    def _calculate_stacking_method(product, rak, orientation='normal'):
        """
        Hitung cara stacking yang optimal
        
        Args:
            product: Product object
            rak: Rak object
            orientation: 'normal' atau 'hybrid'
            
        Returns:
            dict: Informasi cara stacking
        """
        try:
            product_width = float(product.lebar_cm)
            product_length = float(product.panjang_cm)
            product_height = float(product.tinggi_cm)
            
            rak_width = float(rak.lebar_cm)
            rak_length = float(rak.panjang_cm)
            rak_height = float(rak.tinggi_cm)
            
            if orientation == 'normal':
                # Stacking normal: semua berdiri
                stackable_height = int(rak_height / product_height)
                stackable_width = int(rak_width / product_width)
                stackable_length = int(rak_length / product_length)
                
                return {
                    'method': 'normal',
                    'description': f'Level 1-{stackable_height} berdiri x {stackable_width * stackable_length} pcs',
                    'total_per_level': stackable_width * stackable_length,
                    'levels': stackable_height
                }
            
            elif orientation == 'hybrid' and product.posisi_tidur:
                # Hybrid stacking: kombinasi berdiri dan tidur
                # Hitung berapa yang bisa berdiri
                normal_height = int(rak_height / product_height)
                normal_width = int(rak_width / product_width)
                normal_length = int(rak_length / product_length)
                normal_per_level = normal_width * normal_length
                
                # Hitung berapa yang bisa tidur
                rotated_height = int(rak_height / product_length)  # panjang jadi tinggi
                rotated_width = int(rak_width / product_width)
                rotated_length = int(rak_length / product_height)  # tinggi jadi panjang
                rotated_per_level = rotated_width * rotated_length
                
                # Pilih kombinasi terbaik
                if normal_per_level >= rotated_per_level:
                    return {
                        'method': 'hybrid_normal',
                        'description': f'Level 1-{normal_height} berdiri x {normal_per_level} pcs',
                        'total_per_level': normal_per_level,
                        'levels': normal_height
                    }
                else:
                    return {
                        'method': 'hybrid_rotated',
                        'description': f'Level 1-{rotated_height} tidur x {rotated_per_level} pcs',
                        'total_per_level': rotated_per_level,
                        'levels': rotated_height
                    }
            
            else:
                # Fallback ke normal
                stackable_height = int(rak_height / product_height)
                stackable_width = int(rak_width / product_width)
                stackable_length = int(rak_length / product_length)
                
                return {
                    'method': 'normal',
                    'description': f'Level 1-{stackable_height} berdiri x {stackable_width * stackable_length} pcs',
                    'total_per_level': stackable_width * stackable_length,
                    'levels': stackable_height
                }
                
        except Exception as e:
            logger.error(f"Error calculating stacking method: {e}")
            return {
                'method': 'normal',
                'description': 'Level 1 berdiri x 1 pcs',
                'total_per_level': 1,
                'levels': 1
            }
    
    @staticmethod
    def _calculate_hybrid_products_per_slot(rak, product):
        """
        Calculate products per slot dengan GREEDY HYBRID STACKING
        Mengoptimalkan penggunaan ruang dengan kombinasi orientasi normal dan tidur
        
        Args:
            rak: Rak object
            product: Product object
            
        Returns:
            int: Jumlah produk per slot dengan hybrid stacking
        """
        try:
            # Dimensi produk
            product_width = float(product.lebar_cm)
            product_length = float(product.panjang_cm)
            product_height = float(product.tinggi_cm)
            
            # Dimensi rak
            rak_width = float(rak.lebar_cm)
            rak_length = float(rak.panjang_cm)
            rak_height = float(rak.tinggi_cm)
            
            # Hitung produk per slot dengan orientasi normal
            normal_products = _calculate_products_per_slot(rak, product)
            
            # Jika produk tidak mendukung posisi tidur, return normal
            if not product.posisi_tidur:
                return normal_products
            
            # Hitung produk per slot dengan orientasi tidur
            # Buat product object sementara dengan dimensi yang dirotasi
            class RotatedProduct:
                def __init__(self, original_product):
                    self.lebar_cm = original_product.lebar_cm  # width tetap sama
                    self.panjang_cm = original_product.tinggi_cm  # height jadi length
                    self.tinggi_cm = original_product.panjang_cm  # length jadi height
                    self.posisi_tidur = False  # Set false untuk menghindari infinite loop
            
            rotated_product = RotatedProduct(product)
            rotated_products = _calculate_products_per_slot(rak, rotated_product)
            
            # GREEDY HYBRID STACKING ALGORITHM
            # Coba kombinasi orientasi untuk mendapatkan hasil terbaik
            max_products = max(normal_products, rotated_products)
            
            # Jika salah satu orientasi tidak bisa masuk, gunakan yang bisa
            if normal_products == 0 and rotated_products > 0:
                return rotated_products
            elif rotated_products == 0 and normal_products > 0:
                return normal_products
            elif normal_products == 0 and rotated_products == 0:
                return 0
            
            # Jika kedua orientasi bisa masuk, coba hybrid stacking
            # Hitung berapa slot yang dibutuhkan untuk masing-masing orientasi
            # Gunakan quantity = 1 untuk perhitungan per slot
            normal_slots_needed = _calculate_width_slots_needed_for_product(rak, product, 1)
            rotated_slots_needed = _calculate_width_slots_needed_for_product(rak, rotated_product, 1)
            
            # Total slot yang tersedia
            total_slots = int(rak_width / product_width) if product_width > 0 else 0
            
            # Coba berbagai kombinasi hybrid stacking
            best_combination = 0
            
            # Kombinasi 1: Semua normal
            if normal_slots_needed <= total_slots:
                combination1 = normal_products * normal_slots_needed
                best_combination = max(best_combination, combination1)
            
            # Kombinasi 2: Semua rotated
            if rotated_slots_needed <= total_slots:
                combination2 = rotated_products * rotated_slots_needed
                best_combination = max(best_combination, combination2)
            
            # Kombinasi 3: Hybrid (campuran normal dan rotated)
            # Coba berbagai rasio
            for normal_ratio in range(0, min(normal_slots_needed + 1, total_slots + 1)):
                rotated_ratio = total_slots - normal_ratio
                if rotated_ratio >= 0 and rotated_ratio <= rotated_slots_needed:
                    hybrid_total = (normal_products * normal_ratio) + (rotated_products * rotated_ratio)
                    best_combination = max(best_combination, hybrid_total)
            
            return best_combination
            
        except Exception as e:
            logger.error(f"Error calculating hybrid products per slot: {e}")
            # Fallback ke perhitungan normal
            return _calculate_products_per_slot(rak, product)
    
    @staticmethod
    def auto_slotting(product, user, notes=''):
        """
        Automatically select best rack for product (RECOMMENDATION ONLY)
        
        NOTE: Auto slotting bersifat REKOMENDASI, bukan paksaan.
        User tetap bisa memilih rak lain jika diperlukan.
        
        Args:
            product: Product object
            user: User performing slotting
            notes: Additional notes
            
        Returns:
            Dict with success status and selected rak info
        """
        try:
            # Get rak options
            options_result = SlottingService.get_rak_options(product)
            
            if not options_result['success']:
                return {
                    'success': False,
                    'error': options_result['error']
                }
            
            rak_options = options_result['rak_options']
            
            if not rak_options:
                return {
                    'success': False,
                    'error': 'Tidak ada rak yang sesuai dengan dimensi produk ini'
                }
            
            # Select best option (highest fit score)
            best_rak_data = rak_options[0]
            selected_rak = Rak.objects.get(id=best_rak_data['rak_id'])
            
            # Execute slotting
            result = SlottingService.execute_slotting(
                product=product,
                rak=selected_rak,
                user=user,
                notes=f"Auto slotting: {notes}" if notes else "Auto slotting",
                is_auto=True
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in auto slotting: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def execute_slotting(product, rak, user, quantity=None, notes='', is_auto=False):
        """
        Execute slotting operation (RECOMMENDATION ONLY)
        
        NOTE: Slotting bersifat REKOMENDASI, bukan paksaan.
        User tetap bisa memilih rak lain jika diperlukan.
        
        Args:
            product: Product object
            rak: Selected rack
            user: User performing slotting
            quantity: Quantity to slot (optional)
            notes: Additional notes
            is_auto: Whether this is auto slotting
            
        Returns:
            Dict with success status and slotting log
        """
        try:
            # Get stock for quantity validation
            stock = Stock.objects.filter(product=product).first()
            if stock and quantity is None:
                quantity = stock.quantity_putaway
            
            # Validate slotting
            validation = SlottingService.validate_slotting(product, rak, quantity or 0)
            
            if not validation['valid']:
                return {
                    'success': False,
                    'error': validation['message']
                }
            
            # Create slotting log (hanya set suggested_rak, belum scan putaway)
            slotting_log = PutawaySlottingLog.objects.create(
                product=product,
                suggested_rak=rak,
                putaway_by=None,  # Belum di-scan putaway
                putaway_time=None,  # Belum di-scan putaway
                quantity=0,  # Belum di-scan putaway
                notes=notes  # Simpan notes ke database
            )
            
            return {
                'success': True,
                'message': f'Slotting berhasil! {product.sku} → {rak.kode_rak}',
                'slotting_log': slotting_log,
                'rak_info': {
                    'id': rak.id,
                    'kode_rak': rak.kode_rak,
                    'nama_rak': rak.nama_rak,
                    'lokasi': rak.lokasi
                }
            }
            
        except Exception as e:
            logger.error(f"Error executing slotting: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def validate_slotting(product, rak, quantity):
        """
        Validate slotting operation
        
        Args:
            product: Product object
            rak: Target rack
            quantity: Quantity to slot
            
        Returns:
            Dict with valid (bool) and message (str)
        """
        try:
            # Check if product has dimensions
            if not (product.lebar_cm and product.panjang_cm and product.tinggi_cm):
                return {
                    'valid': False,
                    'message': 'Produk tidak memiliki dimensi lengkap'
                }
            
            # Check if rak has dimensions
            if not (rak.lebar_cm and rak.panjang_cm and rak.tinggi_cm):
                return {
                    'valid': False,
                    'message': 'Rak tidak memiliki dimensi lengkap'
                }
            
            # Check if product can fit
            fit_check = SlottingService._can_product_fit_in_rak(product, rak)
            
            if not fit_check['can_fit']:
                return {
                    'valid': False,
                    'message': fit_check['reason']
                }
            
            # Check capacity if quantity provided
            if quantity and quantity > 0:
                from .models import RakCapacity
                capacity = RakCapacity.objects.filter(rak=rak).first()
                
                if capacity:
                    # Hitung berapa slot width yang dibutuhkan dengan hybrid stacking
                    from .rakcapacity import _calculate_width_slots_needed_for_product
                    slots_needed = _calculate_width_slots_needed_for_product(rak, product, quantity)
                    
                    # Hitung berapa cm yang dibutuhkan
                    width_needed = slots_needed * float(product.lebar_cm)
                    
                    if capacity.available_front < width_needed:
                        return {
                            'valid': False,
                            'message': f'Kapasitas rak tidak cukup. Tersedia: {capacity.available_front:.2f}cm, Dibutuhkan: {width_needed:.2f}cm'
                        }
            
            return {
                'valid': True,
                'message': 'Slotting valid'
            }
            
        except Exception as e:
            logger.error(f"Error validating slotting: {e}")
            return {
                'valid': False,
                'message': f'Error dalam validasi: {str(e)}'
            }


# Convenience functions for backward compatibility
def process_putaway(request, rak_id, items_to_putaway, putaway_type='regular', **kwargs):
    """Convenience function for putaway processing"""
    return PutawayService.process_putaway(request, rak_id, items_to_putaway, putaway_type, **kwargs)


def get_rak_options(product, quantity=None):
    """Convenience function for getting rak options"""
    return SlottingService.get_rak_options(product, quantity)


def auto_slotting(product, user, notes=''):
    """Convenience function for auto slotting"""
    return SlottingService.auto_slotting(product, user, notes)


def execute_slotting(product, rak, user, quantity=None, notes='', is_auto=False):
    """Convenience function for executing slotting"""
    return SlottingService.execute_slotting(product, rak, user, quantity, notes, is_auto)


def validate_slotting(product, rak, quantity):
    """Convenience function for validating slotting"""
    return SlottingService.validate_slotting(product, rak, quantity)


# ============================================================================
# FUTURE SLOTTING RECOMMENDATION FEATURES - TO BE IMPLEMENTED
# ============================================================================
# 
# REMINDER FOR FUTURE DEVELOPMENT:
# ================================
# 
# 1. ✅ SLOTTING BY LOCATION (IMPLEMENTED)
#    - Location-based rack recommendations using Rak.lokasi field
#    - Priority: DEKAT(4) > SEDANG(3) > JAUH(2) > BEDA_GUDANG(1)
#    - Integrated with slotting algorithm in get_rak_options()
#    - Display priority badges in putaway interface
# 
# 2. SLOTTING BY SALES (Priority: High)
#    - Implement sales-based rack recommendations
#    - Fast-moving products in easily accessible racks
#    - Slow-moving products in less accessible racks
#    - Use sales history data for recommendations
# 
# 3. SLOTTING BY BRAND (Priority: Medium)
#    - Implement brand-based rack recommendations
#    - Group products by brand for easier picking
#    - Add brand grouping logic
# 
# 4. SLOTTING BY SEASONALITY (Priority: Medium)
#    - Implement seasonal rack recommendations
#    - Seasonal products in easily accessible racks
#    - Use seasonal flags or date-based logic
# 
# 5. SLOTTING BY WEIGHT (Priority: Low)
#    - Implement weight-based rack recommendations
#    - Heavy products in lower racks
#    - Light products in upper racks
# 
# 6. SLOTTING BY EXPIRY DATE (Priority: Low)
#    - Implement FIFO-based rack recommendations
#    - Products with shorter expiry in easily accessible racks
#    - Use expiry date for recommendations
# 
# IMPLEMENTATION NOTES:
# ====================
# - All slotting features should remain RECOMMENDATION ONLY
# - Users should always be able to override recommendations
# - Combine multiple factors for better recommendations
# - Log recommendation reasons for audit trail
# - Consider performance impact for large datasets
# 
# ============================================================================
