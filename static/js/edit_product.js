document.addEventListener('DOMContentLoaded', function() {
    // ========== PHOTO UPLOAD HANDLER ==========
    const photoInput = document.querySelector('input[name="photo"]');
    const productForm = document.getElementById('product-edit-form');
    
    if (photoInput && productForm) {
        const productId = window.location.pathname.split('/').filter(Boolean).pop();
        const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        photoInput.addEventListener('change', async function(e) {
            const file = e.target.files[0];
            
            if (!file) {
                return;
            }
            
            // Validate file type
            if (!file.type.startsWith('image/')) {
                Swal.fire('Error!', 'File harus berupa gambar (JPG, PNG, dll)', 'error');
                photoInput.value = '';
                return;
            }
            
            // Validate file size (max 10MB for original, will compress)
            if (file.size > 10 * 1024 * 1024) {
                Swal.fire('Error!', 'Ukuran file maksimal 10MB', 'error');
                photoInput.value = '';
                return;
            }
            
            // Show loading with progress
            Swal.fire({
                title: 'Processing...',
                html: 'Mengoptimasi dan mengupload foto<br><small>Ukuran asli: ' + (file.size / 1024).toFixed(0) + ' KB</small>',
                allowOutsideClick: false,
                didOpen: () => {
                    Swal.showLoading();
                }
            });
            
            try {
                // Compress and resize image
                // Settings optimized for product photos: 800x800 @ 85% quality
                // Result: ~100-200 KB (perfect for web!)
                const compressedFile = await compressImage(file, {
                    maxWidth: 800,    // Sweet spot for product images
                    maxHeight: 800,   // Sharp enough for zoom, small file size
                    quality: 0.85     // High quality but efficient compression
                });
                
                // Update loading text with compressed size
                Swal.update({
                    html: 'Uploading...<br><small>Ukuran asli: ' + (file.size / 1024).toFixed(0) + ' KB → ' + (compressedFile.size / 1024).toFixed(0) + ' KB</small>'
                });
                
                // Prepare FormData
                const formData = new FormData();
                formData.append('photo', compressedFile, file.name);
                
                // Upload via AJAX
                fetch(`/products/api/upload-photo/${productId}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrftoken
                    },
                    body: formData
                })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Update image preview - find the photo container
                    const photoCard = photoInput.closest('.card');
                    if (photoCard) {
                        const imgContainer = photoCard.querySelector('img');
                        const emptyPlaceholder = photoCard.querySelector('.p-4');
                        
                        if (imgContainer) {
                            // Update existing image
                            imgContainer.src = data.photo_url + '?t=' + new Date().getTime(); // Cache bust
                        } else if (emptyPlaceholder) {
                            // Replace placeholder with actual image
                            const parentDiv = emptyPlaceholder.parentElement;
                            emptyPlaceholder.remove();
                            
                            const newImgDiv = document.createElement('div');
                            newImgDiv.className = 'text-center mb-3';
                            newImgDiv.innerHTML = `
                                <img src="${data.photo_url}?t=${new Date().getTime()}" alt="Product Photo" 
                                     style="width: auto; height: auto; min-width: 150px; min-height: 150px; max-width: 100%; max-height: 250px; object-fit: contain; border-radius: 8px; border: 2px solid #e9ecef;">
                            `;
                            parentDiv.insertBefore(newImgDiv, parentDiv.firstChild);
                        }
                    }
                    
                    Swal.fire('Berhasil!', 'Foto produk berhasil diupload', 'success');
                } else {
                    Swal.fire('Error!', data.error || 'Gagal mengupload foto', 'error');
                    photoInput.value = '';
                }
            })
                .catch(error => {
                    console.error('Upload error:', error);
                    Swal.fire('Error!', 'Terjadi kesalahan saat mengupload foto', 'error');
                    photoInput.value = '';
                });
                
            } catch (error) {
                console.error('Compression error:', error);
                Swal.fire('Error!', 'Gagal memproses gambar: ' + error.message, 'error');
                photoInput.value = '';
            }
        });
    }
    
    // ========== IMAGE COMPRESSION HELPER ==========
    function compressImage(file, options = {}) {
        return new Promise((resolve, reject) => {
            const maxWidth = options.maxWidth || 1200;
            const maxHeight = options.maxHeight || 1200;
            const quality = options.quality || 0.8;
            
            const reader = new FileReader();
            reader.onload = function(e) {
                const img = new Image();
                img.onload = function() {
                    // Calculate new dimensions
                    let width = img.width;
                    let height = img.height;
                    
                    if (width > maxWidth || height > maxHeight) {
                        const ratio = Math.min(maxWidth / width, maxHeight / height);
                        width = width * ratio;
                        height = height * ratio;
                    }
                    
                    // Create canvas
                    const canvas = document.createElement('canvas');
                    canvas.width = width;
                    canvas.height = height;
                    
                    const ctx = canvas.getContext('2d');
                    
                    // Enable image smoothing for better quality
                    ctx.imageSmoothingEnabled = true;
                    ctx.imageSmoothingQuality = 'high';
                    
                    // Draw image
                    ctx.drawImage(img, 0, 0, width, height);
                    
                    // Convert to blob
                    canvas.toBlob(function(blob) {
                        if (blob) {
                            // Create file from blob
                            const compressedFile = new File([blob], file.name, {
                                type: 'image/jpeg',
                                lastModified: Date.now()
                            });
                            resolve(compressedFile);
                        } else {
                            reject(new Error('Failed to compress image'));
                        }
                    }, 'image/jpeg', quality);
                };
                img.onerror = function() {
                    reject(new Error('Failed to load image'));
                };
                img.src = e.target.result;
            };
            reader.onerror = function() {
                reject(new Error('Failed to read file'));
            };
            reader.readAsDataURL(file);
        });
    }
    
    // ========== EXTRA BARCODE HANDLER ==========
    const extraBarcodeCard = document.getElementById('extra-barcode-card');
    if (!extraBarcodeCard) {
        console.log('[Extra Barcode] Card element not found');
        return;
    }

    const productId = extraBarcodeCard.dataset.productId;
    console.log('[Extra Barcode] Initializing for product ID:', productId);
    
    if (!productId) {
        console.error('[Extra Barcode] Product ID not found in data-product-id attribute');
        return;
    }
    
    const extraBarcodeList = document.getElementById('extra-barcode-list');
    const newExtraBarcodeInput = document.getElementById('new-extra-barcode-input');
    const addExtraBarcodeBtn = document.getElementById('add-extra-barcode-btn');
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    function loadExtraBarcodes() {
        console.log('[Extra Barcode] Loading for product ID:', productId);
        
        fetch(`/products/api/extra-barcodes/${productId}/`)
            .then(response => {
                console.log('[Extra Barcode] Response status:', response.status);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('[Extra Barcode] Data received:', data);
                extraBarcodeList.innerHTML = '';
                if (!data.success || !data.extra_barcodes || data.extra_barcodes.length === 0) {
                    extraBarcodeList.innerHTML = '<tr><td colspan="2" class="text-center">Tidak ada extra barcode.</td></tr>';
                } else {
                    console.log('[Extra Barcode] Found', data.extra_barcodes.length, 'barcodes');
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
            .catch((error) => {
                console.error('[Extra Barcode] Error:', error);
                extraBarcodeList.innerHTML = `<tr><td colspan="2" class="text-center text-danger">Gagal memuat extra barcode: ${error.message}</td></tr>`;
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
