from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import json

from .models import Rak, RakCapacity, InventoryRakStock
from products.models import Product


def _calculate_width_slots_needed_for_product(rak, product, quantity):
    """
    Hitung berapa slot width yang dibutuhkan berdasarkan 3 dimensi
    IMPLEMENTASI GREEDY HYBRID STACKING dengan posisi_tidur
    """
    if not (rak.lebar_cm and rak.panjang_cm and rak.tinggi_cm and 
            product.lebar_cm and product.panjang_cm and product.tinggi_cm):
        return 1  # Default jika ada dimensi yang kosong
    
    # Gunakan greedy hybrid stacking calculation
    products_per_slot = _calculate_hybrid_products_per_slot(rak, product)
    
    # Hitung berapa slot width yang dibutuhkan
    if products_per_slot > 0:
        width_slots_needed = (quantity + products_per_slot - 1) // products_per_slot  # Ceiling division
    else:
        width_slots_needed = 1
    
    return width_slots_needed


def _calculate_products_per_slot(rak, product):
    """
    Hitung berapa produk yang bisa masuk dalam 1 slot width
    IMPLEMENTASI GREEDY HYBRID STACKING dengan posisi_tidur
    """
    if not (rak.panjang_cm and rak.tinggi_cm and 
            product.panjang_cm and product.tinggi_cm):
        return 1  # Default jika ada dimensi yang kosong
    
    rak_length = float(rak.panjang_cm)
    rak_height = float(rak.tinggi_cm)
    
    product_length = float(product.panjang_cm)
    product_height = float(product.tinggi_cm)
    
    # Jika produk tidak mendukung posisi tidur, gunakan orientasi normal saja
    if not product.posisi_tidur:
        # Orientasi normal: panjang x tinggi
        products_per_length = int(rak_length / product_length) if product_length > 0 else 1
        products_per_height = int(rak_height / product_height) if product_height > 0 else 1
        return products_per_length * products_per_height
    
    # GREEDY HYBRID STACKING untuk produk dengan posisi_tidur=True
    # Coba semua kemungkinan orientasi produk
    orientations = [
        # Orientasi normal: panjang x tinggi
        (product_length, product_height),
        # Orientasi ditidurkan: tinggi x panjang (jika tinggi produk jadi panjang)
        (product_height, product_length),
    ]
    
    max_products_per_slot = 0
    
    for prod_length, prod_height in orientations:
        # Hitung kapasitas untuk orientasi ini
        products_per_length = int(rak_length / prod_length) if prod_length > 0 else 1
        products_per_height = int(rak_height / prod_height) if prod_height > 0 else 1
        products_per_slot = products_per_length * products_per_height
        
        # Ambil yang maksimal
        max_products_per_slot = max(max_products_per_slot, products_per_slot)
    
    return max_products_per_slot


def _calculate_products_per_slot_normal(rak, product):
    """
    Hitung produk per slot dengan orientasi normal (tanpa hybrid)
    """
    if not (rak.panjang_cm and rak.tinggi_cm and 
            product.panjang_cm and product.tinggi_cm):
        return 1
    
    rak_length = float(rak.panjang_cm)
    rak_height = float(rak.tinggi_cm)
    
    product_length = float(product.panjang_cm)
    product_height = float(product.tinggi_cm)
    
    # Orientasi normal: panjang x tinggi
    products_per_length = int(rak_length / product_length) if product_length > 0 else 1
    products_per_height = int(rak_height / product_height) if product_height > 0 else 1
    
    return products_per_length * products_per_height


