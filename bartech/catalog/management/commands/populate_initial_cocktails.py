from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

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


RECIPES = {
    'woo-woo': {
        'name': 'Woo Woo', 'glass': 'highball-glass', 'tags': ('fruity', 'sweet', 'vodka-based'),
        'lines': (('vodka', '45', 'ml', 'ingredient', ''), ('peach-liqueur', '15', 'ml', 'ingredient', ''), ('cranberry-juice', '60', 'ml', 'ingredient', ''), ('ice-cubes', None, None, 'ice', 'Shake with ice'), ('lime', None, 'piece', 'garnish', 'Wedge')),
        'steps': ('Add vodka, peach liqueur, cranberry juice, and ice to a shaker.', 'Shake briefly and strain over fresh ice.', 'Garnish with a lime wedge.'),
        'equipment': ('shaker', 'strainer', 'jigger'),
    },
    'classic-mojito': {
        'name': 'Classic Mojito', 'glass': 'highball-glass', 'tags': ('classic', 'refreshing', 'rum-based'),
        'lines': (('white-rum', '45', 'ml', 'ingredient', ''), ('lime-juice', '20', 'ml', 'ingredient', 'Fresh'), ('mint', '6', 'piece', 'ingredient', 'Sprigs'), ('granulated-sugar', '2', 'tsp', 'ingredient', 'Cane sugar'), ('club-soda', None, None, 'ingredient', 'To top'), ('ice-cubes', None, None, 'ice', 'Fill glass'), ('mint', None, 'piece', 'garnish', 'Sprig'), ('lime', None, 'piece', 'garnish', 'Wheel')),
        'steps': ('Gently mix the mint, sugar, and lime juice in the glass.', 'Add a splash of soda water and fill with ice.', 'Add rum, top with soda water, and stir lightly.', 'Garnish with mint and lime.'),
        'equipment': ('muddler', 'jigger', 'bar-spoon'),
    },
    'dark-and-stormy': {
        'name': 'Dark and Stormy', 'glass': 'highball-glass', 'tags': ('highball', 'refreshing', 'rum-based'),
        'lines': (('ginger-beer', '100', 'ml', 'ingredient', 'Chilled'), ('dark-rum', '60', 'ml', 'ingredient', 'Float on top'), ('ice-cubes', None, None, 'ice', 'Fill glass'), ('lime', None, 'piece', 'garnish', 'Wedge')),
        'steps': ('Fill a highball glass with ice.', 'Pour in the ginger beer.', 'Float the dark rum over the top.', 'Garnish with lime.'),
        'equipment': ('jigger', 'bar-spoon'),
    },
    'courtesan': {
        'name': 'Courtesan', 'glass': 'martini-glass', 'tags': ('fruity', 'sweet', 'layered'),
        'lines': (('vodka', '45', 'ml', 'ingredient', ''), ('raspberry-liqueur', '15', 'ml', 'ingredient', ''), ('cranberry-juice', '30', 'ml', 'ingredient', ''), ('lime-juice', '15', 'ml', 'ingredient', 'Fresh'), ('ice-cubes', None, None, 'ice', 'Shake with ice'), ('strawberry', None, 'piece', 'garnish', 'Half')),
        'steps': ('Add vodka, raspberry liqueur, cranberry juice, lime juice, and ice to a shaker.', 'Shake and strain into a chilled martini glass.', 'Garnish with a strawberry half.'),
        'equipment': ('shaker', 'strainer', 'jigger'),
    },
    'zombie': {
        'name': 'Zombie', 'glass': 'tiki-glass', 'tags': ('blended', 'strong', 'tiki', 'tropical'),
        'lines': (('dark-rum', '45', 'ml', 'ingredient', 'Jamaican-style dark rum'), ('gold-rum', '45', 'ml', 'ingredient', 'Puerto Rican-style'), ('demerara-rum', '30', 'ml', 'ingredient', ''), ('lime-juice', '20', 'ml', 'ingredient', 'Fresh'), ('falernum', '15', 'ml', 'ingredient', ''), ('grapefruit-juice', '10', 'ml', 'ingredient', 'Donn-style mix component'), ('cinnamon-syrup', '5', 'ml', 'ingredient', 'Donn-style mix component'), ('grenadine', '5', 'ml', 'ingredient', ''), ('angostura-bitters', '1', 'dash', 'ingredient', ''), ('pernod', '6', 'drop', 'ingredient', ''), ('crushed-ice', '170', 'g', 'ice', 'Cracked ice'), ('mint', None, 'piece', 'garnish', 'Leaves')),
        'steps': ('Add the liquid ingredients to a blender.', 'Add cracked ice and pulse briefly.', 'Pour into a tiki glass and add more crushed ice if needed.', 'Garnish with mint.'),
        'equipment': ('blender', 'jigger', 'bar-spoon'),
    },
    'witchs-brew': {
        'name': "Witch's Brew", 'glass': 'highball-glass', 'tags': ('fruity', 'sweet', 'vodka-based'),
        'lines': (('vodka', '45', 'ml', 'ingredient', ''), ('raspberry-liqueur', '15', 'ml', 'ingredient', ''), ('cranberry-juice', '60', 'ml', 'ingredient', ''), ('lime-juice', '15', 'ml', 'ingredient', 'Fresh'), ('ice-cubes', None, None, 'ice', 'Shake with ice'), ('strawberry', None, 'piece', 'garnish', 'Half')),
        'steps': ('Shake vodka, raspberry liqueur, cranberry juice, lime juice, and ice.', 'Strain over fresh ice in a highball glass.', 'Garnish with a strawberry half.'),
        'equipment': ('shaker', 'strainer', 'jigger'),
    },
    'arabica': {
        'name': 'Arabica', 'glass': 'rocks-glass', 'tags': ('coffee', 'dessert', 'spirit-forward'),
        'lines': (('vodka', '30', 'ml', 'ingredient', ''), ('coffee-liqueur', '30', 'ml', 'ingredient', ''), ('amaretto-liqueur', '15', 'ml', 'ingredient', ''), ('ice-cubes', None, None, 'ice', 'Serve over ice'), ('orange', None, 'piece', 'garnish', 'Expressed peel')),
        'steps': ('Add vodka, coffee liqueur, amaretto, and ice to a mixing glass.', 'Stir and strain over fresh ice in a rocks glass.', 'Garnish with orange peel.'),
        'equipment': ('bar-spoon', 'jigger', 'strainer'),
    },
    'blow-job': {
        'name': 'Blow Job', 'glass': 'shot-glass', 'tags': ('layered', 'shot', 'sweet'),
        'lines': (('amaretto-liqueur', '0.5', 'oz', 'ingredient', 'Base layer'), ('irish-cream-liqueur', '0.2', 'oz', 'ingredient', 'Layer over spoon'), ('whipped-cream', None, None, 'garnish', 'Top without mixing')),
        'steps': ('Pour amaretto into a shot glass.', 'Layer Irish cream slowly over the back of a spoon.', 'Top with whipped cream without mixing.'),
        'equipment': ('bar-spoon',),
    },
    'vampires-kiss-martini': {
        'name': "Vampire's Kiss Martini", 'glass': 'martini-glass', 'tags': ('fruity', 'sweet', 'vodka-based'),
        'lines': (('vodka', '45', 'ml', 'ingredient', ''), ('raspberry-liqueur', '15', 'ml', 'ingredient', ''), ('cranberry-juice', '30', 'ml', 'ingredient', ''), ('lime-juice', '15', 'ml', 'ingredient', 'Fresh'), ('ice-cubes', None, None, 'ice', 'Shake with ice'), ('strawberry', None, 'piece', 'garnish', 'Half')),
        'steps': ('Add vodka, raspberry liqueur, cranberry juice, lime juice, and ice to a shaker.', 'Shake and strain into a chilled martini glass.', 'Garnish with a strawberry half.'),
        'equipment': ('shaker', 'strainer', 'jigger'),
    },
}

