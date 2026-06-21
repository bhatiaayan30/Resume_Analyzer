from django.contrib import admin
from .models import Coupon

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percent', 'uses', 'max_uses', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('code',)
