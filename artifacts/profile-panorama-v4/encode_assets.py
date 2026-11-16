"""Format-only WebP encoding; scene generation is handled by imagegen."""
import json
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parents[2]
records = json.loads((Path(__file__).parent / 'generation-manifest.json').read_text(encoding='utf-8'))
for item in records:
    target = root / item['output']
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        with Image.open(item['generated']) as source:
            source.save(target, 'WEBP', quality=92)
    with Image.open(target) as image:
        item['width'], item['height'] = image.size
    item['bytes'] = target.stat().st_size
(Path(__file__).parent / 'assets.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Encoded and verified {len(records)} panorama assets')
