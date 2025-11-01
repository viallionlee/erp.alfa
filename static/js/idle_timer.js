document.addEventListener('DOMContentLoaded', function() {
    let idleTimer;
    const idleOverlay = document.getElementById('global-idle-overlay');

    if (idleOverlay) {
        function showIdleOverlay() {
            idleOverlay.style.display = 'flex';
        }

        function hideIdleOverlay() {
            idleOverlay.style.display = 'none';
        }

        function resetIdleTimer() {
            clearTimeout(idleTimer);
            hideIdleOverlay(); // Sembunyikan overlay setiap kali ada aktivitas
            idleTimer = setTimeout(showIdleOverlay, 60000); // 1 menit = 60000 ms
        }

        // Sembunyikan overlay saat diklik
        idleOverlay.addEventListener('click', resetIdleTimer);

        // Pasang listener untuk semua aktivitas pengguna
        window.addEventListener('mousemove', resetIdleTimer, true);
        window.addEventListener('mousedown', resetIdleTimer, true);
        window.addEventListener('keydown', resetIdleTimer, true);
        window.addEventListener('scroll', resetIdleTimer, true);
        window.addEventListener('touchstart', resetIdleTimer, true);

        // Mulai timer untuk pertama kalinya
        resetIdleTimer();
    }
}); 