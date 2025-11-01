import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser

# Import logic update dari file batchpickingv2.py
from .batchpickingv2 import update_barcode_ws, update_manual_ws

class BatchPickingV2Consumer(AsyncWebsocketConsumer): # NAMA CLASS HARUS SESUAI DENGAN YANG DIIMPORT DI ROUTING.PY
    async def connect(self):
        self.nama_batch = self.scope['url_route']['kwargs']['nama_batch']
        self.group_name = f'batchpickingv2_{self.nama_batch}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        user = self.scope.get('user', None)
        if user is None or isinstance(user, AnonymousUser):
            user = None

        if data.get('type') == 'scan_barcode':
            result = await sync_to_async(update_barcode_ws)(self.nama_batch, data.get('barcode'), user)
            if result.get('success'):
                # Broadcast update item ke semua client di grup
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        'type': 'item_update',
                        'item': result['item']
                    }
                )
            # Kirim feedback ke pengirim (client yang melakukan scan)
            await self.send(text_data=json.dumps({
                'type': 'feedback',
                'status': 'success' if result.get('success') else 'error',
                'message': result.get('error', 'Scan berhasil') if not result.get('success') else 'Scan berhasil'
            }))

        elif data.get('type') == 'manual_update':
            result = await sync_to_async(update_manual_ws)(self.nama_batch, data.get('barcode'), data.get('qty'), user)
            if result.get('success'):
                # Broadcast update item ke semua client di grup
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        'type': 'item_update',
                        'item': result['item']
                    }
                )
            # Kirim feedback ke pengirim (client yang melakukan update manual)
            await self.send(text_data=json.dumps({
                'type': 'feedback',
                'status': 'success' if result.get('success') else 'error',
                'message': result.get('error', 'Update berhasil') if not result.get('success') else 'Update berhasil'
            }))

    async def item_update(self, event):
        # Handler untuk menerima pesan 'item_update' dari channel layer dan mengirimkannya ke client
        await self.send(text_data=json.dumps({
            'type': 'update_item',
            'item': event['item']
        }))
