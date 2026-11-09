from django.db import models

# Create your models here.
import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse

class User(AbstractUser):
    # Custom user model
    
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True) # UUID for security and against ID enumeration

    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.get_full_name() or self.username

    def get_default_address(self, address_type=None):
        """Return the user's default address, optionally filtered by type."""
        qs = self.addresses.filter(is_default=True)
        if address_type:
            qs = qs.filter(address_type=address_type)
        return qs.first()
