import sqlite3

# Path ke database orderlist
DB_PATH = 'database/database_master.db'

def delete_all_orders():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('DELETE FROM orders;')
    conn.commit()
    conn.close()
    print('Semua data di tabel orders sudah dihapus.')

if __name__ == '__main__':
    delete_all_orders()
