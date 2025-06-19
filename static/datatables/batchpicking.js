// batchpicking.js
// Script ini dipindahkan dari batchpicking.html
// Pastikan file ini di-include di template HTML dengan {% static %}

function playSound(type) {
    if (type === 'completed') {
        const audio = new Audio('/static/sounds/completedsound.mp3');
        audio.play();
    } else if (type === 'success') {
        const audio = new Audio('/static/sounds/ding.mp3');
        audio.play();
    } else if (type === 'error' || type === 'fail') {
        const audio = new Audio('/static/sounds/wrong_barcode.mp3');
        audio.play();
    } else {
        // fallback
        const audio = new Audio('/static/sounds/over_scan.mp3');
        audio.play();
    }
}

function showFeedback(message, type, status_ambil, sku) {
    const feedback = document.getElementById('barcodeFeedback');
    feedback.innerHTML = message;
    feedback.className = type === 'success' ? 'alert alert-success' : 'alert alert-danger';
    if (status_ambil === 'completed') {
        playSound('completed');
        // Tampilkan modal modern jika scan completed, auto close 0.5 detik
        Swal.fire({
            icon: 'success',
            title: 'SKU Selesai!',
            html: `<b>SKU <span style='color:#1769aa;'>${sku || ''}</span> sudah semua di scan.</b>`,
            showConfirmButton: false,
            timer: 500,
            customClass: { title: 'fw-bold' }
        });
    } else {
        playSound(type);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const barcodeInput = document.getElementById('barcodeInput');
    barcodeInput.focus();
    barcodeInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            const barcode = barcodeInput.value.trim();
            if (!barcode) return;
            barcodeInput.value = '';
            fetch(`/fullfilment/batchpicking/${window.NAMA_PICKLIST}/update_barcode/`, {
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
                        // Cari baris di tabel pending
                        const row = document.querySelector(`#pendingTable tr[data-barcode='${barcode}']`);
                        if (row) {
                            row.querySelector('.jumlah-ambil').textContent = data.jumlah_ambil;
                            row.querySelector('.status-ambil').textContent = data.status_ambil;
                            row.classList.add('table-success');
                            setTimeout(() => row.classList.remove('table-success'), 1000);
                            // Jika status_ambil sudah completed, pindahkan ke tabel completed
                            if (data.status_ambil === 'completed') {
                                const completedTable = document.querySelector('#completedTable tbody');
                                completedTable.appendChild(row);
                                // Remove from pendingItems
                                const idx = pendingItems.findIndex(item => item.barcode === barcode);
                                if (idx !== -1) pendingItems.splice(idx, 1);
                            }
                        } else {
                            // Jika sudah completed, update di tabel completed jika ada
                            const rowCompleted = document.querySelector(`#completedTable tr[data-barcode='${barcode}']`);
                            if (rowCompleted) {
                                rowCompleted.querySelector('.jumlah-ambil').textContent = data.jumlah_ambil;
                                rowCompleted.querySelector('.status-ambil').textContent = data.status_ambil;
                                rowCompleted.classList.add('table-success');
                                setTimeout(() => rowCompleted.classList.remove('table-success'), 1000);
                            } else {
                                showFeedback('Barcode valid, tapi tidak ditemukan di tabel.', 'success');
                            }
                        }
                        showFeedback('Berhasil scan: ' + barcode, 'success', data.status_ambil);
                    } else {
                        showFeedback(data.error || 'Barcode tidak valid.', 'error');
                    }
                })
                .catch(() => {
                    showFeedback('Terjadi kesalahan koneksi.', 'error');
                });
        }
    });

    var readyToPickBtn = document.getElementById('showReadyToPickModal');
    if (readyToPickBtn) {
        readyToPickBtn.addEventListener('click', function (e) {
            e.preventDefault();
            var modal = new bootstrap.Modal(document.getElementById('readyToPickModal'));
            modal.show();
        });
    }

    // Tambahkan tombol Ready to Print
    const readyToPrintCell = document.getElementById('summary-ready-to-print');
    if (readyToPrintCell) {
        readyToPrintCell.innerHTML = `<a href="/fullfilment/readytoprint/?nama_batch=${window.NAMA_PICKLIST}" class="btn btn-warning btn-sm">Ready to Print</a>`;
    }

    const satBtn = document.getElementById('satBtn');
    if (satBtn) {
        satBtn.addEventListener('click', function (e) {
            e.preventDefault();
            fetch(`/fullfilment/get_sat_brands/?nama_batch=${window.NAMA_PICKLIST}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const brands = data.brands;
                        const sat_count = brands.reduce((a, b) => a + b.totalOrders, 0); // Sama dengan TOTAL ORDER SAT
                        let html = '<div class="modal fade" id="satBrandModal" tabindex="-1" aria-labelledby="satBrandModalLabel" aria-hidden="true">';
                        html += '<div class="modal-dialog"><div class="modal-content">';
                        html += '<div class="modal-header"><h5 class="modal-title" id="satBrandModalLabel">Brand SAT (order_type 1) <span class="text-primary" style="font-size:1rem; font-weight:normal;">TOTAL ORDER SAT: ' + sat_count + '</span></h5>';
                        html += '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>';
                        html += '<div class="modal-body">';
                        if (brands.length > 0) {
                            html += '<ul style="list-style:none;padding-left:0;">';
                            brands.forEach(b => {
                                html += `<li class='d-flex align-items-center mb-2'><b>${b.brand}</b> <span class='text-muted ms-2'>(Total Order: ${b.totalOrders})</span> <button class='btn btn-success btn-sm ms-3 btn-print-brand' data-brand="${encodeURIComponent(b.brand)}">Print</button></li>`;
                            });
                            html += '</ul>';
                        } else {
                            html += '<div class="text-muted">Tidak ada brand SAT (order_type 1) ditemukan.</div>';
                        }
                        html += '</div><div class="modal-footer">';
                        html += '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Tutup</button>';
                        html += '<button type="button" class="btn btn-primary" id="printAllSatBrands">PRINT SEMUA</button>';
                        html += '</div></div></div></div>';
                        document.body.insertAdjacentHTML('beforeend', html);
                        var modal = new bootstrap.Modal(document.getElementById('satBrandModal'));
                        modal.show();
                        document.getElementById('satBrandModal').addEventListener('hidden.bs.modal', function () {
                            document.getElementById('satBrandModal').remove();
                        });
                        // Print button event
                        document.querySelectorAll('.btn-print-brand').forEach(btn => {
                            btn.addEventListener('click', function () {
                                const brand = decodeURIComponent(this.getAttribute('data-brand'));
                                fetch(`/fullfilment/print_sat_brand/?brand=${encodeURIComponent(brand)}&nama_batch=${window.NAMA_PICKLIST}`)
                                    .then(resp => resp.blob())
                                    .then(blob => {
                                        const url = window.URL.createObjectURL(blob);
                                        const a = document.createElement('a');
                                        a.href = url;
                                        a.download = `print_sat_${brand}.xlsx`;
                                        document.body.appendChild(a);
                                        a.click();
                                        a.remove();
                                        window.URL.revokeObjectURL(url);
                                    });
                            });
                        });

                        // Add event listener for the PRINT SEMUA button
                        const printAllSatBrandsBtn = document.getElementById('printAllSatBrands');
                        if (printAllSatBrandsBtn) {
                            printAllSatBrandsBtn.addEventListener('click', function () {
                                fetch(`/fullfilment/print_all_sat_brands/?nama_batch=${window.NAMA_PICKLIST}`)
                                    .then(resp => resp.blob())
                                    .then(blob => {
                                        const url = window.URL.createObjectURL(blob);
                                        const a = document.createElement('a');
                                        a.href = url;
                                        a.download = 'print_sat_all.xlsx';
                                        document.body.appendChild(a);
                                        a.click();
                                        a.remove();
                                        window.URL.revokeObjectURL(url);
                                    });
                            });
                        }
                    } else {
                        alert('Gagal mengambil data brand SAT!');
                    }
                });
        });
    }

    const brandBtn = document.getElementById('brandBtn');
    if (brandBtn) {
        brandBtn.addEventListener('click', function (e) {
            e.preventDefault();
            fetch(`/fullfilment/get_brand_data/?nama_batch=${window.NAMA_PICKLIST}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const brands = data.brands;
                        const brand_count = brands.reduce((a, b) => a + b.totalOrders, 0); // Sama dengan TOTAL ORDER BRAND
                        let html = '<div class="modal fade" id="brandModal" tabindex="-1" aria-labelledby="brandModalLabel" aria-hidden="true">';
                        html += '<div class="modal-dialog"><div class="modal-content">';
                        html += '<div class="modal-header"><h5 class="modal-title" id="brandModalLabel">Brand (order_type 1 & 4) <span class="text-primary" style="font-size:1rem; font-weight:normal;">TOTAL ORDER BRAND: ' + brand_count + '</span></h5>';
                        html += '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>';
                        html += '<div class="modal-body">';
                        if (brands.length > 0) {
                            html += '<ul style="list-style:none;padding-left:0;">';
                            brands.forEach(b => {
                                html += `<li class='d-flex align-items-center mb-2'><b>${b.brand}</b> <span class='text-muted ms-2'>(Total Order: ${b.totalOrders})</span> <button class='btn btn-success btn-sm ms-3 btn-print-brand' data-brand="${encodeURIComponent(b.brand)}">Print</button></li>`;
                            });
                            html += '</ul>';
                        } else {
                            html += '<div class="text-muted">Tidak ada brand ditemukan.</div>';
                        }
                        html += '</div><div class="modal-footer">';
                        html += '<button type="button" class="btn btn-primary" id="printAllBrands">PRINT SEMUA</button>';
                        html += '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Tutup</button>';
                        html += '</div></div></div></div>';
                        document.body.insertAdjacentHTML('beforeend', html);
                        var modal = new bootstrap.Modal(document.getElementById('brandModal'));
                        modal.show();
                        document.getElementById('brandModal').addEventListener('hidden.bs.modal', function () {
                            document.getElementById('brandModal').remove();
                        });
                        // Print button event
                        document.querySelectorAll('.btn-print-brand').forEach(btn => {
                            btn.addEventListener('click', function () {
                                const brand = decodeURIComponent(this.getAttribute('data-brand'));
                                fetch(`/fullfilment/print_brand/?brand=${encodeURIComponent(brand)}&nama_batch=${window.NAMA_PICKLIST}`)
                                    .then(resp => resp.blob())
                                    .then(blob => {
                                        const url = window.URL.createObjectURL(blob);
                                        const a = document.createElement('a');
                                        a.href = url;
                                        a.download = `print_brand_${brand}.xlsx`;
                                        document.body.appendChild(a);
                                        a.click();
                                        a.remove();
                                        window.URL.revokeObjectURL(url);
                                    });
                            });
                        });
                        // Print All Brands button event
                        const printAllBrandsBtn = document.getElementById('printAllBrands');
                        if (printAllBrandsBtn) {
                            printAllBrandsBtn.addEventListener('click', function () {
                                fetch(`/fullfilment/print_all_brands/?nama_batch=${window.NAMA_PICKLIST}`)
                                    .then(resp => resp.blob())
                                    .then(blob => {
                                        const url = window.URL.createObjectURL(blob);
                                        const a = document.createElement('a');
                                        a.href = url;
                                        a.download = 'print_all_brands.xlsx';
                                        document.body.appendChild(a);
                                        a.click();
                                        a.remove();
                                        window.URL.revokeObjectURL(url);
                                    });
                            });
                        }
                    } else {
                        alert('Gagal mengambil data brand!');
                    }
                });
        });
    }
    document.addEventListener('keydown', function (e) {
        // Cek jika Ctrl+Q ditekan
        if (e.ctrlKey && (e.key === 'q' || e.key === 'Q')) {
            e.preventDefault();
            const btn = document.getElementById('generateBatchBtn');
            if (btn) btn.click();
        }
    });
    // Modal konfirmasi print MIX
    const mixBtn = document.getElementById('mixBtn');
    if (mixBtn) {
        mixBtn.addEventListener('click', function () {
            const mixCount = document.getElementById('mixCountBadge').textContent;
            Swal.fire({
                title: 'Print Order MIX',
                html: `<div class='mb-2'>Total order MIX yang akan diprint: <b>${mixCount}</b></div>` +
                    '<div class="text-muted small">Lanjutkan print semua order MIX?</div>',
                icon: 'info',
                showCancelButton: true,
                confirmButtonText: 'Print MIX',
                cancelButtonText: 'Batal',
                customClass: { confirmButton: 'btn btn-primary', cancelButton: 'btn btn-secondary' },
                buttonsStyling: false
            }).then((result) => {
                if (result.isConfirmed) {
                    // Lakukan print MIX
                    fetch(`/fullfilment/batchpicking/${window.NAMA_PICKLIST}/print_mix/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': window.CSRF_TOKEN,
                        },
                    })
                        .then(resp => resp.blob())
                        .then(blob => {
                            const url = window.URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `print_mix_${window.NAMA_PICKLIST}.xlsx`;
                            document.body.appendChild(a);
                            a.click();
                            a.remove();
                            window.URL.revokeObjectURL(url);
                        });
                }
            });
        });
    }

    const detailBtn = document.getElementById('skuNotFoundDetailBtn');
    if (detailBtn) {
        detailBtn.addEventListener('click', function () {
            fetch(`/fullfilment/batchpicking/${window.NAMA_PICKLIST}/sku_not_found_details/`)
                .then(resp => resp.json())
                .then(data => {
                    const list = data.sku_not_found_list || [];
                    const ul = document.getElementById('skuNotFoundList');
                    ul.innerHTML = '';
                    if (list.length === 0) {
                        ul.innerHTML = '<li class="text-muted">Tidak ada SKU not found.</li>';
                    } else {
                        list.forEach(sku => {
                            const li = document.createElement('li');
                            li.textContent = sku;
                            ul.appendChild(li);
                        });
                    }
                    var modal = new bootstrap.Modal(document.getElementById('skuNotFoundModal'));
                    modal.show();
                });
        });
    }

    // --- Download Pending Table as PDF ---
    const downloadBtn = document.getElementById('downloadPendingPDF');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function () {
            if (!window.jspdf || !window.jspdf.jsPDF) {
                alert('jsPDF belum dimuat. Pastikan CDN jsPDF & autotable sudah di-include di HTML.');
                return;
            }
            const doc = new window.jspdf.jsPDF({orientation: 'landscape'});
            doc.autoTable({ html: '#pendingTable', styles: { fontSize: 8 }, headStyles: { fillColor: [23, 105, 170] } });
            doc.save('pending_table.pdf');
        });
    }

    // Update summary SAT & Brand saat halaman pertama kali dimuat
    function updateSatSummary() {
        fetch(`/fullfilment/get_sat_brands/?nama_batch=${window.NAMA_PICKLIST}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const brands = data.brands;
                    const sat_count = brands.reduce((a, b) => a + b.totalOrders, 0);
                    const satBtnSummary = document.getElementById('satBtn');
                    if (satBtnSummary) satBtnSummary.textContent = sat_count;
                }
            });
    }
    function updateBrandSummary() {
        fetch(`/fullfilment/get_brand_data/?nama_batch=${window.NAMA_PICKLIST}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const brands = data.brands;
                    const brand_count = brands.reduce((a, b) => a + b.totalOrders, 0);
                    const brandBtnSummary = document.getElementById('brandBtn');
                    if (brandBtnSummary) brandBtnSummary.textContent = brand_count;
                }
            });
    }
    updateSatSummary();
    updateBrandSummary();

    // Inisialisasi DataTables jika jQuery tersedia
    if (window.jQuery) {
        $('#pendingTable').DataTable();
        $('#completedTable').DataTable();
    }
    // Fungsi sort manual (fallback jika tidak pakai DataTables)
    window.sortTable = function(tableId, col, asc = true) {
        const table = document.getElementById(tableId);
        const tbody = table.tBodies[0];
        Array.from(tbody.querySelectorAll("tr"))
            .sort((a, b) => {
                const aText = a.children[col].textContent.trim();
                const bText = b.children[col].textContent.trim();
                return (asc ? 1 : -1) * aText.localeCompare(bText, undefined, {numeric: true});
            })
            .forEach(tr => tbody.appendChild(tr));
    }
});

// --- Manual Search Autocomplete & Qty Control ---
let pendingItems = Array.from(document.querySelectorAll('#pendingTable tbody tr')).map(row => ({
    sku: row.children[0].textContent.trim(),
    barcode: row.children[1].textContent.trim(),
    nama_produk: row.children[2].textContent.trim(),
    variant_produk: row.children[3].textContent.trim(),
    brand: row.children[4].textContent.trim(),
    jumlah: parseInt(row.querySelector('.jumlah').textContent.trim()),
    jumlah_ambil: parseInt(row.querySelector('.jumlah-ambil').textContent.trim()),
    status_ambil: row.querySelector('.status-ambil').textContent.trim(),
    row: row
}));

const updateManualInput = document.getElementById('updateManualInput');
const updateManualDropdown = document.getElementById('updateManualDropdown');
const updateManualQtyControl = document.getElementById('updateManualQtyControl');
const qtyMinus = document.getElementById('qtyMinus');
const qtyPlus = document.getElementById('qtyPlus');
const qtyInput = document.getElementById('qtyInput');
const qtySubmit = document.getElementById('qtySubmit');
const updateManualFeedback = document.getElementById('updateManualFeedback');
let filteredItems = [];
let selectedIdx = -1;
let selectedItem = null;
let maxQty = 0;

function renderDropdown(items) {
    updateManualDropdown.innerHTML = '';
    if (items.length === 0) {
        updateManualDropdown.style.display = 'none';
        return;
    }
    // Do not highlight any item by default; only highlight if selectedIdx >= 0
    items.forEach((item, idx) => {
        const el = document.createElement('button');
        el.type = 'button';
        el.className = 'list-group-item list-group-item-action' + ((selectedIdx === idx && selectedIdx >= 0) ? ' active' : '');
        el.innerHTML = `<b>${item.sku}</b> | <span class='text-muted'>${item.barcode}</span> - ${item.nama_produk} <span class='text-info'>${item.variant_produk}</span> <span class='text-secondary'>${item.brand}</span>`;
        el.addEventListener('mousedown', e => {
            e.preventDefault();
            selectItem(idx);
        });
        updateManualDropdown.appendChild(el);
    });
    updateManualDropdown.style.display = 'block';
}

function filterItems(query) {
    query = query.toLowerCase();
    return pendingItems.filter(item =>
        item.sku.toLowerCase().includes(query) ||
        item.barcode.toLowerCase().includes(query) ||
        item.nama_produk.toLowerCase().includes(query) ||
        item.variant_produk.toLowerCase().includes(query) ||
        item.brand.toLowerCase().includes(query)
    );
}

function selectItem(idx) {
    selectedIdx = idx;
    selectedItem = filteredItems[idx];
    maxQty = selectedItem ? selectedItem.jumlah : 0;
    updateManualDropdown.style.display = 'none';
    updateManualInput.value = `${selectedItem.sku} | ${selectedItem.barcode} - ${selectedItem.nama_produk}`;
    showQtyControl();
}

function showQtyControl() {
    updateManualQtyControl.style.display = 'flex';
    qtyInput.value = selectedItem.jumlah_ambil;
    qtyInput.min = 0;
    qtyInput.max = maxQty;
    qtyInput.focus();
    updateManualFeedback.innerHTML = '';
}

function hideQtyControl() {
    updateManualQtyControl.style.display = 'none';
    selectedItem = null;
    selectedIdx = -1;
}

updateManualInput.addEventListener('input', function () {
    const val = updateManualInput.value.trim();
    if (!val) {
        updateManualDropdown.style.display = 'none';
        hideQtyControl();
        return;
    }
    filteredItems = filterItems(val);
    selectedIdx = -1; // No highlight by default
    renderDropdown(filteredItems);
    hideQtyControl();
});

updateManualInput.addEventListener('keydown', function (e) {
    if (updateManualDropdown.style.display === 'block') {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (filteredItems.length > 0) {
                if (selectedIdx < 0) selectedIdx = 0;
                else selectedIdx = (selectedIdx + 1) % filteredItems.length;
                renderDropdown(filteredItems);
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (filteredItems.length > 0) {
                if (selectedIdx < 0) selectedIdx = filteredItems.length - 1;
                else selectedIdx = (selectedIdx - 1 + filteredItems.length) % filteredItems.length;
                renderDropdown(filteredItems);
            }
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (selectedIdx >= 0 && filteredItems[selectedIdx]) {
                selectItem(selectedIdx);
            }
        }
    } else if (updateManualQtyControl.style.display === 'flex') {
        if (e.key === 'ArrowUp') {
            e.preventDefault();
            qtyInput.value = Math.min(maxQty, parseInt(qtyInput.value) + 1);
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            qtyInput.value = Math.max(0, parseInt(qtyInput.value) - 1);
        } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            qtyInput.value = maxQty;
        } else if (e.key === 'ArrowLeft') {
            e.preventDefault();
            qtyInput.value = 0;
        } else if (e.key === 'Enter') {
            e.preventDefault();
            submitQty();
        }
    }
});

qtyMinus.addEventListener('click', function () {
    qtyInput.value = Math.max(1, parseInt(qtyInput.value) - 1);
});
qtyPlus.addEventListener('click', function () {
    qtyInput.value = Math.min(maxQty, parseInt(qtyInput.value) + 1);
});
qtySubmit.addEventListener('click', submitQty);

qtyInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        submitQty();
    }
});

function submitQty() {
    if (!selectedItem) return;
    const jumlah_ambil = parseInt(qtyInput.value);
    if (isNaN(jumlah_ambil) || jumlah_ambil < 0 || jumlah_ambil > maxQty) {
        updateManualFeedback.innerHTML = '<div class="alert alert-danger">Jumlah tidak valid.</div>';
        playSound('error');
        return;
    }
    fetch(`/fullfilment/batchpicking/${window.NAMA_PICKLIST}/update_manual/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.CSRF_TOKEN,
        },
        body: JSON.stringify({ barcode: selectedItem.barcode, jumlah_ambil })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update row in pending table
                const row = selectedItem.row;
                row.querySelector('.jumlah-ambil').textContent = data.jumlah_ambil;
                row.querySelector('.status-ambil').textContent = data.status_ambil;
                row.classList.add('table-success');
                setTimeout(() => row.classList.remove('table-success'), 1000);
                // If completed, move to completed table
                if (data.status_ambil === 'completed') {
                    const completedTable = document.querySelector('#completedTable tbody');
                    completedTable.appendChild(row);
                    // Remove from pendingItems
                    const idx = pendingItems.findIndex(item => item.barcode === selectedItem.barcode);
                    if (idx !== -1) pendingItems.splice(idx, 1);
                }
                updateManualFeedback.innerHTML = '<div class="alert alert-success">Berhasil update jumlah ambil.</div>';
                playSound(data.status_ambil === 'completed' ? 'completed' : 'success');
                hideQtyControl();
                updateManualInput.value = '';
                qtyInput.value = 1; // reset qtyInput
                updateManualInput.focus(); // focus ke search bar
            } else {
                updateManualFeedback.innerHTML = `<div class='alert alert-danger'>${data.error || 'Gagal update.'}</div>`;
                playSound('error');
            }
        })
        .catch(() => {
            updateManualFeedback.innerHTML = '<div class="alert alert-danger">Terjadi kesalahan koneksi.</div>';
            playSound('error');
        });
}

