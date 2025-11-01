import os
import sys
import shutil
import pandas as pd
import glob
import django
from datetime import datetime

# --- SETUP DJANGO ENVIRONMENT ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_alfa.settings')
django.setup()

# --- Impor setelah setup ---
from django.db import transaction
from django.db.models import Q
from orders.models import Order, OrderImportHistory
from products.models import Product
from django.contrib.auth import get_user_model

# --- KONFIGURASI ---
FOLDER_PATH = r"C:\Users\m3vil\Downloads\import folder"
# ID user yang akan tercatat di histori. Boleh diganti jika ada ID yang valid.
USER_ID_FOR_HISTORY = 1 
# --------------------

# --- Fungsi aman untuk konversi tipe data ---
def safe_int(value, default=0):
    """Mengonversi nilai ke integer dengan aman. Mengembalikan default jika gagal."""
    try:
        # Mengonversi ke float dulu untuk menangani kasus seperti "1.0"
        return int(float(value))
    except (ValueError, TypeError, AttributeError):
        return default

def safe_float(value, default=0.0):
    """Mengonversi nilai ke float dengan aman. Mengembalikan default jika gagal."""
    try:
        return float(value)
    except (ValueError, TypeError, AttributeError):
        return default

def process_single_file(file_path, user=None):
    """Memproses satu file import dalam satu transaksi database."""
    filename = os.path.basename(file_path)
    
    with transaction.atomic():
        print(f"[{datetime.now()}] Memulai transaksi untuk file: {filename}")
        
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ['.xls', '.xlsx']:
            raise ValueError(f"File harus Excel (.xls/.xlsx), bukan '{ext}'")

        # Baca semua data sebagai string agar bisa divalidasi manual
        df = pd.read_excel(file_path, dtype=str).fillna('')
        df = df.loc[:, [c for c in df.columns if str(c).strip().lower() != 'no.']]

        header_map = { 'Tanggal Pembuatan': 'tanggal_pembuatan', 'Status': 'status', 'Jenis Pesanan': 'jenis_pesanan', 'Channel': 'channel', 'Nama Toko': 'nama_toko', 'ID Pesanan': 'id_pesanan', 'SKU': 'sku', 'Jumlah': 'jumlah', 'Harga Promosi': 'harga_promosi', 'Catatan Pembeli': 'catatan_pembeli', 'Kurir': 'kurir', 'AWB/No. Tracking': 'awb_no_tracking', 'Metode Pengiriman': 'metode_pengiriman', 'Kirim Sebelum': 'kirim_sebelum' }
        def normalize_header(h): return str(h).strip().replace('.', '').replace('/', '').replace('-', '').replace('_', '').replace('  ', ' ').lower()
        norm_header_map = {normalize_header(k): v for k, v in header_map.items()}
        df.rename(columns=lambda c: norm_header_map.get(normalize_header(c), c), inplace=True)

        # --- PERBAIKAN UTAMA: Konversi 'jumlah' menjadi ANGKA sebelum agregasi ---
        if 'jumlah' in df.columns:
            # pd.to_numeric mengubah string ke angka, errors='coerce' membuat yg gagal jadi NaN
            # .fillna(0) mengubah NaN menjadi 0, lalu .astype(int) menjadikannya integer.
            df['jumlah'] = pd.to_numeric(df['jumlah'], errors='coerce').fillna(0).astype(int)
        else:
            # Jika kolom jumlah tidak ada, buat dengan nilai default 0
            df['jumlah'] = 0
        # ------------------------------------------------------------------------

        df['id_pesanan'] = df['id_pesanan'].astype(str).str.strip()
        df['sku'] = df['sku'].astype(str).str.strip().str.upper()

        grouped = df.groupby(['id_pesanan', 'sku'], as_index=False).agg({**{col: 'first' for col in df.columns if col not in ['id_pesanan', 'sku', 'jumlah']}, 'jumlah': 'sum'})
        
        if grouped.empty:
            print(f"File {filename} kosong atau tidak memiliki data valid. Dilewati.")
            return

        updated, created, skipped, failed_count = 0, 0, 0, 0
        failed_notes = []
        orders_to_create, orders_to_update = [], []

        update_map = {(row['id_pesanan'], row['sku']): row for _, row in grouped.iterrows()}
        q_objs = [Q(id_pesanan=idp, sku=sku) for (idp, sku) in update_map.keys()]
        query = q_objs.pop()
        for q in q_objs: query |= q
        existing_orders = Order.objects.filter(query)
        existing_keys = {(order.id_pesanan, order.sku) for order in existing_orders}
        
        sku_set = set(grouped['sku'])
        products_map = {p.sku.upper(): p for p in Product.objects.filter(sku__in=sku_set)}

        order_types = {}
        for id_p, group in grouped.groupby('id_pesanan'):
            if len(group) == 1:
                jumlah = group.iloc[0]['jumlah']
                order_types[id_p] = '2' if jumlah > 1 else '1'
            else:
                brands = {products_map.get(row['sku'], {}).brand for _, row in group.iterrows() if products_map.get(row['sku'])}
                brands.discard(None); brands.discard('')
                order_types[id_p] = '4' if len(brands) == 1 else '3'

        for key, row_data in update_map.items():
            id_pesanan, sku = key
            
            if key in existing_keys:
                order = next((o for o in existing_orders if o.id_pesanan == id_pesanan and o.sku == sku), None)
                if order:
                    new_status = row_data.get('status', '')
                    if new_status and order.status != new_status:
                        order.status = new_status
                        orders_to_update.append(order); updated += 1
                    else: skipped += 1
                continue
            
            product_obj = products_map.get(sku.upper())
            if not product_obj:
                failed_count += 1; failed_notes.append(f"SKU Not Found: {sku} in Order {id_pesanan}"); continue

            # Menggunakan fungsi safe_int dan safe_float
            order_kwargs = {
                'tanggal_pembuatan': row_data.get('tanggal_pembuatan'), 'status': row_data.get('status', ''), 'jenis_pesanan': row_data.get('jenis_pesanan', ''), 'channel': row_data.get('channel', ''), 'nama_toko': row_data.get('nama_toko', ''), 'id_pesanan': id_pesanan, 'sku': sku,
                'jumlah': int(row_data.get('jumlah', 0)),
                'harga_promosi': safe_float(row_data.get('harga_promosi')),
                'catatan_pembeli': row_data.get('catatan_pembeli', ''), 'kurir': row_data.get('kurir', ''), 'awb_no_tracking': row_data.get('awb_no_tracking', ''), 'metode_pengiriman': row_data.get('metode_pengiriman', ''), 'kirim_sebelum': row_data.get('kirim_sebelum'),
                'product': product_obj,
                'order_type': order_types.get(id_pesanan, '1'),
                'status_order': 'pending',
            }
            orders_to_create.append(Order(**order_kwargs))

        if orders_to_update: Order.objects.bulk_update(orders_to_update, ['status'])
        if orders_to_create: Order.objects.bulk_create(orders_to_create, batch_size=1000)
        created = len(orders_to_create)

        OrderImportHistory.objects.create(file_name=filename, notes='\n'.join(failed_notes) if failed_notes else 'Impor Otomatis Berhasil', imported_by=user)
        print(f"Selesai: {filename} | Dibuat: {created}, Diperbarui: {updated}, Dilewati: {skipped}, Gagal: {failed_count}")

