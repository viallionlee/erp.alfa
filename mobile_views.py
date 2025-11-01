from django.shortcuts import render

def mobile_home(request):
    return render(request, 'mobile_home.html')