// Sorting functionality
// Perbaikan: sort numerik benar, toggle per kolom
function sortTable(tableId, columnIndex) {
    const table = document.getElementById(tableId);
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.rows).filter(row => !row.classList.contains('summary-row'));

    // Data attribute per kolom
    const headers = table.querySelectorAll('th');
    headers.forEach((th, idx) => {
        if (idx !== columnIndex) th.removeAttribute('data-sort-order');
    });
    const header = headers[columnIndex];
    let sortOrder = header.getAttribute('data-sort-order') || 'none';
    sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
    header.setAttribute('data-sort-order', sortOrder);

    // Cek numerik: minimal 1 baris numerik
    const isNumeric = rows.some(row => !isNaN(parseFloat(row.cells[columnIndex].innerText.trim())));

    rows.sort((a, b) => {
        let aText = a.cells[columnIndex].innerText.trim();
        let bText = b.cells[columnIndex].innerText.trim();
        if (isNumeric) {
            let aNum = parseFloat(aText.replace(/[^\d.-]/g, '')) || 0;
            let bNum = parseFloat(bText.replace(/[^\d.-]/g, '')) || 0;
            return sortOrder === 'asc' ? aNum - bNum : bNum - aNum;
        } else {
            return sortOrder === 'asc' ? aText.localeCompare(bText, undefined, {numeric: true}) : bText.localeCompare(aText, undefined, {numeric: true});
        }
    });
    rows.forEach(row => tbody.appendChild(row));
}

