import pandas as pd
from django.apps import apps
from django.db import models

def validate_orders_excel_header(excel_file):
    # Read the first row (header) from the Excel file
    df = pd.read_excel(excel_file, nrows=0)
    excel_headers = [col.strip().lower() for col in df.columns if col.strip().lower() != "no."]

    # Get model field names from the orders table (excluding 'id' and auto fields)
    Order = apps.get_model('orders', 'Order')
    # Map model fields to expected Excel headers (case-insensitive, skip relations)
    model_fields = [
        ('tanggal_pembuatan', 'Tanggal Pembuatan'),
        ('status', 'Status'),
        ('jenis_pesanan', 'Jenis Pesanan'),
        ('channel', 'Channel'),
        ('nama_toko', 'Nama Toko'),
        ('id_pesanan', 'ID Pesanan'),
        ('sku', 'SKU'),
        ('jumlah', 'Jumlah'),
        ('harga_promosi', 'Harga Promosi'),
        ('catatan_pembeli', 'Catatan Pembeli'),
        ('kurir', 'Kurir'),
        ('awb_no_tracking', 'AWB/No. Tracking'),
        ('metode_pengiriman', 'Metode Pengiriman'),
        ('kirim_sebelum', 'Kirim Sebelum'),
        ('order_type', 'Order Type'),
        ('status_order', 'Status Order'),
        ('status_cancel', 'Status Cancel'),
        ('status_retur', 'Status Retur'),
        ('jumlah_ambil', 'Jumlah Ambil'),
        ('status_ambil', 'Status Ambil'),
        ('batchlist', 'Batch'),
        ('product', 'Produk'),
    ]
    expected_headers = [h[1].strip().lower() for h in model_fields]

    missing_in_excel = [h for h in expected_headers if h not in excel_headers]
    extra_in_excel = [h for h in excel_headers if h not in expected_headers]

    return {
        "missing_in_excel": missing_in_excel,
        "extra_in_excel": extra_in_excel,
        "is_valid": not missing_in_excel
    }

# Example usage:
# result = validate_orders_excel_header('path_to_excel.xlsx')
# print(result)
