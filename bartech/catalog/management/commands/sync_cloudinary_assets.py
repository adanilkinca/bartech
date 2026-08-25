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


def normalize_raw(value):
    value = (value or '').lower().strip()
    value = re.sub(r'\.[a-z0-9]{2,5}$', '', value)
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
        report, matches, unmatched_ingredients, unmatched_cocktails = self.build_report(assets)
        self.report_mapping(report)
        self.report_unmatched_records(unmatched_ingredients, unmatched_cocktails)
        self.stdout.write(f'Unmatched Cloudinary assets: {sum(row["confidence"] == "unmatched" for row in report)}')
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

    def build_report(self, assets):
        report = []
        matches = []
        matched_records = set()
        for asset in assets:
            group = asset['folder'].split('/', 1)[0].lower()
            if group not in {'ingredients', 'cocktails'}:
                continue
            model = Ingredient if group == 'ingredients' else Cocktail
            candidates = self.candidates_for_asset(asset, model)
            row = self.mapping_row(asset, candidates)
            report.append(row)
            if row['confidence'] in {'exact', 'high'} and len(candidates) == 1:
                candidate = candidates[0]
                record_key = (model, candidate['record'].pk)
                if record_key not in matched_records:
                    matches.append({'model': model, 'record': candidate['record'], 'asset': asset})
                    matched_records.add(record_key)
        unmatched_ingredients = [record for record in Ingredient.objects.all() if (Ingredient, record.pk) not in matched_records]
        unmatched_cocktails = [record for record in Cocktail.objects.all() if (Cocktail, record.pk) not in matched_records]
        return report, matches, unmatched_ingredients, unmatched_cocktails

    def candidates_for_asset(self, asset, model):
        asset_values = (asset['public_id'], asset['display_name'])
        candidates = []
        for record in model.objects.all():
            record_values = (record.name, record.slug)
            raw_match = any(normalize_raw(asset_value) == normalize_raw(record_value) for asset_value in asset_values for record_value in record_values)
            normalized_match = any(normalize(asset_value) == normalize(record_value) for asset_value in asset_values for record_value in record_values)
            possible_match = any(
                normalize(asset_value) in normalize(record_value) or normalize(record_value) in normalize(asset_value)
                for asset_value in asset_values for record_value in record_values
                if normalize(asset_value) and normalize(record_value)
            )
            if raw_match:
                score, confidence, reason = 3, 'exact', 'public/display name exactly matches DB name or slug'
            elif normalized_match:
                score, confidence, reason = 2, 'high', 'normalized name matches after separators or master suffix removal'
            elif possible_match:
                score, confidence, reason = 1, 'possible', 'one normalized value contains the other; review before assigning'
            else:
                continue
            candidates.append({'record': record, 'score': score, 'confidence': confidence, 'reason': reason})
        return sorted(candidates, key=lambda candidate: (-candidate['score'], candidate['record'].name))

    @staticmethod
    def mapping_row(asset, candidates):
        if not candidates:
            return {'asset': asset, 'candidate': 'none', 'confidence': 'unmatched', 'reason': 'no exact or conservative normalized DB candidate'}
        best_score = candidates[0]['score']
        best = [candidate for candidate in candidates if candidate['score'] == best_score]
        if len(best) > 1:
            return {
                'asset': asset,
                'candidate': 'ambiguous: ' + ', '.join(candidate['record'].name for candidate in best),
                'confidence': 'possible',
                'reason': 'multiple DB records share the best normalized match',
            }
        candidate = best[0]
        return {
            'asset': asset,
            'candidate': candidate['record'].name,
            'confidence': candidate['confidence'],
            'reason': candidate['reason'],
        }

    def report_mapping(self, report):
        for group in ('cocktails', 'ingredients'):
            self.stdout.write(f'{group.title()} mapping report')
            for row in report:
                if row['asset']['folder'].split('/', 1)[0].lower() == group:
                    asset = row['asset']
                    self.stdout.write(
                        f"{asset['public_id']} | {asset['display_name']} | {row['candidate']} | "
                        f"{row['confidence']} | {row['reason']}"
                    )

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