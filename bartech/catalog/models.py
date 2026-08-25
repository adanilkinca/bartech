from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from .image_helpers import display_image_url
from .querysets import CocktailQuerySet, IngredientQuerySet


class PublicationStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    PUBLISHED = 'published', 'Published'


class MeasurementKind(models.TextChoices):
    VOLUME = 'volume', 'Volume'
    WEIGHT = 'weight', 'Weight'
    COUNT = 'count', 'Count'
    QUALITATIVE = 'qualitative', 'Qualitative'


class RecipeLineRole(models.TextChoices):
    INGREDIENT = 'ingredient', 'Ingredient'
    GARNISH = 'garnish', 'Garnish'
    ICE = 'ice', 'Ice'


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class IngredientCategory(TimeStampedModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, unique=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('display_order', 'name')
        indexes = [models.Index(fields=('display_order', 'name'))]

    def __str__(self):
        return self.name


class Tag(TimeStampedModel):
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class MeasurementUnit(models.Model):
    code = models.CharField(max_length=30, unique=True)
    label = models.CharField(max_length=60)
    kind = models.CharField(max_length=20, choices=MeasurementKind.choices)

    class Meta:
        ordering = ('kind', 'code')

    def __str__(self):
        return self.label


class Glassware(TimeStampedModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class Equipment(TimeStampedModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('name',)
        indexes = [models.Index(fields=('is_active', 'name'))]

    def __str__(self):
        return self.name


class Ingredient(TimeStampedModel):
    objects = IngredientQuerySet.as_manager()
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        IngredientCategory,
        on_delete=models.PROTECT,
        related_name='ingredients',
    )
    primary_image = models.ImageField(upload_to='ingredients/', blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('name',)
        indexes = [
            models.Index(fields=('is_active', 'name')),
            models.Index(fields=('category', 'name')),
        ]

    def __str__(self):
        return self.name

    @property
    def primary_image_url(self):
        return display_image_url(self.primary_image)


class Cocktail(TimeStampedModel):
    objects = CocktailQuerySet.as_manager()
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True)
    short_description = models.TextField(blank=True)
    status = models.CharField(
        max_length=10,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DRAFT,
        db_index=True,
    )
    curated_order = models.PositiveIntegerField(default=0, db_index=True)
    primary_image = models.ImageField(upload_to='cocktails/', blank=True)
    primary_glassware = models.ForeignKey(
        Glassware,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='primary_cocktails',
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name='cocktails')

    class Meta:
        ordering = ('curated_order', 'name')
        indexes = [models.Index(fields=('status', 'curated_order', 'name'))]

    def __str__(self):
        return self.name

    @property
    def primary_image_url(self):
        return display_image_url(self.primary_image)


class CocktailIngredient(models.Model):
    cocktail = models.ForeignKey(
        Cocktail,
        on_delete=models.CASCADE,
        related_name='recipe_ingredients',
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name='cocktail_uses',
    )
    amount = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0'))],
    )
    unit = models.ForeignKey(
        MeasurementUnit,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='recipe_ingredients',
    )
    sort_order = models.PositiveIntegerField(default=0)
    role = models.CharField(
        max_length=12,
        choices=RecipeLineRole.choices,
        default=RecipeLineRole.INGREDIENT,
    )
    preparation_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ('sort_order', 'pk')
        indexes = [
            models.Index(fields=('cocktail', 'sort_order')),
            models.Index(fields=('ingredient', 'cocktail')),
        ]

    def __str__(self):
        return f'{self.cocktail} - {self.ingredient}'


class PreparationStep(models.Model):
    cocktail = models.ForeignKey(
        Cocktail,
        on_delete=models.CASCADE,
        related_name='preparation_steps',
    )
    sort_order = models.PositiveIntegerField(default=0)
    instruction = models.TextField()

    class Meta:
        ordering = ('sort_order', 'pk')
        constraints = [
            models.UniqueConstraint(
                fields=('cocktail', 'sort_order'),
                name='unique_preparation_step_order',
            ),
        ]

    def __str__(self):
        return f'{self.cocktail} step {self.sort_order}'


class CocktailEquipment(models.Model):
    cocktail = models.ForeignKey(
        Cocktail,
        on_delete=models.CASCADE,
        related_name='equipment_items',
    )
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.PROTECT,
        related_name='cocktail_uses',
    )
    quantity = models.PositiveIntegerField(default=1)
    sort_order = models.PositiveIntegerField(default=0)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ('sort_order', 'pk')
        indexes = [models.Index(fields=('cocktail', 'sort_order'))]

    def __str__(self):
        return f'{self.cocktail} - {self.equipment}'