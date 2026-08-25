from django.core.management.base import BaseCommand
from django.db import transaction

import cloudinary.api

from catalog.models import Cocktail, Ingredient, IngredientCategory, PublicationStatus


INGREDIENTS = (
    ('granulated_sugar-master', 'Granulated Sugar', 'granulated-sugar', 'Sweeteners'),
    ('raspberry_jam-master', 'Raspberry Jam', 'raspberry-jam', 'Sweeteners'),
    ('raspberry_liqueur-master', 'Raspberry Liqueur', 'raspberry-liqueur', 'Liqueurs'),
    ('sparkling_wine-master', 'Sparkling Wine', 'sparkling-wine', 'Wines'),
    ('cranberry_juice-master', 'Cranberry Juice', 'cranberry-juice', 'Juices'),
    ('peach_liqueur-master', 'Peach Liqueur', 'peach-liqueur', 'Liqueurs'),
    ('ice_cubes-master', 'Ice Cubes', 'ice-cubes', 'Ice'),
    ('lime-master', 'Lime', 'lime', 'Fruits & Herbs'),
    ('Crushed_Ice-master', 'Crushed Ice', 'crushed-ice', 'Ice'),
    ('club_soda', 'Club Soda', 'club-soda', 'Carbonated Drinks'),
    ('mint-master', 'Mint', 'mint', 'Fruits & Herbs'),
    ('white_rum-master', 'White Rum', 'white-rum', 'Spirits'),
    ('whipped-cream-master', 'Whipped Cream', 'whipped-cream', 'Dairy/Cream'),
    ('vodka-master', 'Vodka', 'vodka', 'Spirits'),
    ('strawberry-master', 'Strawberry', 'strawberry', 'Fruits & Herbs'),
    ('dark_rum-master', 'Dark Rum', 'dark-rum', 'Spirits'),
    ('irish_cream_liqueur-master', 'Irish Cream Liqueur', 'irish-cream-liqueur', 'Liqueurs'),
    ('coffee-liqueur-master', 'Coffee Liqueur', 'coffee-liqueur', 'Liqueurs'),
    ('amaretto_liqueur-master', 'Amaretto Liqueur', 'amaretto-liqueur', 'Liqueurs'),
)

COCKTAILS = (
    ('woo_woo-master', 'Woo Woo', 'woo-woo'),
    ('classic-mojito-master', 'Classic Mojito', 'classic-mojito'),
    ('dark_and_stormy-master', 'Dark and Stormy', 'dark-and-stormy'),
    ('courtesan-master', 'Courtesan', 'courtesan'),
    ('zombie-master', 'Zombie', 'zombie'),
    ('witchs_brew-master', "Witch's Brew", 'witchs-brew'),
    ('arabica-master', 'Arabica', 'arabica'),
    ('blow_job-master', 'Blow Job', 'blow-job'),
    ('vampires_kiss_martini-master', "Vampire's Kiss Martini", 'vampires-kiss-martini'),
)

CATEGORY_ORDER = {
    'Spirits': 10,
    'Liqueurs': 20,
    'Juices': 30,
    'Sweeteners': 40,
    'Carbonated Drinks': 50,
    'Fruits & Herbs': 60,
    'Dairy/Cream': 70,
    'Ice': 80,
    'Wines': 90,
}


class Command(BaseCommand):
    help = 'Plan or apply the first BarTech catalog records for existing Cloudinary assets.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Apply the proposed catalog records.')

    def handle(self, *args, **options):
        assets = self.discover_assets()
        asset_ids = {asset['public_id'] for asset in assets}
        self.write_header(asset_ids)
        self.report_ingredients(asset_ids)
        self.report_cocktails(asset_ids)
        self.report_demo_cocktails()
        if options['apply']:
            self.apply_records(asset_ids)
            self.stdout.write(self.style.SUCCESS('Cloudinary catalog bootstrap applied.'))
        else:
            self.stdout.write('Dry run: no database changes made. Review the table, then rerun with --apply.')

    def discover_assets(self):
        assets = []
        next_cursor = None
        while True:
            params = {'resource_type': 'image', 'type': 'upload', 'max_results': 500}
            if next_cursor:
                params['next_cursor'] = next_cursor
            response = cloudinary.api.resources(**params)
            assets.extend(response.get('resources', []))
            next_cursor = response.get('next_cursor')
            if not next_cursor:
                return assets

    def write_header(self, asset_ids):
        expected = {asset_id for asset_id, *_ in INGREDIENTS + tuple((asset_id, name, slug, '') for asset_id, name, slug in COCKTAILS)}
        missing = expected - asset_ids
        self.stdout.write(f'Cloudinary assets verified: {len(expected - missing)}/{len(expected)}')
        if missing:
            self.stdout.write('Missing expected assets: ' + ', '.join(sorted(missing)))
        self.stdout.write('Type | Action | Name | Slug | Category/Status | Cloudinary public ID')

    def report_ingredients(self, asset_ids):
        for public_id, name, slug, category_name in INGREDIENTS:
            existing = Ingredient.objects.filter(slug=slug).first()
            action = 'update' if existing else 'create'
            availability = '' if public_id in asset_ids else ' [asset missing]'
            self.stdout.write(f'Ingredient | {action} | {name} | {slug} | {category_name} | {public_id}{availability}')

    def report_cocktails(self, asset_ids):
        for public_id, name, slug in COCKTAILS:
            existing = Cocktail.objects.filter(slug=slug).first()
            action = 'update' if existing else 'create'
            availability = '' if public_id in asset_ids else ' [asset missing]'
            self.stdout.write(f'Cocktail | {action} | {name} | {slug} | draft | {public_id}{availability}')

    def report_demo_cocktails(self):
        target_slugs = {slug for _, _, slug in COCKTAILS}
        demos = Cocktail.objects.exclude(slug__in=target_slugs).order_by('name')
        self.stdout.write(f'Existing demo cocktails not changed: {demos.count()}')
        for cocktail in demos:
            self.stdout.write(f'- {cocktail.name} ({cocktail.slug}, {cocktail.status})')

    @staticmethod
    @transaction.atomic
    def apply_records(asset_ids):
        categories = {}
        for name, display_order in CATEGORY_ORDER.items():
            categories[name] = IngredientCategory.objects.update_or_create(
                slug=name.lower().replace('&', 'and').replace('/', '-').replace(' ', '-'),
                defaults={'name': name, 'display_order': display_order},
            )[0]
        for public_id, name, slug, category_name in INGREDIENTS:
            if public_id not in asset_ids:
                continue
            Ingredient.objects.update_or_create(
                slug=slug,
                defaults={'name': name, 'category': categories[category_name], 'primary_image': public_id, 'is_active': True},
            )
        for order, (public_id, name, slug) in enumerate(COCKTAILS, start=1):
            if public_id not in asset_ids:
                continue
            Cocktail.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'primary_image': public_id,
                    'status': PublicationStatus.DRAFT,
                    'curated_order': 100 + order,
                },
            )