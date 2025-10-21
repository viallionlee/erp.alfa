import time
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

class SessionExpiryMessageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Cek jika user tidak login, dan sebelumnya login (session expired)
        if not request.user.is_authenticated and request.path != reverse('login'):
            if request.session.get('session_expired', False):
                messages.warning(request, "Sesi Anda telah habis. Silakan login kembali.")
                request.session['session_expired'] = False
        return self.get_response(request) 