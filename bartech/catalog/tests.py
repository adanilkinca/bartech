from decimal import Decimal

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from catalog.models import (
    Cocktail,
    CocktailEquipment,
    CocktailIngredient,
    Equipment,
    Glassware,
    Ingredient,
    IngredientCategory,
    MeasurementKind,
    MeasurementUnit,
    PreparationStep,
    PublicationStatus,
    RecipeLineRole,
)


class CatalogDomainTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = IngredientCategory.objects.create(name='Spirits', slug='spirits')
        cls.ingredient = Ingredient.objects.create(name='Bourbon', slug='bourbon', category=cls.category)
        cls.second_ingredient = Ingredient.objects.create(name='Lemon', slug='lemon', category=cls.category)
        cls.unit = MeasurementUnit.objects.create(code='oz', label='Ounce', kind=MeasurementKind.VOLUME)
        cls.piece = MeasurementUnit.objects.create(code='piece', label='Piece', kind=MeasurementKind.COUNT)
        cls.glass = Glassware.objects.create(name='Rocks glass', slug='rocks-glass')
        cls.equipment = Equipment.objects.create(name='Shaker', slug='shaker')
        cls.cocktail = Cocktail.objects.create(
            name='Test Cocktail', slug='test-cocktail', primary_glassware=cls.glass,
        )

    def test_cocktail_and_ingredient_creation(self):
        self.assertEqual(self.cocktail.name, 'Test Cocktail')
        self.assertEqual(self.ingredient.category, self.category)

    def test_unique_slugs_are_enforced(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Ingredient.objects.create(name='Another Bourbon', slug='bourbon', category=self.category)

    def test_publication_status_distinguishes_draft_and_published(self):
        published = Cocktail.objects.create(name='Published', slug='published', status=PublicationStatus.PUBLISHED)
        draft = Cocktail.objects.create(name='Draft', slug='draft', status=PublicationStatus.DRAFT)
        self.assertEqual(published.status, 'published')
        self.assertEqual(draft.status, 'draft')

    def test_recipe_lines_keep_decimal_and_nullable_amounts(self):
        measured = CocktailIngredient.objects.create(
            cocktail=self.cocktail, ingredient=self.ingredient, unit=self.unit,
            amount=Decimal('1.250'), sort_order=1,
        )
        unmeasured = CocktailIngredient.objects.create(
            cocktail=self.cocktail, ingredient=self.second_ingredient, unit=self.piece,
            amount=None, role=RecipeLineRole.ICE, sort_order=2,
        )
        self.assertEqual(measured.amount, Decimal('1.250'))
        self.assertIsNone(unmeasured.amount)

    def test_recipe_line_ordering_and_repeated_ingredients_are_supported(self):
        CocktailIngredient.objects.create(cocktail=self.cocktail, ingredient=self.ingredient, unit=self.unit, sort_order=2)
        CocktailIngredient.objects.create(cocktail=self.cocktail, ingredient=self.ingredient, unit=self.unit, sort_order=1, role=RecipeLineRole.GARNISH)
        lines = list(self.cocktail.recipe_ingredients.all())
        self.assertEqual([line.sort_order for line in lines], [1, 2])
        self.assertEqual(lines[0].ingredient, lines[1].ingredient)

    def test_preparation_steps_are_ordered(self):
        PreparationStep.objects.create(cocktail=self.cocktail, sort_order=2, instruction='Strain.')
        PreparationStep.objects.create(cocktail=self.cocktail, sort_order=1, instruction='Shake.')
        self.assertEqual(list(self.cocktail.preparation_steps.values_list('instruction', flat=True)), ['Shake.', 'Strain.'])

    def test_equipment_relationship_preserves_quantity_and_order(self):
        link = CocktailEquipment.objects.create(cocktail=self.cocktail, equipment=self.equipment, quantity=2, sort_order=1, note='Use a large shaker.')
        self.assertEqual(self.cocktail.equipment_items.get(), link)
        self.assertEqual(self.equipment.cocktail_uses.get(), link)

    def test_reverse_ingredient_relationship_returns_cocktails(self):
        CocktailIngredient.objects.create(cocktail=self.cocktail, ingredient=self.ingredient, unit=self.unit)
        self.assertIn(self.cocktail, [line.cocktail for line in self.ingredient.cocktail_uses.all()])

    def test_referenced_ingredient_and_unit_cannot_be_deleted(self):
        CocktailIngredient.objects.create(cocktail=self.cocktail, ingredient=self.ingredient, unit=self.unit)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.ingredient.delete()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.unit.delete()

    def test_seed_command_is_idempotent(self):
        call_command('seed_catalog')
        first_count = Cocktail.objects.count()
        call_command('seed_catalog')
        self.assertEqual(Cocktail.objects.count(), first_count)
        self.assertEqual(Cocktail.objects.filter(status=PublicationStatus.PUBLISHED).count(), 3)