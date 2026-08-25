from django.core.management.base import BaseCommand

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
    Tag,
)


class Command(BaseCommand):
    help = 'Create or update a small original BarTech catalog dataset.'

    def handle(self, *args, **options):
        categories = self._create_categories()
        units = self._create_units()
        ingredients = self._create_ingredients(categories)
        equipment = self._create_equipment()
        glassware = self._create_glassware()
        tags = self._create_tags()
        self._create_cocktails(ingredients, units, equipment, glassware, tags)
        self.stdout.write(self.style.SUCCESS('Catalog seed data is ready.'))

    def _create_categories(self):
        names = ('Spirits', 'Liqueurs', 'Syrups', 'Juices', 'Fruits and herbs', 'Ice')
        return {
            name: IngredientCategory.objects.update_or_create(
                slug=name.lower().replace(' ', '-'),
                defaults={'name': name},
            )[0]
            for name in names
        }

    def _create_units(self):
        definitions = {
            'ml': ('Milliliter', MeasurementKind.VOLUME),
            'oz': ('Ounce', MeasurementKind.VOLUME),
            'g': ('Gram', MeasurementKind.WEIGHT),
            'piece': ('Piece', MeasurementKind.COUNT),
            'dash': ('Dash', MeasurementKind.COUNT),
            'bar spoon': ('Bar spoon', MeasurementKind.COUNT),
            'tsp': ('Teaspoon', MeasurementKind.VOLUME),
            'tbsp': ('Tablespoon', MeasurementKind.VOLUME),
        }
        return {
            code: MeasurementUnit.objects.update_or_create(
                code=code,
                defaults={'label': label, 'kind': kind},
            )[0]
            for code, (label, kind) in definitions.items()
        }

    def _create_ingredients(self, categories):
        definitions = {
            'bourbon': ('Bourbon', 'Aged American whiskey with vanilla and oak notes.', 'Spirits'),
            'coffee-liqueur': ('Coffee liqueur', 'A sweet coffee-flavored liqueur.', 'Liqueurs'),
            'simple-syrup': ('Simple syrup', 'A blend of sugar and water used to sweeten drinks.', 'Syrups'),
            'lemon-juice': ('Lemon juice', 'Freshly squeezed lemon juice.', 'Juices'),
            'lime-juice': ('Lime juice', 'Freshly squeezed lime juice.', 'Juices'),
            'mint': ('Mint', 'Fresh mint leaves for aroma and garnish.', 'Fruits and herbs'),
            'orange': ('Orange', 'Fresh orange used for aroma and garnish.', 'Fruits and herbs'),
            'ice-cubes': ('Ice cubes', 'Cold cubes of clear drinking water.', 'Ice'),
        }
        return {
            key: Ingredient.objects.update_or_create(
                slug=key,
                defaults={'name': name, 'description': description, 'category': categories[category]},
            )[0]
            for key, (name, description, category) in definitions.items()
        }

    def _create_equipment(self):
        definitions = ('Shaker', 'Bar spoon', 'Strainer', 'Jigger')
        return {
            name: Equipment.objects.update_or_create(
                slug=name.lower().replace(' ', '-'),
                defaults={'name': name},
            )[0]
            for name in definitions
        }

    def _create_glassware(self):
        definitions = ('Rocks glass', 'Coupe glass', 'Highball glass')
        return {
            name: Glassware.objects.update_or_create(
                slug=name.lower().replace(' ', '-'),
                defaults={'name': name},
            )[0]
            for name in definitions
        }

    def _create_tags(self):
        definitions = ('spirit-forward', 'sour', 'refreshing')
        return {
            name: Tag.objects.update_or_create(
                slug=name,
                defaults={'name': name.replace('-', ' ').title()},
            )[0]
            for name in definitions
        }

    def _create_cocktails(self, ingredients, units, equipment, glassware, tags):
        cocktails = {
            'oak-and-coffee': {
                'name': 'Oak and Coffee',
                'description': 'A spirit-forward bourbon drink with a gentle coffee sweetness.',
                'glass': 'Rocks glass',
                'tag': 'spirit-forward',
                'lines': [('bourbon', 'oz', '2', 'ingredient'), ('coffee-liqueur', 'oz', '0.5', 'ingredient'), ('ice-cubes', 'piece', None, 'ice')],
                'steps': ('Add the ingredients to a mixing glass with ice and stir.', 'Strain over fresh ice in the rocks glass.'),
                'equipment': ('Bar spoon', 'Strainer'),
            },
            'garden-sour': {
                'name': 'Garden Sour',
                'description': 'A bright, herbaceous sour balanced with simple syrup.',
                'glass': 'Coupe glass',
                'tag': 'sour',
                'lines': [('bourbon', 'ml', '45', 'ingredient'), ('lemon-juice', 'ml', '25', 'ingredient'), ('simple-syrup', 'ml', '15', 'ingredient'), ('mint', None, None, 'garnish'), ('ice-cubes', 'piece', None, 'ice')],
                'steps': ('Shake the bourbon, lemon juice, syrup, and ice.', 'Strain into a chilled coupe and garnish with mint.'),
                'equipment': ('Shaker', 'Strainer', 'Jigger'),
            },
            'citrus-highball': {
                'name': 'Citrus Highball',
                'description': 'A tall, easy-drinking combination of bourbon and fresh citrus.',
                'glass': 'Highball glass',
                'tag': 'refreshing',
                'lines': [('bourbon', 'oz', '1.5', 'ingredient'), ('lime-juice', 'tbsp', '2', 'ingredient'), ('simple-syrup', 'tsp', '2', 'ingredient'), ('orange', 'piece', '1', 'garnish'), ('ice-cubes', 'piece', None, 'ice')],
                'steps': ('Build the ingredients over ice in the highball glass.', 'Stir briefly and garnish with orange.'),
                'equipment': ('Jigger', 'Bar spoon'),
            },
        }
        for order, (slug, data) in enumerate(cocktails.items(), start=1):
            cocktail = Cocktail.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': data['name'],
                    'short_description': data['description'],
                    'status': PublicationStatus.PUBLISHED,
                    'curated_order': order,
                    'primary_glassware': glassware[data['glass']],
                },
            )[0]
            cocktail.tags.set([tags[data['tag']]])
            cocktail.recipe_ingredients.all().delete()
            for line_order, (ingredient, unit, amount, role) in enumerate(data['lines'], start=1):
                CocktailIngredient.objects.create(
                    cocktail=cocktail,
                    ingredient=ingredients[ingredient],
                    unit=units.get(unit),
                    amount=amount,
                    role=role,
                    sort_order=line_order,
                )
            cocktail.preparation_steps.all().delete()
            for step_order, instruction in enumerate(data['steps'], start=1):
                PreparationStep.objects.create(cocktail=cocktail, sort_order=step_order, instruction=instruction)
            cocktail.equipment_items.all().delete()
            for item_order, name in enumerate(data['equipment'], start=1):
                CocktailEquipment.objects.create(
                    cocktail=cocktail,
                    equipment=equipment[name],
                    sort_order=item_order,
                )