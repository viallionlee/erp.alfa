document.addEventListener('DOMContentLoaded', function() {
    const extraBarcodeCard = document.getElementById('extra-barcode-card');
    if (!extraBarcodeCard) return;

    const productId = extraBarcodeCard.dataset.productId;
    const extraBarcodeList = document.getElementById('extra-barcode-list');
    const newExtraBarcodeInput = document.getElementById('new-extra-barcode-input');
    const addExtraBarcodeBtn = document.getElementById('add-extra-barcode-btn');
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    function loadExtraBarcodes() {
        fetch(`/products/api/extra-barcodes/${productId}/`)
            .then(response => response.json())
            .then(data => {
                extraBarcodeList.innerHTML = '';
                if (!data.success || !data.extra_barcodes || data.extra_barcodes.length === 0) {
                    extraBarcodeList.innerHTML = '<tr><td colspan="2" class="text-center">Tidak ada extra barcode.</td></tr>';
                } else {
                    data.extra_barcodes.forEach(barcode => {
                        const row = `
                            <tr data-id="${barcode.id}">
                                <td>${barcode.barcode}</td>
                                <td>
                                    <button class="btn btn-danger btn-sm delete-extra-barcode" data-id="${barcode.id}">Hapus</button>
                                </td>
                            </tr>
                        `;
                        extraBarcodeList.insertAdjacentHTML('beforeend', row);
                    });
                }
            })
            .catch(() => {
                extraBarcodeList.innerHTML = '<tr><td colspan="2" class="text-center text-danger">Gagal memuat extra barcode.</td></tr>';
            });
    }

    let isAdding = false;
    function handleAddExtraBarcode() {
        if (isAdding) return;
        addExtraBarcodeBtn.disabled = true;
        isAdding = true;

        const barcodeValue = newExtraBarcodeInput.value.trim();
        if (!barcodeValue) {
            Swal.fire('Peringatan!', 'Barcode tidak boleh kosong.', 'warning');
            addExtraBarcodeBtn.disabled = false;
            isAdding = false;
            return;
        }

        fetch(`/products/api/add-extra-barcode/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({
                product_id: productId,
                barcode_value: barcodeValue
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                Swal.fire('Berhasil!', data.message, 'success');
                newExtraBarcodeInput.value = '';
                loadExtraBarcodes();
            } else {
                Swal.fire('Error!', data.error || 'Gagal menambah barcode.', 'error');
            }
        })
        .catch(() => {
            Swal.fire('Error!', 'Terjadi kesalahan saat menambah barcode.', 'error');
        })
        .finally(() => {
            addExtraBarcodeBtn.disabled = false;
            isAdding = false;
        });
    }

    let debounceTimeout;
    addExtraBarcodeBtn.addEventListener('click', function() {
        clearTimeout(debounceTimeout);
        debounceTimeout = setTimeout(handleAddExtraBarcode, 200);
    });

    extraBarcodeList.addEventListener('click', function(event) {
        if (event.target.classList.contains('delete-extra-barcode')) {
            const barcodeId = event.target.dataset.id;
            Swal.fire({
                title: 'Anda yakin?',
                text: "Barcode ini akan dihapus permanen!",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Ya, hapus!'
            }).then((result) => {
                if (result.isConfirmed) {
                    fetch(`/products/api/delete-extra-barcode/${barcodeId}/`, {
                        method: 'POST',
                        headers: { 'X-CSRFToken': csrftoken }
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            Swal.fire('Dihapus!', data.message, 'success');
                            loadExtraBarcodes();
                        } else {
                            Swal.fire('Error!', data.error || 'Gagal menghapus barcode.', 'error');
                        }
                    })
                    .catch(() => {
                        Swal.fire('Error!', 'Terjadi kesalahan saat menghapus barcode.', 'error');
                    });
                }
            });
        }
    });

    loadExtraBarcodes();
});
