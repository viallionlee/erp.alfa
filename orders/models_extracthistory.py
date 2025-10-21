from django.db import models
from django.conf import settings

class OrdersExtractHistory(models.Model):
    extract_time = models.DateTimeField(auto_now_add=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    extracted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.file_name or 'Manual'} at {self.extract_time}"
