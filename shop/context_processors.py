from .models import Category

def categories(request):
    """
    Globally provides the 'categories' context variable to all templates.
    """
    return {
        'categories': Category.objects.all()
    }
