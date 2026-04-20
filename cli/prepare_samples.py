#!/usr/bin/env python3
"""
Sample Preparation CLI for Stardock Podium.

Converts MP3 voice samples into the mono 16 kHz WAV format that
Kokoro TTS (and ``cli/validate_voices.py``) requires.

Typical usage:

    python cli/prepare_samples.py \
        --input-dir voices/samples/Star_Trek_Horizon

By default the script writes each ``<name>.wav`` next to the source
``<name>.mp3``. Use ``--output-dir`` to redirect, or ``--force`` to
overwrite existing WAVs. The script shells out to the ``ffmpeg``
binary (already required by ``audio_pipeline.py``) so MP3 decoding
works on every platform without extra codecs.
"""

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1
DEFAULT_MAX_DURATION_S = 19.5


def _require_ffmpeg() -> str:
    """Resolve the ffmpeg binary or abort with a clear error."""
    binary = shutil.which('ffmpeg')
    if not binary:
        raise RuntimeError(
            "ffmpeg not found on PATH. Install ffmpeg (the same binary "
            "audio_pipeline.py uses) and try again."
        )
    return binary


def convert_one(
    ffmpeg_bin: str,
    src: Path,
    dst: Path,
    *,
    force: bool = False,
    max_duration: float | None = DEFAULT_MAX_DURATION_S,
) -> bool:
    """Convert a single file to mono / 16 kHz WAV.

    When ``max_duration`` is set the output is hard-capped at that many
    seconds via ffmpeg's ``-t`` flag so the result always sits under
    Kokoro's 20 s hard validation ceiling.

    Returns True when a new WAV was produced, False when the target
    already existed and ``force`` was not set.
    """
    if dst.exists() and not force:
        logger.info("Skip (exists): %s", dst.name)
        return False

    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin,
        '-y' if force else '-n',
        '-loglevel', 'error',
        '-i', str(src),
        '-ac', str(TARGET_CHANNELS),
        '-ar', str(TARGET_SAMPLE_RATE),
        '-c:a', 'pcm_s16le',
    ]
    if max_duration is not None:
        cmd.extend(['-t', f'{max_duration:.3f}'])
    cmd.append(str(dst))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(
            "ffmpeg failed on %s: %s", src.name, result.stderr.strip())
        return False
    logger.info("Converted: %s -> %s", src.name, dst.name)
    return True


def prepare_directory(
    input_dir: Path,
    output_dir: Path | None = None,
    *,
    force: bool = False,
    max_duration: float | None = DEFAULT_MAX_DURATION_S,
) -> int:
    """Convert every ``*.mp3`` in ``input_dir`` to a matching WAV."""
    if not input_dir.is_dir():
        logger.error("Input directory not found: %s", input_dir)
        return 1

    ffmpeg_bin = _require_ffmpeg()
    targets = sorted(input_dir.glob('*.mp3'))
    if not targets:
        logger.warning("No MP3 files in %s", input_dir)
        return 0

    out_root = output_dir or input_dir
    converted = 0
    for src in targets:
        dst = out_root / (src.stem + '.wav')
        if convert_one(
                ffmpeg_bin, src, dst,
                force=force, max_duration=max_duration):
            converted += 1

    logger.info(
        "Done. Converted %d of %d file(s). Output: %s",
        converted, len(targets), out_root,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convert MP3 voice samples to Kokoro-ready mono 16 kHz WAV."
        ),
    )
    parser.add_argument(
        '--input-dir',
        default='voices/samples/Star_Trek_Horizon',
        help='Directory containing *.mp3 sample files.',
    )
    parser.add_argument(
        '--output-dir',
        default=None,
        help='Where to write WAVs (defaults to --input-dir).',
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing WAV outputs.',
    )
    parser.add_argument(
        '--max-duration',
        type=float,
        default=DEFAULT_MAX_DURATION_S,
        help=(
            'Hard cap on WAV duration in seconds (default: %.1f). Kept '
            'just under the 20 s Kokoro validator ceiling. Pass 0 to '
            'disable trimming.' % DEFAULT_MAX_DURATION_S
        ),
    )
    args = parser.parse_args()

    try:
        return prepare_directory(
            Path(args.input_dir),
            Path(args.output_dir) if args.output_dir else None,
            force=args.force,
            max_duration=args.max_duration if args.max_duration > 0 else None,
        )
    except Exception as exc:  # pragma: no cover — top-level guard
        logger.error("Sample preparation failed: %s", exc)
        return 1


if __name__ == '__main__':
    sys.exit(main())
