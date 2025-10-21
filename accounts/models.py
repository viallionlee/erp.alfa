from django.db import models
from django.contrib.auth.models import User

# Create your models here. 

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    brand_assigned = models.CharField(max_length=100, blank=True, null=True, help_text="Brand yang ditugaskan untuk user ini (jika ada)")

    def __str__(self):
        return f'{self.user.username} Profile' 