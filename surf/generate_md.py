import json, glob

spots = []
for f in sorted(glob.glob('../spots/*.json')):
    if '_marine_areas' in f:
        continue
    d = json.load(open(f, encoding='utf-8'))
    pt = d.get('classification', {}).get('primary_type', 'unknown')
    if pt in ('sand_beach', 'unknown'):
        spots.append({
            'name': d.get('name', ''),
            'pref': d.get('area', {}).get('prefecture', ''),
            'city': d.get('area', {}).get('city', ''),
            'slug': d.get('slug', ''),
            'type': pt,
        })

lines = []
lines.append('# サーフスポット調査対象リスト')
lines.append('')
lines.append(f'施設区分が `sand_beach` または `unknown` のスポット（{len(spots)}件）。')
lines.append('Web検索で各スポットがサーフスポットかどうかを調査し、`surfer_spot` 列に ✓ を記入してください。')
lines.append('')
lines.append('| スポット名 | 都道府県 | 市町村 | スラッグ | 施設区分 | surfer_spot |')
lines.append('|-----------|---------|-------|---------|---------|------------|')
for s in spots:
    lines.append(f"| {s['name']} | {s['pref']} | {s['city']} | {s['slug']} | {s['type']} |  |")

with open('surf_spot_research.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
print(f'{len(spots)}件書き出し完了')
