import os
import sqlite3
import pandas as pd

FOLDER_PATH = r"C:\Users\m3vil\Downloads\website"
DB_PATH = r"C:\Users\m3vil\OneDrive\Desktop\ERP.ALFA\db.sqlite3"

header_map = {
    'Tanggal Pembuatan': 'tanggal_pembuatan',
    'Status': 'status',
    'Jenis Pesanan': 'jenis_pesanan',
    'Channel': 'channel',
    'Nama Toko': 'nama_toko',
    'ID Pesanan': 'id_pesanan',
    'SKU': 'sku',
    'Jumlah': 'jumlah',
    'Harga Promosi': 'harga_promosi',
    'Catatan Pembeli': 'catatan_pembeli',
    'Kurir': 'kurir',
    'AWB/No. Tracking': 'awb_no_tracking',
    'Metode Pengiriman': 'metode_pengiriman',
    'Kirim Sebelum': 'kirim_sebelum',
}

# Mapping tipe kolom NOT NULL (bisa dideteksi otomatis dari schema, contoh di bawah)
def get_table_columns_and_types(cur, table_name):
    cur.execute(f"PRAGMA table_info({table_name})")
    return [
        {
            "name": row[1],
            "type": row[2].lower(),
            "notnull": row[3],  # 1 if NOT NULL, 0 otherwise
        }
        for row in cur.fetchall()
    ]

def get_order_type(grouped, id_pesanan, jumlah):
    same_id = grouped[grouped['id_pesanan'] == id_pesanan]
    if len(same_id) == 1:
        if jumlah == 1:
            return '1'
        else:
            return '2'
    else:
        return '3'

for filename in os.listdir(FOLDER_PATH):
    if filename.endswith('.xlsx'):
        file_path = os.path.join(FOLDER_PATH, filename)
        try:
            df = pd.read_excel(file_path)
            df = df.loc[:, [c for c in df.columns if str(c).strip().lower() != 'no.']]
            df.rename(columns=header_map, inplace=True)
            df['id_pesanan'] = df['id_pesanan'].astype(str).str.strip()
            df['sku'] = df['sku'].astype(str).str.strip()
            grouped = df.groupby(['id_pesanan', 'sku'], as_index=False).agg(
                {**{col: 'first' for col in df.columns if col not in ['id_pesanan', 'sku', 'jumlah']}, 'jumlah': 'sum'}
            )

            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            table_name = "orders_order"
            columns_info = get_table_columns_and_types(cur, table_name)
            insert_columns = [col['name'] for col in columns_info if col['name'] != 'id']
            created, updated, skipped = 0, 0, 0
            batch = []
            for _, row in grouped.iterrows():
                id_pesanan = row['id_pesanan']
                sku = row['sku']
                jumlah = row['jumlah']
                cur.execute(
                    f'SELECT status FROM {table_name} WHERE id_pesanan=? AND sku=?',
                    (id_pesanan, sku)
                )
                existing = cur.fetchone()
                if existing:
                    if existing[0] != row['status']:
                        cur.execute(
                            f'UPDATE {table_name} SET status=? WHERE id_pesanan=? AND sku=?',
                            (row['status'], id_pesanan, sku)
                        )
                        updated += 1
                    else:
                        skipped += 1
                    continue

                order_type = get_order_type(grouped, id_pesanan, jumlah)
                insert_dict = {}
                for col in columns_info:
                    name = col['name']
                    col_type = col['type']
                    notnull = col['notnull']
                    if name == 'id':
                        continue
                    if name == 'order_type':
                        insert_dict[name] = order_type
                    elif name in row:
                        value = row[name]
                        # Handle kosong/NaN
                        if pd.isna(value) or value is None:
                            # Kolom string
                            if 'char' in col_type or 'text' in col_type:
                                insert_dict[name] = '' if notnull else None
                            # Kolom numerik
                            elif 'int' in col_type or 'real' in col_type or 'float' in col_type or 'double' in col_type or 'numeric' in col_type:
                                insert_dict[name] = 0 if notnull else None
                            else:
                                insert_dict[name] = None
                        else:
                            insert_dict[name] = value
                    else:
                        # Jika kolom tidak ada di Excel
                        if 'char' in col_type or 'text' in col_type:
                            insert_dict[name] = '' if notnull else None
                        elif 'int' in col_type or 'real' in col_type or 'float' in col_type or 'double' in col_type or 'numeric' in col_type:
                            insert_dict[name] = 0 if notnull else None
                        else:
                            insert_dict[name] = None
                values = [insert_dict[col] for col in insert_columns]
                batch.append(values)
                if len(batch) >= 500:
                    placeholders = ','.join(['?'] * len(insert_columns))
                    cur.executemany(
                        f'INSERT INTO {table_name} ({",".join(insert_columns)}) VALUES ({placeholders})',
                        batch
                    )
                    created += len(batch)
                    batch = []
            if batch:
                placeholders = ','.join(['?'] * len(insert_columns))
                cur.executemany(
                    f'INSERT INTO {table_name} ({",".join(insert_columns)}) VALUES ({placeholders})',
                    batch
                )
                created += len(batch)
            conn.commit()
            conn.close()
            print(f"Import sukses dari {file_path}. Created: {created}, Updated: {updated}, Skipped: {skipped}")
        except Exception as e:
            print(f"Error import {file_path}: {e}")

import time
print("Script selesai. Window akan tertutup otomatis dalam 10 detik...")
time.sleep(10)
