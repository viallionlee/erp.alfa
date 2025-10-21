
 fungsi erase_order_from_batch secara singkat adalah sebagai berikut:
Fungsi ini melepaskan item pesanan dari sebuah batch tertentu, tanpa membatalkan pesanan secara permanen.
Cara Kerjanya:
Menerima ID Pesanan dan Nama Batch.
Di dalam sebuah transaksi:
Menyesuaikan (mengurangi) jumlah item di BatchItem terkait dan memperbarui status_ambil (misal: 'partial', 'pending', 'completed').
Jika BatchItem.jumlah dan BatchItem.picked_quantity menjadi nol, BatchItem akan dihapus.
Mengurangi quantity_locked pada Stock produk yang bersangkutan, sehingga stok "dialokasikan kembali" dan tidak lagi terkunci oleh batch ini.
Penting: Saat ini, fungsi ini TIDAK lagi membuat entri di StockCardEntry (sesuai instruksi Anda).
Mengosongkan (nama_batch = None) kolom nama_batch pada item Order asli, secara efektif melepaskannya dari batch.
Mengembalikan status keberhasilan/kegagalan dalam format JSON.
Ini adalah fungsi yang lebih granular, dan cancel_order menggunakannya sebagai langkah awal untuk membersihkan alokasi batch sebelum mengubah status pesanan menjadi 'cancel'.


<!-- posisi edit order
edit_order_batch tidak bisa di lakukan jika batch sudah posisi closed
jika iya harus izin dan harus ada notifikasi atau log history nya karena ini krucial
edit akan berhubungan dengan quantity_locked , `jumlah` di batchitem , `status_ambil` di batchitem , `orders` di orders.order  ,mengupdate inventory.stock , tidka perlu mengedit stockcardentry , tidak mengubah row -->


<!-- buat fungsi transfer batch
buat fungsi keep virtual stock? tp saranku ttp ada 1 tempat utk mensimpan barangny biar tidak hilang 
jd ada batch khusus utk menyimpan semua pending_batch2nd c -->


<!-- fungsi reopen jgn update status_batch menjadi `completed` cukup open aja - sudah oke

ada misteri stockawal saat close batch di stockentrycard
tambahin header `barcode` di stock_card.htm -->

<!-- gmn crnya jgn update stock entry card jika sudah di reopen krn pasti kan ada closebatch lg , tp pas close batch yg di update hanya product_id yg berubah , tidak perlu upte stock card entry yg tdiak ada perubahan
krn nanti jd duplicate2 di stock card entry, dan kasi tipe_pergerakan yg berbeda misal 2nd or 3rd close batch, gmn crnya bisa nge lacak batch ini brp x di close??? -->



close batch seharusnya berhubungan dgn quantity ready
tp gmn crnya 
krn skrg
nanti ktia cari tau sousi nya ya

<!-- buat tampian login mobile --> -->

importan!
buat pending batch double check lg , jd kaya scan ulang barang yg uda masuk ke jumlah_ambil


seharusnya pas truncate orders orderlist jg ke truncate

lihat detail barang di readytoprint munculin ya utk Daftar Order Not Ready to Pick
 
fungsi transfer batch baru kosong
1 buat validasi jumlah_ambil hasil transfer
2  

______________________________

______________________________
<!-- harus ada jumlah_terpakai jg di batchitem -->
_____________________
<!-- benerin sku_bundling utk bisa menerima jumlah lebih dari 1
dan notes sku sku nya di per cantik -->
_____________________
setelah ada over_stock harus di kemanain lg?? harus nya ada stock_return function
fungsi return stock sekalian dgn retunr ke rak 
dan buat fitur rak inventory

_____________________
<!-- benerin tampilan batchpicking pakai card table pending nya -->
----------------------
<!-- order yang uda di batalkan di jaga di bagian picked - printed - handover -->


fungsi delete batch di kaji kembali
1. harus ada return stock batch
2. tidak bisa delete batchlist batchitem secara langsung, fitur delete hanya mendelete nama_batch dari orders_order namun tidak menghapus `batchlist`,batchlist cm bisa di delete ketika tidak ada overstock dari batchitem di dalamnya lagi (tidak ada jumlah_ambil)
3. wajib return stock batch dahulu sebelum delete order batchlist , baru delete batchlist (cascade ke batchitem)

