from .models import Category


def sidebar_categories(request):
    """Context processor that injects the complete sidebar category hierarchy."""
    try:
        categories = Category.objects.prefetch_related('subcategories').all().order_by('order', 'name')
    except Exception:
        categories = []
    return {
        'sidebar_categories': categories
    }

