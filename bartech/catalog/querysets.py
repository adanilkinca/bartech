from django.db import models
from django.db.models import Q

class CocktailQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status='published')

    def with_catalog_relations(self):
        return self.select_related('primary_glassware').prefetch_related('tags', 'recipe_ingredients__ingredient')

    def with_detail_relations(self):
        return self.select_related('primary_glassware').prefetch_related(
            'tags',
            'recipe_ingredients__ingredient',
            'recipe_ingredients__unit',
            'preparation_steps',
            'equipment_items__equipment',
        )

    def search(self, query):
        if not query:
            return self
        return self.filter(
            Q(name__icontains=query) | Q(recipe_ingredients__ingredient__name__icontains=query),
        ).distinct()

    def filter_by_tag(self, slug):
        return self.filter(tags__slug=slug) if slug else self

    def filter_by_ingredient(self, slug):
        return self.filter(recipe_ingredients__ingredient__slug=slug) if slug else self

    def filter_by_glassware(self, slug):
        return self.filter(primary_glassware__slug=slug) if slug else self


class IngredientQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def search(self, query):
        return self.filter(name__icontains=query) if query else self

    def filter_by_category(self, slug):
        return self.filter(category__slug=slug) if slug else self