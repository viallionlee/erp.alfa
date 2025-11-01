"""
ASGI config for erp_alfa project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
import django # Import django

# Pindahkan baris ini ke sini, sebelum import Django atau aplikasi lainnya
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_alfa.settings') 

# Tambahkan baris ini untuk memuat settings dan aplikasi Django
django.setup() 

# Import setelah DJANGO_SETTINGS_MODULE diatur dan Django setup
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
# import fullfilment.routing # REMOVED: File sudah dihapus


application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    # "websocket": URLRouter(
    #     fullfilment.routing.websocket_urlpatterns
    # ), # REMOVED: WebSocket routing sudah tidak diperlukan
})
