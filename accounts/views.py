from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.contrib.auth.views import LoginView
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse

# Create your views here. 

@login_required
def profile(request):
    return render(request, 'accounts/profile.html') 

class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    extra_context = {'hide_navbar': True} 

def custom_logout(request):
    """
    Menangani proses logout dan menambahkan pesan session habis.
    """
    request.session['session_expired'] = True # Set flag bahwa sesi habis
    logout(request) # Lakukan logout Django
    # Redirect ke halaman login setelah logout
    return redirect(reverse('login')) # Menggunakan reverse untuk menghindari hardcoding URL 