INGREDIENTS = {
    'ginger-beer': ('Ginger Beer', 'Carbonated Drinks'), 'gold-rum': ('Gold Rum', 'Spirits'),
    'demerara-rum': ('Demerara Rum', 'Spirits'), 'falernum': ('Falernum', 'Liqueurs'),
    'grapefruit-juice': ('Grapefruit Juice', 'Juices'), 'cinnamon-syrup': ('Cinnamon Syrup', 'Sweeteners'),
    'grenadine': ('Grenadine', 'Sweeteners'), 'angostura-bitters': ('Angostura Bitters', 'Liqueurs'),
    'pernod': ('Pernod', 'Liqueurs'),
}
REFERENCE = {
    'highball-glass': (Glassware, 'Highball Glass'), 'martini-glass': (Glassware, 'Martini Glass'),
    'rocks-glass': (Glassware, 'Rocks Glass'), 'shot-glass': (Glassware, 'Shot Glass'),
    'tiki-glass': (Glassware, 'Tiki Glass'), 'shaker': (Equipment, 'Shaker'), 'strainer': (Equipment, 'Strainer'),
    'jigger': (Equipment, 'Jigger'), 'muddler': (Equipment, 'Muddler'), 'bar-spoon': (Equipment, 'Bar Spoon'),
    'blender': (Equipment, 'Blender'),
}
UNITS = {'ml': ('Milliliter', MeasurementKind.VOLUME), 'oz': ('Ounce', MeasurementKind.VOLUME), 'g': ('Gram', MeasurementKind.WEIGHT), 'piece': ('Piece', MeasurementKind.COUNT), 'dash': ('Dash', MeasurementKind.COUNT), 'drop': ('Drop', MeasurementKind.COUNT), 'tsp': ('Teaspoon', MeasurementKind.VOLUME)}


