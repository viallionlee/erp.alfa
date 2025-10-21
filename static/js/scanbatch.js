document.addEventListener('DOMContentLoaded', function() {
    const namaBatch = window.SCANBATCH_NAMA_BATCH;
    const appDiv = document.getElementById('scanbatch-app');
    appDiv.innerHTML = `<p>Ready to scan for batch: <b>${namaBatch}</b></p>`;
    // Tambahkan logika scan sesuai kebutuhan Anda di sini
});