def run_import_from_folder():
    """Fungsi utama untuk memindai folder dan memproses semua file di dalamnya."""
    print("="*60 + f"\n[{datetime.now()}] Memulai Proses Impor Order Otomatis\nMemindai folder: {FOLDER_PATH}\n" + "="*60)

    if not os.path.isdir(FOLDER_PATH):
        print(f"!!! FATAL: Folder tidak ditemukan di -> {FOLDER_PATH}"); return

    # --- BAGIAN YANG DIPERBAIKI ---
    User = get_user_model()
    importer = None
    if USER_ID_FOR_HISTORY:
        try:
            importer = User.objects.get(id=USER_ID_FOR_HISTORY)
            print(f"INFO: Histori akan dicatat atas nama user: '{importer.username}'")
        except User.DoesNotExist:
            print(f"!!! WARNING: User dengan ID={USER_ID_FOR_HISTORY} tidak ditemukan. Histori akan dicatat tanpa user.")
    # -----------------------------
    
    excel_files = glob.glob(os.path.join(FOLDER_PATH, "*.xls*"))

    if not excel_files:
        print("Tidak ada file untuk diproses.")
    else:
        for file_path in excel_files:
            try:
                process_single_file(file_path, user=importer)
                print(f"-> SUKSES: Memproses {os.path.basename(file_path)}.")
            except Exception as e:
                print(f"!!! GAGAL TOTAL untuk file {os.path.basename(file_path)}: {e}")
            finally:
                try:
                    os.remove(file_path)
                    print(f"-> INFO: File {os.path.basename(file_path)} telah dihapus.\n")
                except OSError as e:
                    print(f"!!! WARNING: Gagal menghapus file {os.path.basename(file_path)}: {e}\n")
    
    print("="*60 + f"\n[{datetime.now()}] Proses Impor Selesai.\n" + "="*60)

if __name__ == "__main__":
    run_import_from_folder()
