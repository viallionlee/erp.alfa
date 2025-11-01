// scanpicking.js

window.ORDER_ID = window.ORDER_ID || "";
window.CSRF_TOKEN = window.CSRF_TOKEN || "";

function playSound(type) {
    if (type === 'completed') {
        new Audio('/static/sounds/completedsound.mp3').play();
    } else if (type === 'success') {
        new Audio('/static/sounds/ding.mp3').play();
    } else if (type === 'error' || type === 'fail') {
        new Audio('/static/sounds/wrong_barcode.mp3').play();
    } else {
        new Audio('/static/sounds/over_scan.mp3').play();
    }
}

function showFeedback(message, type, status_ambil, sku) {
    const feedback = document.getElementById('barcodeFeedback');
    if (!feedback) return;
    feedback.innerHTML = message;
    feedback.className = type === 'success' ? 'alert alert-success' : 'alert alert-danger';

    // Mainkan suara 'ding' jika ada SKU yang baru selesai, TAPI BUKAN seluruh order.
    if (status_ambil === 'completed') {
        playSound('success'); // Gunakan suara 'success' (ding) untuk SKU
        Swal.fire({
            icon: 'success',
            title: 'SKU Selesai!',
            html: `<b>SKU <span style='color:#1769aa;'>${sku || ''}</span> sudah semua di scan.</b>`,
            showConfirmButton: false,
            timer: 1500,
            customClass: { title: 'fw-bold' }
        });
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const orderIdInput = document.getElementById('orderIdInput');
    const orderBarcodeInput = document.getElementById('orderBarcodeInput');
    const barcodeForm = document.getElementById('barcodeForm');
    const barcodeError = document.getElementById('barcodeError');

    // Setel fokus awal jika di halaman input Order ID
    if (orderIdInput) {
        orderIdInput.focus();
    } 

    // Mencegah form submit dan menangani scan
    if (barcodeForm) {
        barcodeForm.addEventListener('submit', function(e) {
            e.preventDefault(); // Prevent form submission
            const barcode = orderBarcodeInput.value.trim();
            if (!barcode) return;
            
            // Process barcode scan
            processBarcodeScan(barcode);
        });
    }

    // Barcode Input Handler (like batchpicking)
    if (orderBarcodeInput) {
        orderBarcodeInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault(); // Prevent default form submission
                const barcode = orderBarcodeInput.value.trim();
                if (!barcode) return;
                
                // Process barcode scan
                processBarcodeScan(barcode);
            }
        });
    }

    function processBarcodeScan(barcode) {
        // Clear input first
        orderBarcodeInput.value = '';

        fetch(`/fullfilment/scanpicking/${window.ORDER_ID}/scan-barcode/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.CSRF_TOKEN,
            },
            body: JSON.stringify({ barcode })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateTable('pendingTableBody', data.pending_orders);
                updateTable('completedTableBody', data.completed_orders);
                
                const pendingTableBody = document.getElementById('pendingTableBody');
                const pendingDataRows = pendingTableBody.querySelectorAll('tr[data-sku]');

                // KONDISI UTAMA
                if (pendingDataRows.length === 0 && data.completed_orders.length > 0) {
                    // Jika seluruh order selesai, panggil modal penyelesaian.
                    // Ini akan memutar suara "completed".
                    showCompletedModal();
                    // JANGAN lanjutkan ke blok 'else' di bawah ini.
                    return; 
                }
                
                // Blok ini hanya akan berjalan jika order BELUM selesai.
                showFeedback('Berhasil scan: ' + (data.sku || barcode), 'success', data.status_ambil, data.sku);
                
            } else {
                playSound('error');
                Swal.fire({
                    icon: 'error',
                    title: 'Scan Gagal',
                    text: data.error || 'Barcode tidak valid.',
                    confirmButtonText: 'Tutup'
                });
            }
            
            // IMPORTANT: Return focus to barcode input after processing
            setTimeout(() => {
                if (orderBarcodeInput) {
                    orderBarcodeInput.focus();
                }
            }, 100);
        })
        .catch(() => {
            showFeedback('Terjadi kesalahan koneksi.', 'error');
            playSound('error');
            
            // Return focus to barcode input even on error
            setTimeout(() => {
                if (orderBarcodeInput) {
                    orderBarcodeInput.focus();
                }
            }, 100);
        });
    }

    function updateTable(tableBodyId, rows) {
        const tbody = document.getElementById(tableBodyId);
        if (!tbody) return;
        tbody.innerHTML = '';
        if (rows.length === 0) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = 8;
            td.className = 'text-center text-muted';
            td.textContent = tableBodyId === 'pendingTableBody' ? 'Tidak ada data pending.' : 'Tidak ada data completed.';
            tr.appendChild(td);
            tbody.appendChild(tr);
            return;
        }
        rows.forEach(function(o) {
            const tr = document.createElement('tr');
            tr.setAttribute('data-sku', o.sku);
            tr.setAttribute('data-barcode', o.barcode);

            let statusBadge = '';
            if (o.status_ambil === 'pending') {
                statusBadge = '<span class="badge bg-warning text-dark">Pending</span>';
            } else if (o.status_ambil === 'partial') {
                statusBadge = '<span class="badge bg-info">Partial</span>';
            } else if (o.status_ambil === 'completed') {
                statusBadge = '<span class="badge bg-success">Completed</span>';
            } else {
                statusBadge = `<span class="badge bg-secondary">${o.status_ambil}</span>`;
            }

            tr.innerHTML = `
                <td>${o.sku}</td>
                <td>${o.barcode}</td>
                <td>${o.nama_produk}</td>
                <td>${o.variant_produk}</td>
                <td>${o.brand}</td>
                <td class="jumlah text-end">${o.jumlah}</td>
                <td class="jumlah-ambil text-end">${o.jumlah_ambil}</td>
                <td class="status-ambil text-center">${statusBadge}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    function showCompletedModal() {
        // Mainkan suara "completed" HANYA saat modal akhir muncul
        playSound('completed');
        
        if (document.getElementById('completedModal')) return;
        const modal = document.createElement('div');
        modal.id = 'completedModal';
        modal.innerHTML = `
        <div style="position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.4);z-index:9999;display:flex;align-items:center;justify-content:center;">
            <div style="background:#fff;padding:2.5rem 2rem 2rem 2rem;border-radius:1rem;box-shadow:0 4px 32px rgba(0,0,0,0.15);text-align:center;min-width:320px;max-width:90vw;">
                <div style="font-size:3rem;color:#28a745;margin-bottom:0.5rem;">
                    <svg width="60" height="60" fill="none" viewBox="0 0 24 24"><circle cx="12" cy="12" r="12" fill="#e6f9ed"/><path d="M7 13.5l3 3 7-7" stroke="#28a745" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                </div>
                <div style="font-size:1.2rem;font-weight:600;margin-bottom:0.5rem;">Semua Order ID <span class="text-primary">${window.ORDER_ID}</span> Sudah Selesai di Check</div>
            </div>
        </div>`;
        document.body.appendChild(modal);
        setTimeout(function(){
            const params = new URLSearchParams(window.location.search);
            if (params.get('from') === 'scanpicking') {
                window.location.href = window.location.origin + "/fullfilment/scanpicking/";
            } else {
                window.location.href = window.location.origin + "/fullfilment/scanpicking/";
            }
        }, 300);
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl+R for reload and focus
        if (e.ctrlKey && (e.key === 'r' || e.key === 'R')) {
            e.preventDefault();
            window.location.reload();
        }
    });
});