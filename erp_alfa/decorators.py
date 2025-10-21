from django.shortcuts import redirect, render
from django.contrib import messages
from django.urls import reverse
from functools import wraps # Penting untuk menjaga metadata fungsi asli

def custom_auth_and_permission_required(permission_name):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # --- Langkah 1: Periksa apakah pengguna sudah login ---
            if not request.user.is_authenticated:
                messages.info(request, "Akses Ditolak. Anda perlu login untuk melihat halaman ini.")
                # Redirect ke halaman login, dengan 'next' parameter agar bisa kembali setelah login
                return redirect(f"{reverse('login')}?next={request.path}")

            # --- Langkah 2: Jika sudah login, periksa izin (permission) ---
            if not request.user.has_perm(permission_name):
                messages.error(request, f"Akses Ditolak. Anda tidak memiliki izin '{permission_name}' yang cukup untuk melihat halaman ini.")
                # Render halaman 403 atau pesan khusus
                return render(request, '403.html', {'message': "Anda tidak memiliki izin yang cukup."}, status=403)
            
            # --- Jika semua pemeriksaan lolos, jalankan view function asli ---
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
