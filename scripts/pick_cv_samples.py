import csv, os, random, subprocess, pathlib, argparse

def get_duration_wav(path):
    # Use ffprobe to get duration in seconds
    result = subprocess.run([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return float(result.stdout.strip())
    except Exception:
        return 0.0

p = argparse.ArgumentParser()
p.add_argument('--clips_dir')
p.add_argument('--tsv')
p.add_argument('--dst')
p.add_argument('--min_sec', type=int)
p.add_argument('--max_sec', type=int)
args = p.parse_args()

wav_out = pathlib.Path(args.dst)
wav_out.mkdir(parents=True, exist_ok=True)
chosen = {}

for row in csv.DictReader(open(args.tsv, 'r', encoding='utf-8'), delimiter='\t'):
    spk = row['client_id']
    if spk in chosen: continue
    src = pathlib.Path(args.clips_dir, row['path'])
    if not src.exists(): continue
    dur = get_duration_wav(src)
    if not (args.min_sec <= dur <= args.max_sec): continue
    dst = wav_out / f"{spk}.wav"
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'quiet', '-i', str(src), '-ac', '1', '-ar', '16000', str(dst)])
    chosen[spk] = 1
    if len(chosen) == 200: break
print(f"Saved {len(chosen)} samples → {wav_out}") 