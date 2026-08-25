import re
from collections import defaultdict

import cloudinary.api
from django.core.management.base import BaseCommand

from catalog.image_helpers import FALLBACK_PUBLIC_ID
from catalog.models import Cocktail, Ingredient


def normalize(value):
    value = (value or '').lower().strip()
    value = re.sub(r'\.[a-z0-9]{2,5}$', '', value)
    value = re.sub(r'(?:[\s_-]+master)$', '', value)
    return re.sub(r'[^a-z0-9]+', '', value)


class Command(BaseCommand):
    help = 'Report or safely assign matching Cloudinary image assets.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write only confident matches to empty image fields.')
        parser.add_argument('--force', action='store_true', help='With --apply, replace existing image fields.')

    def handle(self, *args, **options):
        if options['force'] and not options['apply']:
            self.stdout.write(self.style.ERROR('--force requires --apply.'))
            return
        assets = self.discover_assets()
        self.stdout.write(f'Discovered assets: {len(assets)}')
        self.report_group_counts(assets)
        matches, unmatched_ingredients, unmatched_cocktails = self.match_records(assets)
        self.report_matches(matches, options['force'])
        self.report_unmatched_records(unmatched_ingredients, unmatched_cocktails)
        matched_ids = {match['asset']['public_id'] for match in matches}
        unmatched_assets = [asset for asset in assets if asset['public_id'] not in matched_ids and asset['public_id'] != FALLBACK_PUBLIC_ID]
        self.stdout.write(f'Unmatched Cloudinary assets: {len(unmatched_assets)}')
        for asset in unmatched_assets:
            self.stdout.write(f"- {asset['public_id']}")
        if options['apply']:
            self.apply_matches(matches, options['force'])
            self.stdout.write(self.style.SUCCESS('Applied confident matches.'))
        else:
            self.stdout.write('Dry run: no database changes made. Use --apply to write empty image fields.')

    def discover_assets(self):
        assets = []
        next_cursor = None
        while True:
            kwargs = {'resource_type': 'image', 'type': 'upload', 'max_results': 500}
            if next_cursor:
                kwargs['next_cursor'] = next_cursor
            response = cloudinary.api.resources(**kwargs)
            for resource in response.get('resources', []):
                public_id = resource.get('public_id', '')
                assets.append({
                    'public_id': public_id,
                    'display_name': resource.get('display_name') or resource.get('filename') or public_id.rsplit('/', 1)[-1],
                    'folder': resource.get('asset_folder') or resource.get('folder') or self.folder_from_public_id(public_id),
                    'format': resource.get('format', ''),
                    'secure_url': resource.get('secure_url', ''),
                })
            next_cursor = response.get('next_cursor')
            if not next_cursor:
                return assets

    @staticmethod
    def folder_from_public_id(public_id):
        return public_id.rsplit('/', 1)[0] if '/' in public_id else 'other'

    def report_group_counts(self, assets):
        groups = defaultdict(int)
        for asset in assets:
            folder = asset['folder'].split('/', 1)[0].lower()
            groups[folder if folder in {'cocktails', 'ingredients', 'common'} else 'other'] += 1
        self.stdout.write('Asset groups: ' + ', '.join(f'{key}={groups[key]}' for key in ('cocktails', 'ingredients', 'common', 'other')))

    def match_records(self, assets):
        matches = []
        matched_ids = set()
        for model, group in ((Ingredient, 'ingredients'), (Cocktail, 'cocktails')):
            for record in model.objects.all():
                candidates = []
                record_names = {normalize(record.name), normalize(record.slug)}
                for asset in assets:
                    if asset['public_id'] == FALLBACK_PUBLIC_ID or asset['public_id'] in matched_ids:
                        continue
                    if asset['folder'].split('/', 1)[0].lower() != group:
                        continue
                    if record_names & {normalize(asset['public_id']), normalize(asset['display_name'])}:
                        candidates.append(asset)
                if len(candidates) == 1:
                    matches.append({'model': model, 'record': record, 'asset': candidates[0]})
                    matched_ids.add(candidates[0]['public_id'])
        matched_records = {(match['model'], match['record'].pk) for match in matches}
        unmatched_ingredients = [record for record in Ingredient.objects.all() if (Ingredient, record.pk) not in matched_records]
        unmatched_cocktails = [record for record in Cocktail.objects.all() if (Cocktail, record.pk) not in matched_records]
        return matches, unmatched_ingredients, unmatched_cocktails

    def report_matches(self, matches, force):
        for model, label in ((Ingredient, 'ingredients'), (Cocktail, 'cocktails')):
            model_matches = [match for match in matches if match['model'] is model]
            self.stdout.write(f'Matched {label}: {len(model_matches)}')
            for match in model_matches:
                action = 'assign' if force or not match['record'].primary_image else 'skip existing'
                self.stdout.write(f"- {match['record'].name} -> {match['asset']['public_id']} ({action})")

    def report_unmatched_records(self, ingredients, cocktails):
        self.stdout.write(f'Unmatched DB ingredients: {len(ingredients)}')
        for record in ingredients:
            self.stdout.write(f'- {record.name}')
        self.stdout.write(f'Unmatched DB cocktails: {len(cocktails)}')
        for record in cocktails:
            self.stdout.write(f'- {record.name}')

    @staticmethod
    def apply_matches(matches, force):
        for match in matches:
            record = match['record']
            if force or not record.primary_image:
                record.primary_image = match['asset']['public_id']
                record.save(update_fields=['primary_image', 'updated_at'])