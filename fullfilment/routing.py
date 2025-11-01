from django.urls import re_path
from .consumers import BatchPickingV2Consumer

websocket_urlpatterns = [
    re_path(r'ws/batchpicking_v2/(?P<nama_batch>[^/]+)/$', BatchPickingV2Consumer.as_asgi()),
]
