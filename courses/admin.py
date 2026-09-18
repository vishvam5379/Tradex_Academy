from django.contrib import admin
from .models import Category, SubCategory, Video, WatchProgress


class SubCategoryInline(admin.TabularInline):
    model = SubCategory
    extra = 1
    prepopulated_fields = {'slug': ('name',)}


class VideoInline(admin.StackedInline):
    model = Video
    extra = 1
    prepopulated_fields = {'slug': ('title',)}
    fields = (('title', 'slug', 'order'), ('video_url', 'duration', 'is_free_preview'), 'description', 'thumbnail_url')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order', 'subcategories_count', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [SubCategoryInline]
    ordering = ('order', 'name')

    def subcategories_count(self, obj):
        return obj.subcategories.count()
    subcategories_count.short_description = 'Sub-Categories'


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'badge', 'order', 'videos_count', 'total_duration_minutes')
    list_filter = ('parent',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [VideoInline]
    ordering = ('parent', 'order', 'name')

    def videos_count(self, obj):
        return obj.videos.count()
    videos_count.short_description = 'Videos'


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'sub_category', 'order', 'duration_formatted', 'is_free_preview', 'created_at')
    list_filter = ('sub_category__parent', 'sub_category', 'is_free_preview')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}
    ordering = ('sub_category', 'order')


@admin.register(WatchProgress)
class WatchProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'video', 'completed', 'updated_at')
    list_filter = ('completed', 'video__sub_category')
    search_fields = ('user__email', 'video__title')
