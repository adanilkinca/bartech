from django.contrib import admin

from .models import (
    Cocktail,
    CocktailEquipment,
    CocktailIngredient,
    Equipment,
    Glassware,
    Ingredient,
    IngredientCategory,
    MeasurementUnit,
    PreparationStep,
    Tag,
)


class CocktailIngredientInline(admin.TabularInline):
    model = CocktailIngredient
    extra = 1
    ordering = ('sort_order', 'pk')
    autocomplete_fields = ('ingredient', 'unit')


class PreparationStepInline(admin.TabularInline):
    model = PreparationStep
    extra = 1
    ordering = ('sort_order', 'pk')


class CocktailEquipmentInline(admin.TabularInline):
    model = CocktailEquipment
    extra = 1
    ordering = ('sort_order', 'pk')
    autocomplete_fields = ('equipment',)


@admin.register(Cocktail)
class CocktailAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'curated_order', 'primary_glassware', 'updated_at')
    list_filter = ('status', 'tags')
    search_fields = ('name', 'short_description', 'recipe_ingredients__ingredient__name')
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ('tags',)
    autocomplete_fields = ('primary_glassware',)
    inlines = (CocktailIngredientInline, PreparationStepInline, CocktailEquipmentInline)


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_active', 'slug', 'updated_at')
    list_filter = ('is_active', 'category')
    search_fields = ('name', 'description', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('category',)


@admin.register(IngredientCategory)
class IngredientCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_order', 'slug')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(MeasurementUnit)
class MeasurementUnitAdmin(admin.ModelAdmin):
    list_display = ('code', 'label', 'kind')
    list_filter = ('kind',)
    search_fields = ('code', 'label')


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'slug')
    list_filter = ('is_active',)
    search_fields = ('name', 'description', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Glassware)
class GlasswareAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'description', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(CocktailIngredient)
class CocktailIngredientAdmin(admin.ModelAdmin):
    list_display = ('cocktail', 'ingredient', 'amount', 'unit', 'role', 'sort_order')
    list_filter = ('role', 'unit')
    search_fields = ('cocktail__name', 'ingredient__name')
    autocomplete_fields = ('cocktail', 'ingredient', 'unit')


@admin.register(PreparationStep)
class PreparationStepAdmin(admin.ModelAdmin):
    list_display = ('cocktail', 'sort_order', 'instruction')
    search_fields = ('cocktail__name', 'instruction')
    autocomplete_fields = ('cocktail',)


@admin.register(CocktailEquipment)
class CocktailEquipmentAdmin(admin.ModelAdmin):
    list_display = ('cocktail', 'equipment', 'quantity', 'sort_order')
    search_fields = ('cocktail__name', 'equipment__name')
    autocomplete_fields = ('cocktail', 'equipment')