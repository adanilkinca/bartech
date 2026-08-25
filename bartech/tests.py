from decimal import Decimal

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from bartech.settings import cloudinary_config_from_env, database_config_from_env

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
            cocktail=self.cocktail, ingredient=self.second_ingredient, unit=None,
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


class CatalogPublicViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_catalog')
        cls.cocktail = Cocktail.objects.get(slug='garden-sour')
        cls.draft = Cocktail.objects.create(name='Hidden Draft', slug='hidden-draft')
        cls.ingredient = Ingredient.objects.get(slug='bourbon')
        cls.category = cls.ingredient.category
        cls.tag = cls.cocktail.tags.first()
        cls.glassware = cls.cocktail.primary_glassware

    def test_cocktail_list_shows_published_and_excludes_drafts(self):
        response = self.client.get(reverse('catalog:cocktail-list'))
        self.assertContains(response, 'Garden Sour')
        self.assertNotContains(response, 'Hidden Draft')

    def test_published_cocktail_detail_works_and_draft_returns_404(self):
        response = self.client.get(reverse('catalog:cocktail-detail', args=[self.cocktail.slug]))
        self.assertContains(response, 'Garden Sour')
        self.assertContains(response, 'Bourbon')
        self.assertEqual(
            self.client.get(reverse('catalog:cocktail-detail', args=[self.draft.slug])).status_code,
            404,
        )

    def test_ingredient_list_shows_active_ingredients_only(self):
        inactive = Ingredient.objects.create(name='Hidden Herb', slug='hidden-herb', category=self.category, is_active=False)
        response = self.client.get(reverse('catalog:ingredient-list'))
        self.assertContains(response, 'Bourbon')
        self.assertNotContains(response, inactive.name)

    def test_cocktail_search_finds_ingredient_names(self):
        response = self.client.get(reverse('catalog:cocktail-list'), {'q': 'mint'})
        self.assertContains(response, 'Garden Sour')

    def test_cocktail_tag_ingredient_and_glassware_filters(self):
        url = reverse('catalog:cocktail-list')
        self.assertContains(self.client.get(url, {'tag': self.tag.slug}), self.cocktail.name)
        self.assertContains(self.client.get(url, {'ingredient': 'bourbon'}), self.cocktail.name)
        self.assertContains(self.client.get(url, {'glassware': self.glassware.slug}), self.cocktail.name)

    def test_ingredient_category_filter_and_alphabetical_sort(self):
        response = self.client.get(reverse('catalog:ingredient-list'), {'category': self.category.slug})
        self.assertContains(response, 'Bourbon')
        response = self.client.get(reverse('catalog:cocktail-list'), {'sort': 'alphabetical'})
        names = [cocktail.name for cocktail in Cocktail.objects.published().order_by('name')]
        positions = [response.content.decode().find(name) for name in names]
        self.assertEqual(positions, sorted(positions))

    def test_pagination_preserves_filters(self):
        for index in range(7):
            extra = Cocktail.objects.create(
                name=f'Extra {index}', slug=f'extra-{index}', status=PublicationStatus.PUBLISHED,
                curated_order=index + 10,
            )
            extra.tags.add(self.tag)
        response = self.client.get(reverse('catalog:cocktail-list'), {'tag': self.tag.slug, 'page': 2})
        self.assertContains(response, f'tag={self.tag.slug}&page=1')

    def test_ingredient_detail_reverse_list_deduplicates_and_excludes_drafts(self):
        CocktailIngredient.objects.create(cocktail=self.cocktail, ingredient=self.ingredient, unit=None, sort_order=90)
        CocktailIngredient.objects.create(cocktail=self.draft, ingredient=self.ingredient, unit=None, sort_order=1)
        response = self.client.get(reverse('catalog:ingredient-detail', args=[self.ingredient.slug]))
        content = response.content.decode()
        self.assertEqual(content.count('Garden Sour'), 1)
        self.assertNotIn('Hidden Draft', content)

    def test_nullable_unit_renders_without_none(self):
        response = self.client.get(reverse('catalog:cocktail-detail', args=[self.cocktail.slug]))
        self.assertContains(response, 'Mint')
        self.assertContains(response, 'to taste')
        self.assertNotContains(response, 'None')


class EnvironmentConfigurationTests(TestCase):
    def test_database_defaults_to_sqlite_without_tidb(self):
        config = database_config_from_env({})
        self.assertEqual(config['ENGINE'], 'django.db.backends.sqlite3')

    def test_tidb_configuration_requires_tls_ca_and_builds_mysql_options(self):
        environment = {
            'USE_TIDB': 'true',
            'TIDB_HOST': 'db.example.test',
            'TIDB_DATABASE': 'bartech',
            'TIDB_USER': 'bartech-user',
            'TIDB_PASSWORD': 'not-a-real-secret',
            'TIDB_SSL_CA': 'C:/certs/ca.pem',
        }
        config = database_config_from_env(environment)
        self.assertEqual(config['ENGINE'], 'django_tidb')
        self.assertEqual(config['OPTIONS']['ssl']['ca'], 'C:/certs/ca.pem')

    def test_tidb_without_ca_is_rejected(self):
        with self.assertRaises(RuntimeError):
            database_config_from_env({
                'USE_TIDB': 'true', 'TIDB_HOST': 'host', 'TIDB_DATABASE': 'db',
                'TIDB_USER': 'user', 'TIDB_PASSWORD': 'password',
            })

    def test_cloudinary_falls_back_when_credentials_are_absent(self):
        self.assertIsNone(cloudinary_config_from_env({}))

    def test_cloudinary_configuration_is_secure_and_complete(self):
        config = cloudinary_config_from_env({
            'CLOUDINARY_CLOUD_NAME': 'example',
            'CLOUDINARY_API_KEY': '123',
            'CLOUDINARY_API_SECRET': 'not-a-real-secret',
        })
        self.assertTrue(config['SECURE'])
        self.assertEqual(config['CLOUD_NAME'], 'example')
        self.assertEqual(config['PREFIX'], '')

    def test_partial_cloudinary_configuration_is_rejected(self):
        with self.assertRaises(RuntimeError):
            cloudinary_config_from_env({'CLOUDINARY_CLOUD_NAME': 'example'})