class Command(BaseCommand):
    help = 'Plan or populate provisional recipes for the first nine BarTech cocktails.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write recipes and publish the target cocktails.')

    def handle(self, *args, **options):
        self.stdout.write('Cocktail | ingredients count | steps count | glassware | equipment count | status')
        for slug, recipe in RECIPES.items():
            existing = Cocktail.objects.filter(slug=slug).first()
            status = existing.status if existing else 'draft (planned)'
            self.stdout.write(f"{recipe['name']} | {len(recipe['lines'])} | {len(recipe['steps'])} | {REFERENCE[recipe['glass']][1]} | {len(recipe['equipment'])} | {status} -> published")
        if options['apply']:
            self.apply()
            self.stdout.write(self.style.SUCCESS('Initial cocktails populated and published.'))
        else:
            self.stdout.write('Dry run: no database changes made. Review the plan, then rerun with --apply.')

    @transaction.atomic
    def apply(self):
        categories = {}
        for slug, (name, category_name) in INGREDIENTS.items():
            category_slug = category_name.lower().replace(' ', '-').replace('&', 'and')
            categories[category_name] = IngredientCategory.objects.update_or_create(slug=category_slug, defaults={'name': category_name})[0]
            Ingredient.objects.update_or_create(slug=slug, defaults={'name': name, 'category': categories[category_name], 'is_active': True})
        for slug, (model, name) in REFERENCE.items():
            defaults = {'name': name}
            if model is Equipment:
                defaults['is_active'] = True
            model.objects.update_or_create(slug=slug, defaults=defaults)
        units = {code: MeasurementUnit.objects.update_or_create(code=code, defaults={'label': label, 'kind': kind})[0] for code, (label, kind) in UNITS.items()}
        for recipe_slug, recipe in RECIPES.items():
            tags = [Tag.objects.update_or_create(slug=tag, defaults={'name': tag.replace('-', ' ').title()})[0] for tag in recipe['tags']]
            cocktail = Cocktail.objects.get(slug=recipe_slug)
            cocktail.primary_glassware = Glassware.objects.get(slug=recipe['glass'])
            cocktail.status = PublicationStatus.PUBLISHED
            cocktail.tags.set(tags)
            cocktail.save(update_fields=['primary_glassware', 'status', 'updated_at'])
            cocktail.recipe_ingredients.all().delete()
            for order, (ingredient_slug, amount, unit_code, role, note) in enumerate(recipe['lines'], start=1):
                CocktailIngredient.objects.create(cocktail=cocktail, ingredient=Ingredient.objects.get(slug=ingredient_slug), amount=Decimal(amount) if amount is not None else None, unit=units.get(unit_code), role=role, preparation_note=note, sort_order=order)
            cocktail.preparation_steps.all().delete()
            for order, instruction in enumerate(recipe['steps'], start=1):
                PreparationStep.objects.create(cocktail=cocktail, sort_order=order, instruction=instruction)
            cocktail.equipment_items.all().delete()
            for order, equipment_slug in enumerate(recipe['equipment'], start=1):
                CocktailEquipment.objects.create(cocktail=cocktail, equipment=Equipment.objects.get(slug=equipment_slug), sort_order=order)