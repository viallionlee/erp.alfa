from django.shortcuts import render, redirect

def home(request):
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
        return redirect('mobile_home')
    return render(request, 'home.html')
