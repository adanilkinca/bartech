from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import (
    Cocktail,
    Glassware,
    Ingredient,
    IngredientCategory,
    PublicationStatus,
    Tag,
)


def cocktail_list(request):
    query = request.GET.get('q', '').strip()
    tag_slug = request.GET.get('tag', '').strip()
    ingredient_slug = request.GET.get('ingredient', '').strip()
    glassware_slug = request.GET.get('glassware', '').strip()
    sort = request.GET.get('sort', 'curated')

    cocktails = Cocktail.objects.published().with_catalog_relations().search(query)
    cocktails = cocktails.filter_by_tag(tag_slug).filter_by_ingredient(ingredient_slug).filter_by_glassware(glassware_slug)
    cocktails = cocktails.order_by('name' if sort == 'alphabetical' else 'curated_order', 'name')
    page_obj = Paginator(cocktails, 6).get_page(request.GET.get('page'))
    context = {
        'page_obj': page_obj,
        'cocktails': page_obj.object_list,
        'query': query,
        'selected_tag': tag_slug,
        'selected_ingredient': ingredient_slug,
        'selected_glassware': glassware_slug,
        'selected_sort': sort,
        'tags': Tag.objects.order_by('name'),
        'ingredients': Ingredient.objects.active().order_by('name'),
        'glasswares': Glassware.objects.order_by('name'),
        'query_params': request.GET.copy(),
    }
    context['query_params'].pop('page', None)
    return render(request, 'catalog/cocktail_list.html', context)


def cocktail_detail(request, slug):
    cocktail = get_object_or_404(
        Cocktail.objects.published().with_detail_relations(),
        slug=slug,
    )
    return render(request, 'catalog/cocktail_detail.html', {'cocktail': cocktail})


def ingredient_list(request):
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    ingredients = Ingredient.objects.active().select_related('category').search(query).filter_by_category(category_slug)
    ingredients = ingredients.order_by('name')
    page_obj = Paginator(ingredients, 12).get_page(request.GET.get('page'))
    context = {
        'page_obj': page_obj,
        'ingredients': page_obj.object_list,
        'query': query,
        'selected_category': category_slug,
        'categories': IngredientCategory.objects.order_by('display_order', 'name'),
        'query_params': request.GET.copy(),
    }
    context['query_params'].pop('page', None)
    return render(request, 'catalog/ingredient_list.html', context)


def ingredient_detail(request, slug):
    ingredient = get_object_or_404(
        Ingredient.objects.active().select_related('category'),
        slug=slug,
    )
    cocktails = Cocktail.objects.published().filter(
        recipe_ingredients__ingredient=ingredient,
    ).distinct().order_by('curated_order', 'name')
    cocktails = cocktails.select_related('primary_glassware')
    return render(request, 'catalog/ingredient_detail.html', {'ingredient': ingredient, 'cocktails': cocktails})