# Panduan Alur Data Fulfillment

Tabel ini menjelaskan dampak dari setiap proses utama terhadap field-field kunci di database.

**Legenda:**
*   ✔ : **Ya**, proses ini membuat entri baru.
*   ❌ : **Tidak**, proses ini tidak memengaruhi field ini.
*   ➕ : **Menambah** nilai pada field ini.
*   ➖ : **Mengurangi** nilai pada field ini.
*   🔄 : **Mengubah** nilai field ini (bisa bertambah atau berkurang).
*   ➖/➕: **Mengurangi** di batch asal, **Menambah** di batch tujuan.

---

| Nama Proses | `Stock.quantity_locked` | `BatchItemLog` | `StockCardEntry` | `BatchItem.jumlah` | `BatchItem.jumlah_ambil` | `BatchItem.jumlah_transfer` | `BatchItem.jumlah_terpakai` | Catatan Penting | 
| **Proses Picking**        |q.loc|bil |sce |bi.jl |bi.ja|bi.jt|bi.jp|
| `update_barcode_picklist` | ➖ | ✔  | ❌ | ❌  | ➕  | ❌ | ❌ | Mengunci & mengurangi stok fisik. |
| `update_manual`           | 🔄 | ✔  | ❌ | ❌  | 🔄  | ❌ | ❌ | Menyesuaikan `jumlah_ambil` & stok terkunci. |
| **Proses Return** |
| `return_item_by_scan`     | ❌ | ✔  | ✔  | ❌  | ➖  | ❌ | ❌ | Mengembalikan stok ke `quantity_available`. |
| `return_item_manual`      | ❌ | ✔  | ✔  | ❌  | 🔄  | ❌ | ❌ | Sama seperti di atas, tapi dengan jumlah manual. |
| **Proses Transfer** |
| `transfer_order_item`     | ❌ | ✔  | ❌ |➖➕| ❌  | ❌ | ❌ | Memindahkan kebutuhan (`jumlah`) antar batch. |
| `transfer_batch_pending`  | ❌ | ✔  | ❌ |➖➕| ❌  | ➕ | ❌ | Memindahkan **semua** order gantung & sisa stok pick. |
| **Proses Print** |
| `print_*` (semua jenis)   | ❌ | ❌ | ❌ | ❌  | ❌ | ❌ | ➕ | Menandai stok yang sudah di-pick sebagai "terpakai". |
| **Proses Manajemen** |
| `erase_order_from_batch`  | ➖ | ❌ | ❌ | ➖  | ❌ | ❌ | ❌ | Melepaskan `quantity_locked` & mengurangi kebutuhan. |
| `close_batch`             | ➖ | ❌ | ✔  | ❌  | ❌ | ❌ | ❌ | Melepaskan `quantity_locked` & membuat transaksi `close_batch`. |
| `cancel_order`           | ➖  | ❌ | ❌ | ➖  | ❌ | ❌ | ❌ | Sama seperti erase,tp update status_order.order &status.orderke `cancel`. |
| `reopen_batch`            | ➕ | ❌ | ❌ | ❌  | ❌ | ❌ | ❌ | Mengunci kembali stok berdasarkan `jumlah_ambil`. |

---
**Catatan Tambahan:**
*   Kolom `Order.jumlah` **tidak pernah diubah** oleh proses-proses di atas. Ia hanya dibaca sebagai acuan.
*   Kolom `Stock.quantity_locked` adalah representasi dari stok yang terkunci untuk order.
