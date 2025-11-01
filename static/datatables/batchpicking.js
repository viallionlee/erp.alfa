/**
 * @version 4.1 - Final & Feature Complete (Fixes missing features)
 * @description Script terpadu untuk halaman Batch Picking.
 * Mengembalikan fungsionalitas Manual Search, event keyboard, suara, dan Scan History.
 */
document.addEventListener('DOMContentLoaded', function () {

    // === Fungsi Global ===
    function playSound(type) {
        let soundFile = '';
        switch(type) {
            case 'completed': soundFile = '/static/sounds/completedsound.mp3'; break;
            case 'success': soundFile = '/static/sounds/ding.mp3'; break;
            case 'error': soundFile = '/static/sounds/errorsound.mp3'; break;
            default: soundFile = '/static/sounds/errorsound.mp3'; break;
        }
        new Audio(soundFile).play();
    }

    /**
     * Menambahkan baris baru ke tabel riwayat scan.
     * @param {string} barcode - Barcode yang di-scan.
     * @param {object} result - Objek berisi status dan waktu scan.
     * @param {string} type - 'S' untuk Scan, 'M' untuk Manual.
     */
    function addScanToHistory(barcode, result, type = 'S') { // Default ke 'S'
        const tableBody = document.getElementById('scanHistoryTableBody');
        if (!tableBody) return;

        const timeString = result.time || new Date().toLocaleTimeString('id-ID', { hour12: false, timeZone: 'Asia/Jakarta' });
        
        let statusHtml = '';
        switch(result.status) {
            case 'completed': statusHtml = `<span class="badge bg-success">Completed</span>`; break;
            case 'success': statusHtml = `<span class="badge bg-primary">OK</span>`; break;
            case 'overscan': statusHtml = `<span class="badge bg-warning text-dark">Over Scan</span>`; break;
            default: statusHtml = `<span class="badge bg-danger">Error</span>`; break;
        }
        const newRow = document.createElement('tr');
        newRow.innerHTML = `
            <td class="ps-3">${timeString}</td>
            <td><b>${type}</b></td>
            <td>${barcode}</td>
            <td>${statusHtml}</td>
        `;
        tableBody.insertBefore(newRow, tableBody.firstChild);
        if (tableBody.rows.length > 10) {
            tableBody.deleteRow(10);
        }
    }

    // === ELEMEN UTAMA ===
    const barcodeInput = document.getElementById('barcodeInput');
    const pendingItemsContainer = document.getElementById('pendingItemsContainer');
    const pendingSearchInput = document.getElementById('pendingSearchInput');
    const pendingFilterButtons = document.getElementById('pendingFilterButtons');
    const updateManualInput = document.getElementById('updateManualInput');
    const updateManualDropdown = document.getElementById('updateManualDropdown');
    const updateManualQtyControl = document.getElementById('updateManualQtyControl');
    const qtyMinus = document.getElementById('qtyMinus');
    const qtyPlus = document.getElementById('qtyPlus');
    const qtyInput = document.getElementById('qtyInput');
    const qtySubmit = document.getElementById('qtySubmit');
    const updateManualFeedback = document.getElementById('updateManualFeedback');

    if (!barcodeInput || !pendingItemsContainer || !pendingFilterButtons || !updateManualInput) {
        console.error("Satu atau lebih elemen UI penting tidak ditemukan. Script berhenti.");
        return;
    }
    // 1. Fungsikan kembali tombol Show History
    const showHistoryBtn = document.getElementById('showHistoryBtn');
    if (showHistoryBtn) {
        showHistoryBtn.addEventListener('click', function() {
            window.location.href = `/fullfilment/batchitemlogs/${window.NAMA_PICKLIST}/`;
        });
    }

    barcodeInput.focus();

    // === STATE MANAGEMENT ===
    let isProcessing = false;
    let currentStatusFilter = 'pending';
    let manualSearchItems = [], filteredManualItems = [], selectedManualIdx = -1, selectedManualItem = null, maxManualQty = 0;

    // === FUNGSI INTI ===

    function updateBadgeCounts() {
        const allItems = pendingItemsContainer.querySelectorAll('.list-group-item[data-status]');
        const counts = { pending: 0, partial: 0, over_stock: 0, completed: 0 };
        allItems.forEach(item => {
            const status = item.dataset.status;
            if (counts.hasOwnProperty(status)) counts[status]++;
        });
        document.querySelector('#pendingFilterButtons button[data-filter="pending"] .badge').textContent = counts.pending;
        document.querySelector('#pendingFilterButtons button[data-filter="partial"] .badge').textContent = counts.partial;
        document.querySelector('#pendingFilterButtons button[data-filter="over_stock"] .badge').textContent = counts.over_stock;
        document.querySelector('#pendingFilterButtons button[data-filter="completed"] .badge').textContent = counts.completed;
    }

    function applyFilterAndSearch() {
        const query = pendingSearchInput.value.toLowerCase().trim();
        const allItems = pendingItemsContainer.querySelectorAll('.list-group-item[data-status]');
        allItems.forEach(item => {
            const statusMatch = (currentStatusFilter === 'all') || (item.dataset.status === currentStatusFilter);
            const searchMatch = item.textContent.toLowerCase().includes(query);
            item.classList.toggle('item-hidden', !(searchMatch && statusMatch));
        });
    }

    function updateItemUI(data) {
        const barcodeToUpdate = data.main_barcode || (data.product_info && data.product_info.barcode);
        if (!barcodeToUpdate) return;
        const row = document.querySelector(`.list-group-item[data-barcode='${barcodeToUpdate}']`);
        if (!row) return;

        row.dataset.status = data.status_ambil;
        const statusEl = row.querySelector('.status-ambil');
        let statusClass = 'bg-secondary', statusText = data.status_ambil;
        if (data.status_ambil === 'pending') { statusClass = 'bg-light text-dark'; statusText = 'Pending'; }
        if (data.status_ambil === 'partial') { statusClass = 'bg-warning text-dark'; statusText = 'Partial'; }
        if (data.status_ambil === 'over_stock') { statusClass = 'bg-danger'; statusText = 'Over Stock'; }
        if (data.status_ambil === 'completed') { statusClass = 'bg-success'; statusText = 'Completed'; }
        statusEl.className = `badge rounded-pill status-ambil ${statusClass}`;
        statusEl.textContent = statusText;
        row.querySelector('.jumlah-ambil').textContent = data.jumlah_ambil;

        if (data.product_info) {
            document.getElementById('monitor-nama').textContent = data.product_info.nama_produk;
            document.getElementById('monitor-jumlah').textContent = `${data.jumlah_ambil} / ${data.jumlah}`;
            document.getElementById('monitor-sku').textContent = data.product_info.sku || '---';
            document.getElementById('monitor-barcode').textContent = data.product_info.barcode || '---';
            document.getElementById('monitor-brand').textContent = data.product_info.brand || '---';
            document.getElementById('monitor-variant').textContent = data.product_info.variant_produk || '---';
        }
        updateBadgeCounts();
        applyFilterAndSearch();
    }

    // === FUNGSI MANUAL SEARCH ===

    function populateManualSearchItems() {
        manualSearchItems = Array.from(document.querySelectorAll('#pendingItemsContainer .list-group-item[data-barcode]')).map(row => {
            const getText = (selector) => row.querySelector(selector)?.textContent.trim() || '';
            return {
                sku: getText('.sku-badge').replace('SKU:', '').trim(),
                barcode: row.dataset.barcode,
                nama_produk: getText('.product-name-link'),
                variant_produk: getText('.variant-produk'),
                brand: getText('.brand'),
                jumlah: parseInt(getText('.jumlah')) || 0,
                jumlah_ambil: parseInt(getText('.jumlah-ambil')) || 0,
            };
        });
    }

    function renderDropdown() {
        updateManualDropdown.innerHTML = '';
        if (filteredManualItems.length === 0) { updateManualDropdown.style.display = 'none'; return; }
        filteredManualItems.forEach((item, idx) => {
            const el = document.createElement('button');
            el.type = 'button';
            el.className = 'list-group-item list-group-item-action' + (selectedManualIdx === idx ? ' active' : '');
            el.innerHTML = `<b>${item.sku}</b> | ${item.nama_produk} <span class='text-info'>${item.variant_produk}</span>`;
            el.addEventListener('mousedown', (e) => { e.preventDefault(); selectItem(idx); });
            updateManualDropdown.appendChild(el);
        });
        updateManualDropdown.style.display = 'block';
    }

    function selectItem(idx) {
        selectedManualIdx = idx;
        selectedManualItem = filteredManualItems[idx];
        maxManualQty = selectedManualItem.jumlah;
        updateManualDropdown.style.display = 'none';
        updateManualInput.value = `${selectedManualItem.sku} | ${selectedManualItem.nama_produk}`;
        updateManualQtyControl.style.display = 'flex';
        qtyInput.value = selectedManualItem.jumlah_ambil;
        qtyInput.max = maxManualQty;
        qtyInput.focus();
    }

    function hideAllManual() {
        updateManualDropdown.style.display = 'none';
        updateManualQtyControl.style.display = 'none';
        updateManualFeedback.innerHTML = '';
        updateManualInput.value = '';
        selectedManualItem = null;
        barcodeInput.focus();
    }

    function submitQty() {
        if (!selectedManualItem || isProcessing) return;
        const jumlah_ambil = parseInt(qtyInput.value);
        if (isNaN(jumlah_ambil) || jumlah_ambil < 0) {
            playSound('error');
            updateManualFeedback.innerHTML = '<div class="alert alert-danger p-2">Jumlah tidak valid.</div>';
            return;
        }
        isProcessing = true;

        fetch(`/fullfilment/batchpicking/${window.NAMA_PICKLIST}/update_manual/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.CSRF_TOKEN },
            body: JSON.stringify({ barcode: selectedManualItem.barcode, jumlah_ambil: jumlah_ambil })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Tambahkan log untuk update manual yang berhasil dengan tipe 'M'
                addScanToHistory(selectedManualItem.barcode, { status: data.completed ? 'completed' : 'success' }, 'M');
                playSound(data.completed ? 'completed' : 'success');
                const uiData = { ...data, main_barcode: selectedManualItem.barcode, jumlah: selectedManualItem.jumlah, product_info: { ...selectedManualItem } };
                updateItemUI(uiData);
                if (data.completed) {
                    Swal.fire({ icon: 'success', title: 'Selesai!', html: `<b>${selectedManualItem.nama_produk}</b> telah selesai.`, showConfirmButton: false, timer: 1500 });
                }
                hideAllManual();
            } else {
                // Tambahkan log untuk update manual yang error dengan tipe 'M'
                addScanToHistory(selectedManualItem.barcode, { status: 'error' }, 'M');
                playSound('error');
                updateManualFeedback.innerHTML = `<div class='alert alert-danger p-2'>${data.error || 'Gagal update.'}</div>`;
            }
        })
        .catch(error => { 
            // Tambahkan log untuk error koneksi dengan tipe 'M'
            addScanToHistory(selectedManualItem.barcode, { status: 'error' }, 'M');
            playSound('error'); 
            console.error("Manual Update Error:", error); 
        })
        .finally(() => { isProcessing = false; });
    }

    // === EVENT LISTENERS ===

    pendingFilterButtons.addEventListener('click', (e) => {
        const button = e.target.closest('button[data-filter]');
        if (!button) return;
        currentStatusFilter = button.dataset.filter;
        pendingFilterButtons.querySelectorAll('button').forEach(btn => btn.classList.replace('btn-light', 'btn-outline-light'));
        button.classList.replace('btn-outline-light', 'btn-light');
        applyFilterAndSearch();
    });

    pendingSearchInput.addEventListener('input', applyFilterAndSearch);

    barcodeInput.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        if (isProcessing) return;
        const barcode = barcodeInput.value.trim();
        if (!barcode) return;
        isProcessing = true;
        barcodeInput.value = '';

        fetch(`/fullfilment/batchpicking/${window.NAMA_PICKLIST}/update_barcode/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.CSRF_TOKEN },
            body: JSON.stringify({ barcode })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Scan response:', data); // Debug log
            if (data.success) {
                // Panggil history dengan tipe 'S' (Scan)
                addScanToHistory(barcode, { status: data.completed ? 'completed' : 'success', time: data.server_time }, 'S');
                playSound(data.completed ? 'completed' : 'success');
                updateItemUI(data);
                if (data.completed) {
                    Swal.fire({ icon: 'success', title: 'Selesai!', html: `<b>${data.product_info.nama_produk}</b> telah selesai.`, showConfirmButton: false, timer: 1500 });
                }
            } else {
                // Panggil history dengan tipe 'S' (Scan)
                if (data.already_completed) {
                    // Item sudah completed - tidak perlu suara error, hanya notifikasi info
                    console.log('Item already completed, no error sound'); // Debug log
                    addScanToHistory(barcode, { status: 'overscan', time: data.server_time }, 'S');
                    Swal.fire({ icon: 'info', title: 'Item Sudah Selesai', html: data.error || 'Item ini sudah selesai diambil.' });
                } else {
                    // Error lainnya - mainkan suara error
                    console.log('Real error, playing error sound'); // Debug log
                    addScanToHistory(barcode, { status: 'error', time: data.server_time }, 'S');
                    playSound('error');
                    Swal.fire({ icon: 'error', title: 'Error', html: data.error || 'Barcode tidak valid.' });
                }
            }
        })
        .catch(error => {
            // Panggil history dengan tipe 'S' (Scan)
            addScanToHistory(barcode, { status: 'error' }, 'S');
            playSound('error');
            console.error('Scan Error:', error);
        })
        .finally(() => { isProcessing = false; barcodeInput.focus(); });
    });

    updateManualInput.addEventListener('input', () => {
        const query = updateManualInput.value.toLowerCase().trim();
        if (!query) { updateManualDropdown.style.display = 'none'; return; }
        populateManualSearchItems();
        // PERBAIKAN: Menambahkan kembali 'barcode', 'variant_produk', dan 'brand' ke dalam filter
        filteredManualItems = manualSearchItems.filter(item => 
            item.sku.toLowerCase().includes(query) ||
            item.barcode.toLowerCase().includes(query) ||
            item.nama_produk.toLowerCase().includes(query) ||
            item.variant_produk.toLowerCase().includes(query) ||
            item.brand.toLowerCase().includes(query)
        );
        selectedManualIdx = -1;
        renderDropdown();
    });

    updateManualInput.addEventListener('keydown', (e) => {
        if (updateManualDropdown.style.display !== 'block') return;
        if (e.key === 'ArrowDown') { e.preventDefault(); selectedManualIdx = (selectedManualIdx + 1) % filteredManualItems.length; renderDropdown(); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); selectedManualIdx = (selectedManualIdx - 1 + filteredManualItems.length) % filteredManualItems.length; renderDropdown(); }
        else if (e.key === 'Enter' || e.key === 'ArrowRight') { e.preventDefault(); if (selectedManualIdx > -1) selectItem(selectedManualIdx); }
    });

    qtyMinus.addEventListener('click', () => { qtyInput.value = Math.max(0, parseInt(qtyInput.value) - 1); });
    qtyPlus.addEventListener('click', () => { qtyInput.value = Math.min(maxManualQty, parseInt(qtyInput.value) + 1); });
    qtySubmit.addEventListener('click', submitQty);
    // PERBAIKAN: Mengembalikan event handler untuk ArrowRight (max qty) dan ArrowLeft (reset ke 0)
    qtyInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); submitQty(); }
        if (e.key === 'ArrowUp') { e.preventDefault(); qtyInput.value = Math.min(maxManualQty, parseInt(qtyInput.value) + 1); }
        if (e.key === 'ArrowDown') { e.preventDefault(); qtyInput.value = Math.max(0, parseInt(qtyInput.value) - 1); }
        if (e.key === 'ArrowRight') { e.preventDefault(); qtyInput.value = maxManualQty; }
        if (e.key === 'ArrowLeft') { e.preventDefault(); qtyInput.value = 0; }
    });

    // === INISIALISASI HALAMAN ===
    updateBadgeCounts();
    
    // Aktifkan tombol pending secara default
    const pendingButton = document.querySelector('#pendingFilterButtons button[data-filter="pending"]');
    if (pendingButton) {
        pendingButton.classList.replace('btn-outline-light', 'btn-light');
        // Pastikan tombol lain tidak aktif
        pendingFilterButtons.querySelectorAll('button[data-filter]:not([data-filter="pending"])').forEach(btn => {
            btn.classList.replace('btn-light', 'btn-outline-light');
        });
    }
    
    applyFilterAndSearch();
    
    // Update kartu monitoring dengan item pertama yang pending
    function updateInitialMonitoringCard() {
        const firstPendingItem = document.querySelector('#pendingItemsContainer .list-group-item[data-status="pending"]');
        if (firstPendingItem) {
            const sku = firstPendingItem.querySelector('.sku-badge')?.textContent.trim() || '---';
            const barcode = firstPendingItem.querySelector('.barcode-badge')?.textContent.replace('📊', '').trim() || '---';
            const nama = firstPendingItem.querySelector('.product-name-link')?.textContent.trim() || '---';
            const brand = firstPendingItem.querySelector('.brand')?.textContent.trim() || '---';
            const variant = firstPendingItem.querySelector('.variant-produk')?.textContent.trim() || '---';
            const jumlahAmbil = firstPendingItem.querySelector('.jumlah-ambil')?.textContent.trim() || '0';
            const jumlah = firstPendingItem.querySelector('.jumlah')?.textContent.trim() || '0';
            
            document.getElementById('monitor-sku').textContent = sku;
            document.getElementById('monitor-barcode').textContent = barcode;
            document.getElementById('monitor-nama').textContent = nama;
            document.getElementById('monitor-brand').textContent = brand;
            document.getElementById('monitor-variant').textContent = variant;
            document.getElementById('monitor-jumlah').textContent = `${jumlahAmbil} / ${jumlah}`;
        }
    }
    
    // Panggil fungsi update kartu monitoring saat halaman dimuat
    updateInitialMonitoringCard();
});