def _calculate_products_per_slot_rotated(rak, product):
    """
    Hitung produk per slot dengan orientasi tidur (tanpa hybrid)
    """
    if not (rak.panjang_cm and rak.tinggi_cm and 
            product.panjang_cm and product.tinggi_cm):
        return 1
    
    rak_length = float(rak.panjang_cm)
    rak_height = float(rak.tinggi_cm)
    
    product_length = float(product.panjang_cm)
    product_height = float(product.tinggi_cm)
    
    # Orientasi tidur: tinggi x panjang
    products_per_length = int(rak_length / product_height) if product_height > 0 else 1  # tinggi jadi panjang
    products_per_height = int(rak_height / product_length) if product_length > 0 else 1  # panjang jadi tinggi
    
    return products_per_length * products_per_height


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
        
        # Hitung produk per slot dengan orientasi normal (tanpa hybrid)
        normal_products = _calculate_products_per_slot_normal(rak, product)
        
        # Jika produk tidak mendukung posisi tidur, return normal
        if not product.posisi_tidur:
            return normal_products
        
        # Hitung produk per slot dengan orientasi tidur (tanpa hybrid)
        rotated_products = _calculate_products_per_slot_rotated(rak, product)
        
        # VERTICAL HYBRID STACKING ALGORITHM
        # Coba stacking vertikal: produk tidur di bawah, produk berdiri di atas
        
        # Step 1: Hitung berapa produk tidur yang bisa masuk di bawah
        # Dimensi produk tidur: tinggi jadi panjang, panjang jadi tinggi
        rotated_length = product_height  # 10cm jadi panjang
        rotated_height = product_length  # 6cm jadi tinggi
        
        # Berapa produk tidur yang bisa masuk di panjang rak
        products_rotated_length = int(rak_length / rotated_length) if rotated_length > 0 else 0
        
        # Berapa produk tidur yang bisa masuk di tinggi rak (untuk stack bawah)
        # Ambil setengah tinggi rak untuk stack bawah
        half_rak_height = rak_height / 2
        products_rotated_height_bottom = int(half_rak_height / rotated_height) if rotated_height > 0 else 0
        
        # Total produk tidur di stack bawah
        products_rotated_bottom = products_rotated_length * products_rotated_height_bottom
        
        # Step 2: Hitung berapa produk berdiri yang bisa masuk di atas
        # Tinggi yang tersisa untuk produk berdiri
        remaining_height = rak_height - (products_rotated_height_bottom * rotated_height)
        
        # Berapa produk berdiri yang bisa masuk di panjang rak
        products_normal_length = int(rak_length / product_length) if product_length > 0 else 0
        
        # Berapa produk berdiri yang bisa masuk di tinggi yang tersisa
        products_normal_height = int(remaining_height / product_height) if product_height > 0 else 0
        
        # Total produk berdiri di stack atas
        products_normal_top = products_normal_length * products_normal_height
        
        # Step 3: Hitung total hybrid stacking
        total_hybrid = products_rotated_bottom + products_normal_top
        
        # Step 4: Bandingkan dengan single orientation
        max_single = max(normal_products, rotated_products)
        
        # Ambil yang terbaik
        best_result = max(total_hybrid, max_single)
        
        return best_result
        
    except Exception as e:
        # Fallback ke perhitungan normal
        return _calculate_products_per_slot(rak, product)


def update_rak_capacity_for_rak(rak_code):
    """
    Utility function untuk update capacity satu rak tertentu
    """
    try:
        rak = get_object_or_404(Rak, kode_rak=rak_code)
        
        # Update capacity untuk rak ini saja
        try:
            capacity = RakCapacity.objects.get(rak=rak)
        except RakCapacity.DoesNotExist:
            capacity = RakCapacity.objects.create(rak=rak)
        
        # Hitung ulang capacity
        stocks = InventoryRakStock.objects.filter(rak=rak, quantity__gt=0).select_related('product')
        
        total_used_width = 0
        for stock in stocks:
            if (stock.product.lebar_cm and stock.product.panjang_cm and 
                stock.product.tinggi_cm and rak.lebar_cm and 
                rak.panjang_cm and rak.tinggi_cm):
                
                # Hitung berdasarkan 3 dimensi
                width_slots_needed = _calculate_width_slots_needed_for_product(
                    rak, stock.product, stock.quantity
                )
                total_used_width += width_slots_needed * float(stock.product.lebar_cm)
            elif stock.product.lebar_cm:
                # Fallback ke perhitungan lama
                total_used_width += float(stock.product.lebar_cm) * stock.quantity
        
        # Update available_front
        rak_width_float = float(rak.lebar_cm) if rak.lebar_cm else 0
        capacity.available_front = max(0, rak_width_float - total_used_width)
        capacity.save()
        
        return True, f'Capacity rak {rak_code} berhasil diupdate'
        
    except Exception as e:
        return False, f'Error update capacity rak {rak_code}: {str(e)}'


def update_rak_capacity_for_product(product_id):
    """
    Utility function untuk update capacity semua rak yang memiliki produk tertentu
    """
    try:
        # Ambil semua rak yang memiliki produk ini
        rak_stocks = InventoryRakStock.objects.filter(
            product_id=product_id,
            quantity__gt=0
        ).values_list('rak__kode_rak', flat=True).distinct()
        
        updated_count = 0
        for rak_code in rak_stocks:
            success, message = update_rak_capacity_for_rak(rak_code)
            if success:
                updated_count += 1
        
        return True, f'Berhasil update capacity untuk {updated_count} rak'
        
    except Exception as e:
        return False, f'Error update capacity untuk produk {product_id}: {str(e)}'