_______________________________
<!-- tolong buat model nya dl
order_cancel_log tempat mencatat semua kejadian order yang `status` & `status_order` di orders_order nya sudah `batal` atau `cancel` 
akan mencatat

order_id_scanned
user (user yg scan)
scan_time
status_order_at_scan
status_retur (default `N`) (jika order_id sudah di scan di module `order_cancel_retur` maka akan update ini menjadi `Y` ) -->

dan module order_cancel_retur
fungsi utk mengupdate data `status_retur` di table `order_cancel_log` dan status_retur di `orders_order` menjadi `Y`

dan menjadi tempat scan balik barang barang yang harus di retur (front end) 
caranya mengurangi `jumlah_ambil` di orders_order by ajax
mengupdate retur_inbound (ini sedang di pikirkan krn proses nya seperti kembali ke inbound )
________________________

<!-- discanpacking jika status sudah shipped sudah picked sudah packed wajibinfoin user yang melakukannya dan waktu melakukannya 
contoh :
Pesanan 'JX5394881690' sudah di-SHIPPED oleh `user` jam `waktu_ship` Tolong kembalikan kertas ini ke admin. -->


gini aq ulang sekali lagi ya

workflow scanordercancel
1.saat scan order id pertama kali langsung cek 
   a.`status` atau `status_order` mengandung kata `batal` atau `cancel` jika `ada` baru boleh, jika `tidak ada` maka response JSON ` Order id ini tidak ada masalah di batalkan, apakah ada masalah?,tolong periksa kembali`
   b.`status_retur` Y atau N jika sudah `Y` response JSON error `Order ini sudah pernah di return oleh `created_by` `created_at` ---- update models class ReturnSourceLog(models.Model): `created_by` nya

jika masih `N` maka boleh  masuk ke front end show table pending , table completed , barcodeinput


2.table pending mengambil detail data dari `orders_order` data yg di ambil adalah  `product_id` `jumlah_ambil` bukan `jumlah` dan excluded status_bundle `Y`

3.cara kerja user scan barcodeinput utk mengupdate `jumlah_check` di table pending sampai table pending tidak ada lagi baru tombol `SUBMIT RETURN` muncul atau bisa di CLICK

4.Fungsi Submit Return adalah 
    a.mengupdate `jumlah_ambil` di orders_order  ` jumlah_ambil di orders_order akan di kurangin jumlah_check dari front end sehingga hasilnya menjadi 0`
    b.mengupdate semua `order_id` dari orders_order `status_retur` nya menjadi `Y` included status_bundle `Y` tanpa terkecuali
    c.mengupdate `product` `qty` di `returnitem` sesuai dengan `jumlah_check` yang ada di frontend (karena data excluded status_bundle `Y`,maka row yg ada status_bundle tidak boleh ikut di update ke `returnitem`)
    d.mengupdate `returnsourcelog`  
    
    ______________________________
    slotting dan putaway
    slotting berdiri sendiri , dia hanya rekomendasi 

    workflow nya
    ada bbrp tahap masuk di erp.alfa
    inboundmasuk - masih masuk ke tahapan quantity_putaway - masuk ke putawaytask -
    returnitem - qc - putaway

    Scan Putaway → quantity_putaway (-) di Stock
              → quantity (+) di Stock  
              → quantity (+) di InventoryRakStock (berdasarkan kode_rak)
              Inbound: 100 unit Product A

→ Stock.quantity_putaway = 100
→ Stock.quantity = 0
→ InventoryRakStock = kosong

Putaway ke Rak A1: 50 unit
→ Stock.quantity_putaway = 50 (-50)
→ Stock.quantity = 50 (+50)  ← Update ini juga
→ InventoryRakStock[A1] = 50

Putaway ke Rak A2: 50 unit  
→ Stock.quantity_putaway = 0 (-50)
→ Stock.quantity = 100 (+50)  ← Update ini juga
→ InventoryRakStock[A1] = 50, InventoryRakStock[A2] = 50


workflow di rak
1. Putaway (Inbound → Rak)
Sumber: Inbound
Tujuan: Rak
Arah: Masuk ke rak
2. Picking (Rak → Outbound)
Sumber: Rak
Tujuan: Order/Batch
Arah: Keluar dari rak
3. Transfer (Rak → Rak)
Sumber: Rak A
Tujuan: Rak B
Arah: Pindah antar rak
 

 _____
 mulai batchpicking - ada over stock - wajib melakukan proses return di returnlist -  setelah itu baru bisa close