document.querySelectorAll('th.sortable').forEach((header, index) => {
    header.addEventListener('click', () => {
        const tableId = header.closest('table').id;
        sortTable(tableId, index);
    });
});

document.addEventListener('keydown', (event) => {
    if (!selectedItem) return;
    const row = selectedItem.row;
    const qtyCell = row.querySelector('.jumlah-ambil');
    let currentQty = parseInt(qtyCell.textContent) || 0;

    switch (event.key) {
        case 'ArrowUp':
            currentQty = Math.min(currentQty + 1, maxQty);
            break;
        case 'ArrowDown':
            currentQty = Math.max(currentQty - 1, 0);
            break;
        case 'ArrowRight':
            currentQty = maxQty;
            break;
        case 'ArrowLeft':
            currentQty = 0;
            break;
        default:
            return;
    }

    qtyCell.textContent = currentQty;
    qtyInput.value = currentQty;
});

// === GLOBAL BARCODE SCANNER LISTENER ===
let barcodeBuffer = '';
let barcodeTimer = null;
let lastKeyTime = Date.now();
window.addEventListener('keydown', function(e) {
    // Abaikan jika sedang fokus di input manual
    const active = document.activeElement;
    if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA') && active !== barcodeInput) return;
    const now = Date.now();
    if (now - lastKeyTime > 100) barcodeBuffer = '';
    lastKeyTime = now;
    if (e.key === 'Enter') {
        if (barcodeBuffer.length > 0) {
            handleBarcodeScan(barcodeBuffer);
            barcodeBuffer = '';
        }
    } else if (e.key.length === 1) {
        barcodeBuffer += e.key;
    }
});
function handleBarcodeScan(barcode) {
    // Proses persis seperti input scan biasa
    fetch(`/fullfilment/batchpicking/${window.NAMA_PICKLIST}/update_barcode/`, {
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
            const row = document.querySelector(`#pendingTable tr[data-barcode='${barcode}']`);
            if (row) {
                row.querySelector('.jumlah-ambil').textContent = data.jumlah_ambil;
                row.querySelector('.status-ambil').textContent = data.status_ambil;
                row.classList.add('table-success');
                setTimeout(() => row.classList.remove('table-success'), 1000);
                if (data.status_ambil === 'completed') {
                    const completedTable = document.querySelector('#completedTable tbody');
                    completedTable.appendChild(row);
                }
            }
            showFeedback('Berhasil scan: ' + barcode, 'success', data.status_ambil);
        } else {
            showFeedback(data.error || 'Barcode tidak valid.', 'error');
        }
    })
    .catch(() => {
        showFeedback('Terjadi kesalahan koneksi.', 'error');
    });
}
// === Hapus semua event handler dan kode inline editing jumlah_ambil ===

// === Scan Barcode History ===
const scanHistory = [];
const maxHistory = 50;
function addScanHistory(barcode, status) {
  scanHistory.unshift({ barcode, status, time: new Date().toLocaleTimeString() });
  if (scanHistory.length > maxHistory) scanHistory.pop();
  renderScanHistory();
}
function renderScanHistory() {
  const el = document.getElementById('scanHistory');
  if (!el) return;
  el.innerHTML = '<div class="fw-bold mb-1">History Scan</div>' +
    '<ul class="list-group">' +
    scanHistory.map(item =>
      `<li class="list-group-item py-1 d-flex justify-content-between align-items-center">
        <span>${item.barcode}</span>
        <span class="badge ${item.status === 'success' ? 'bg-success' : 'bg-danger'}">${item.status === 'success' ? 'Berhasil' : 'Gagal'}</span>
        <span class="text-muted" style="font-size:0.8em;">${item.time}</span>
      </li>`
    ).join('') + '</ul>';
}
// Integrasi dengan proses scan barcode:
window.addScanHistory = addScanHistory;
window.renderScanHistory = renderScanHistory;