@login_required
@permission_required('inventory.view_rak', raise_exception=True)
def rak_capacity_view(request):
    """
    View untuk menampilkan kapasitas rak berdasarkan available_front
    """
    # Ambil semua rak dengan capacity
    rak_capacities = RakCapacity.objects.select_related('rak').all().order_by('rak__kode_rak')
    
    # Hitung summary
    total_raks = rak_capacities.count()
    total_available_front = sum(capacity.available_front for capacity in rak_capacities)
    total_used_front = sum(capacity.used_front for capacity in rak_capacities)
    total_width = sum(capacity.rak.lebar_cm or 0 for capacity in rak_capacities)
    
    # Rata-rata utilization
    avg_utilization = (float(total_used_front) / float(total_width) * 100) if total_width > 0 else 0
    
    context = {
        'rak_capacities': rak_capacities,
        'total_raks': total_raks,
        'total_available_front': total_available_front,
        'total_used_front': total_used_front,
        'total_width': total_width,
        'avg_utilization': avg_utilization,
    }
    
    return render(request, 'inventory/rak_capacity.html', context)


@login_required
@permission_required('inventory.change_rak', raise_exception=True)
def update_rak_capacity(request):
    """
    AJAX endpoint untuk update rak capacity berdasarkan current stock
    """
    try:
        # Update semua rak capacity
        updated_count = 0
        for capacity in RakCapacity.objects.select_related('rak').all():
            capacity.update_available_front()
            updated_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Berhasil update {updated_count} rak capacity',
            'updated_count': updated_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Terjadi kesalahan: {str(e)}'
        }, status=500)


def update_single_rak_capacity(request):
    """
    AJAX endpoint untuk update capacity satu rak tertentu
    """
    try:
        data = json.loads(request.body)
        rak_code = data.get('rak_code')
        
        if not rak_code:
            return JsonResponse({
                'success': False,
                'error': 'Kode rak tidak boleh kosong'
            }, status=400)
        
        # Update capacity untuk rak ini saja
        success, message = update_rak_capacity_for_rak(rak_code)
        
        if success:
            # Ambil data capacity terbaru untuk response
            try:
                capacity = RakCapacity.objects.select_related('rak').get(rak__kode_rak=rak_code)
                return JsonResponse({
                    'success': True,
                    'message': message,
                    'rak_code': rak_code,
                    'new_capacity': {
                        'available_front': float(capacity.available_front),
                        'used_front': float(capacity.used_front),
                        'utilization': float(capacity.utilization_percentage)
                    }
                })
            except RakCapacity.DoesNotExist:
                return JsonResponse({
                    'success': True,
                    'message': message,
                    'rak_code': rak_code
                })
        else:
            return JsonResponse({
                'success': False,
                'error': message
            }, status=500)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Data JSON tidak valid'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Terjadi kesalahan: {str(e)}'
        }, status=500)


