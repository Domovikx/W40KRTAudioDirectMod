"""Merge all catalog/people/*.yaml into a single catalog/merged.yaml"""
import os, glob, yaml

PEOPLE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'catalog', 'people')
OUTPUT = os.path.join(os.path.dirname(__file__), '..', '..', 'catalog', 'merged.yaml')

files = sorted(glob.glob(os.path.join(PEOPLE_DIR, '*.yaml')))
merged = {
    'generated': '2026-07-21',
    'total_characters': len(files),
    'total_phrases': 0,
    'characters': {}
}

for fp in files:
    with open(fp, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    if not data:
        continue
    key = os.path.splitext(os.path.basename(fp))[0]
    merged['characters'][key] = data
    merged['total_phrases'] += data.get('total_phrases', len(data.get('phrases', [])))

with open(OUTPUT, 'w', encoding='utf-8') as f:
    yaml.dump(merged, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

print(f'Merged {len(files)} files -> {OUTPUT}')
print(f'Total characters: {merged["total_characters"]}, total phrases: {merged["total_phrases"]}')
