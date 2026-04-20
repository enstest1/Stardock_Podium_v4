"""One-off sanity check: every speaker in the re-parsed script resolves to a voice."""

import json
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dialogue_engine import resolve_character_voice_config, load_voice_config

cfg = load_voice_config()
script = json.load(open('episodes/ep_7ba65dfe/script.json', encoding='utf-8'))

speaker_counts = Counter()
for scene in script['scenes']:
    for line in scene['lines']:
        if line.get('type') == 'dialogue':
            speaker_counts[line.get('character', '<missing>')] += 1

resolved = 0
unresolved = []
for speaker, count in speaker_counts.most_common():
    entry = resolve_character_voice_config(speaker, cfg)
    if entry and entry.get('speaker_wav'):
        resolved += count
        wav = Path(entry['speaker_wav']).name
        print(f"  OK {count:4d}x  {speaker!r:50s} -> {wav}")
    else:
        unresolved.append((speaker, count))
        print(f"  MISS {count:4d}x  {speaker!r:50s} -> <no match>")

print()
print(
    f"Resolved: {resolved} / {sum(speaker_counts.values())} dialogue lines "
    f"across {len(speaker_counts)} unique speaker labels."
)
if unresolved:
    print(f"Unresolved labels: {[s for s, _ in unresolved]}")
    sys.exit(1)