@require_GET
def rak_detail_data(request):
    """
    API endpoint untuk mendapatkan detail item di rak tertentu
    """
    try:
        rak_code = request.GET.get('rak_code')
        if not rak_code:
            return JsonResponse({
                'success': False,
                'error': 'Kode rak tidak boleh kosong'
            }, status=400)
        
        # Ambil rak
        rak = get_object_or_404(Rak, kode_rak=rak_code)
        
        # Ambil semua stock di rak tersebut
        stocks = InventoryRakStock.objects.filter(
            rak=rak,
            quantity__gt=0  # Hanya yang ada quantity
        ).select_related('product').order_by('-quantity')
        
        items = []
        for stock in stocks:
            # Format dimensi produk dengan label yang jelas
            product_dimensions = []
            if stock.product.lebar_cm:
                product_dimensions.append(f"L: {float(stock.product.lebar_cm)}cm")
            if stock.product.panjang_cm:
                product_dimensions.append(f"P: {float(stock.product.panjang_cm)}cm")
            if stock.product.tinggi_cm:
                product_dimensions.append(f"T: {float(stock.product.tinggi_cm)}cm")
            
            if product_dimensions:
                product_dimensions_str = " | ".join(product_dimensions)
                has_dimensions = True
            else:
                product_dimensions_str = "Tidak ada dimensi"
                has_dimensions = False
            
            # Hitung berdasarkan 3 dimensi jika ada dimensi produk
            if stock.product.lebar_cm and stock.product.panjang_cm and stock.product.tinggi_cm:
                width_slots_needed = _calculate_width_slots_needed_for_product(rak, stock.product, stock.quantity)
                used_width = width_slots_needed * float(stock.product.lebar_cm)
                percentage = (used_width / float(rak.lebar_cm)) * 100 if rak.lebar_cm else 0
                width_cm = float(stock.product.lebar_cm)
                used_width_str = f"{used_width:.1f}"
                width_slots = width_slots_needed
                products_per_slot = _calculate_products_per_slot(rak, stock.product)
            else:
                # Jika tidak ada dimensi produk, gunakan default values
                width_slots_needed = 1
                used_width = stock.quantity  # Default: 1 unit = 1 cm
                percentage = (used_width / float(rak.lebar_cm)) * 100 if rak.lebar_cm else 0
                width_cm = 0
                used_width_str = f"{used_width:.1f} (estimasi)"
                width_slots = 1
                products_per_slot = 1
            
            # Hitung slot terpakai (simple: used_width / lebar_produk)
            slots_used = 0
            if stock.product.lebar_cm and float(stock.product.lebar_cm) > 0:
                slots_used = round(float(used_width) / float(stock.product.lebar_cm), 1)
            
            items.append({
                'sku': stock.product.sku,
                'nama_produk': stock.product.nama_produk,
                'variant_produk': stock.product.variant_produk,
                'brand': stock.product.brand,
                'photo': stock.product.photo.url if stock.product.photo else None,
                'width_cm': width_cm,
                'product_dimensions': product_dimensions_str,
                'has_dimensions': has_dimensions,
                'product_id': stock.product.id,
                'quantity': stock.quantity,
                'used_width': used_width_str,
                'slots_used': slots_used,
                'percentage': percentage,
                'width_slots': width_slots,
                'products_per_slot': products_per_slot
            })
        
        # Format dimensi rak dengan label yang jelas
        rak_dimensions = []
        if rak.lebar_cm:
            rak_dimensions.append(f"L: {float(rak.lebar_cm)}cm")
        if rak.panjang_cm:
            rak_dimensions.append(f"P: {float(rak.panjang_cm)}cm")
        if rak.tinggi_cm:
            rak_dimensions.append(f"T: {float(rak.tinggi_cm)}cm")
        
        if rak_dimensions:
            rak_dimensions_str = " | ".join(rak_dimensions)
        else:
            rak_dimensions_str = "Tidak ada data dimensi"
        
        return JsonResponse({
            'success': True,
            'rak_code': rak_code,
            'rak_name': rak.nama_rak,
            'rak_width': float(rak.lebar_cm) if rak.lebar_cm else 0,
            'rak_dimensions': rak_dimensions_str,
            'rak_lebar_cm': float(rak.lebar_cm) if rak.lebar_cm else None,
            'rak_panjang_cm': float(rak.panjang_cm) if rak.panjang_cm else None,
            'rak_tinggi_cm': float(rak.tinggi_cm) if rak.tinggi_cm else None,
            'items': items
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Terjadi kesalahan: {str(e)}'
        }, status=500)


@require_POST
@csrf_exempt
def update_rak_dimensions(request):
    """
    AJAX endpoint untuk update dimensi rak
    """
    try:
        data = json.loads(request.body)
        rak_code = data.get('rak_code')
        lebar_cm = data.get('lebar_cm')
        panjang_cm = data.get('panjang_cm')
        tinggi_cm = data.get('tinggi_cm')
        
        if not rak_code:
            return JsonResponse({
                'success': False,
                'error': 'Kode rak tidak boleh kosong'
            }, status=400)
        
        # Ambil rak
        rak = get_object_or_404(Rak, kode_rak=rak_code)
        
        # Update dimensi
        if lebar_cm is not None:
            # Konversi koma ke titik untuk format float
            lebar_str = str(lebar_cm).replace(',', '.') if lebar_cm else None
            rak.lebar_cm = float(lebar_str) if lebar_str else None
        if panjang_cm is not None:
            # Konversi koma ke titik untuk format float
            panjang_str = str(panjang_cm).replace(',', '.') if panjang_cm else None
            rak.panjang_cm = float(panjang_str) if panjang_str else None
        if tinggi_cm is not None:
            # Konversi koma ke titik untuk format float
            tinggi_str = str(tinggi_cm).replace(',', '.') if tinggi_cm else None
            rak.tinggi_cm = float(tinggi_str) if tinggi_str else None
        
        rak.save()
        
        # Update rak capacity setelah perubahan dimensi
        success, message = update_rak_capacity_for_rak(rak_code)
        if not success:
            return JsonResponse({
                'success': False,
                'error': f'Berhasil update dimensi tapi gagal update capacity: {message}'
            }, status=500)
        
        return JsonResponse({
            'success': True,
            'message': f'Dimensi rak {rak_code} berhasil diupdate',
            'rak_code': rak_code,
            'new_dimensions': {
                'lebar_cm': float(rak.lebar_cm) if rak.lebar_cm else None,
                'panjang_cm': float(rak.panjang_cm) if rak.panjang_cm else None,
                'tinggi_cm': float(rak.tinggi_cm) if rak.tinggi_cm else None
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Data JSON tidak valid'
        }, status=400)
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': f'Format angka tidak valid: {str(e)}'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Terjadi kesalahan: {str(e)}'
        }, status=500)
