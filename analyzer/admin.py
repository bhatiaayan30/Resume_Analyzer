from django.contrib import admin
from .models import Coupon, BlogPost

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percent', 'uses', 'max_uses', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('code',)

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'read_time', 'published_at', 'is_published')
    list_filter = ('is_published', 'category')
    search_fields = ('title', 'summary', 'content')
    prepopulated_fields = {'slug': ('title',)}

