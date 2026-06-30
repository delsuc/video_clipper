#!/usr/bin/env python3
"""
Video Clipper - Extract and concatenate video segments from a source file.
Uses ffmpeg as the backend engine.
"""

import subprocess
import sys
import os
import tempfile
import re


def parse_timestamp(ts):
    """Parse a timestamp string into seconds.
    Accepts formats: MM:SS, HH:MM:SS, HH:MM:SS.fff, or plain seconds.
    """
    ts = ts.strip()
    match = re.match(r'^(\d+):(\d{1,2}):(\d{1,2})(?:\.(\d+))?$', ts)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        frac = match.group(4)
        if frac:
            s += int(frac.ljust(3, '0')[:3]) / 1000
        return h * 3600 + m * 60 + s

    match = re.match(r'^(\d{1,2}):(\d{1,2})(?:\.(\d+))?$', ts)
    if match:
        m, s = int(match.group(1)), int(match.group(2))
        frac = match.group(3)
        if frac:
            s += int(frac.ljust(3, '0')[:3]) / 1000
        return m * 60 + s

    try:
        return float(ts)
    except ValueError:
        raise ValueError(f"Invalid timestamp format: '{ts}'. Use MM:SS or HH:MM:SS.")


def format_timestamp(seconds):
    """Format seconds into HH:MM:SS.mmm."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def get_video_duration(filepath):
    """Get video duration in seconds using ffprobe."""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        filepath
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        duration = float(result.stdout.strip())
        return duration
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed: {e.stderr.strip()}")
    except FileNotFoundError:
        raise RuntimeError("ffprobe not found. Ensure ffmpeg is installed.")


def collect_segments(video_duration):
    """Interactively collect segments from the user."""
    segments = []
    print(f"\nVideo duration: {format_timestamp(video_duration)}")
    print(f"  (enter timestamps in MM:SS or HH:MM:SS format)\n")

    seg_num = 1
    while True:
        print(f"--- Segment #{seg_num} ---")
        start_input = input(f"  Start time (or 'done' to finish): ").strip()

        if start_input.lower() == 'done':
            if not segments:
                print("  No segments added. Exiting.")
                sys.exit(1)
            break

        try:
            start = parse_timestamp(start_input)
        except ValueError as e:
            print(f"  Error: {e}")
            continue

        end_input = input("  End time: ").strip()
        try:
            end = parse_timestamp(end_input)
        except ValueError as e:
            print(f"  Error: {e}")
            continue

        # Validation
        if start < 0 or end < 0:
            print("  Error: Timestamps cannot be negative.")
            continue
        if start >= video_duration or end > video_duration:
            print(f"  Error: Timestamps must be between 0 and {format_timestamp(video_duration)}.")
            continue
        if start >= end:
            print("  Error: Start time must be less than end time.")
            continue

        segments.append((start, end))
        print(f"  Added: {format_timestamp(start)} -> {format_timestamp(end)}")
        seg_num += 1

    # Auto-sort segments by start time
    segments.sort(key=lambda x: x[0])
    print(f"\nCollected {len(segments)} segment(s), sorted by start time.")

    # Check for overlaps
    for i in range(len(segments) - 1):
        if segments[i][1] > segments[i + 1][0]:
            print(f"  Warning: Segment {i+1} and {i+2} overlap.")

    return segments


def create_concat_list(temp_dir, segments):
    """Create an ffmpeg concat demuxer list file."""
    list_path = os.path.join(temp_dir, 'segments.txt')
    with open(list_path, 'w') as f:
        for start, end in segments:
            f.write(f"file 'clip_{int(start*1000)}ms_to_{int(end*1000)}ms.ts'\n")
    return list_path


def extract_segment(input_file, start, end, output_path, verbose=False):
    """Extract a single segment using ffmpeg with re-encoding for keyframe alignment."""
    duration = end - start
    # Re-encode to ensure keyframes align at exact start position.
    # Without this, stream-copy concat leaves frozen-frame gaps where segments join.
    # Audio is copied to preserve quality and save time.
    cmd = [
        'ffmpeg',
        '-y',
        '-i', input_file,
        '-ss', format_timestamp(start),
        '-to', format_timestamp(end),
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '18',
        '-pix_fmt', 'yuv420p',
        '-g', '30',
        '-keyint_min', '30',
        '-sc_threshold', '0',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        output_path
    ]
    if verbose:
        print(f"  DEBUG: ffmpeg cmd = {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if verbose:
            print(f"  DEBUG: stderr = {result.stderr[:2000]}")
        raise RuntimeError(f"ffmpeg error:\n{result.stderr}")

    # Verify actual output duration
    actual_duration = get_video_duration(output_path)
    if verbose:
        print(f"  DEBUG: requested duration = {duration:.3f}s, actual = {actual_duration:.3f}s")
    if abs(actual_duration - duration) > 0.5:
        print(f"  WARNING: Duration mismatch! Expected ~{duration:.1f}s, got {actual_duration:.1f}s")
    return output_path


def extract_and_concat(input_file, segments, output_file, verbose=False):
    """Extract segments and concatenate them using ffmpeg concat demuxer."""
    # First, extract each segment into a temp file
    temp_dir = tempfile.mkdtemp(prefix='video_clipper_')
    temp_files = []

    try:
        for i, (start, end) in enumerate(segments):
            clip_path = os.path.join(temp_dir, f'clip_{i:04d}.ts')
            temp_files.append(clip_path)
            print(f"  Extracting segment {i+1}/{len(segments)}: {format_timestamp(start)} -> {format_timestamp(end)}")
            extract_segment(input_file, start, end, clip_path, verbose=verbose)

        # Create concat list
        list_path = os.path.join(temp_dir, 'concat_list.txt')
        with open(list_path, 'w') as f:
            for clip_path in temp_files:
                f.write(f"file '{clip_path}'\n")

        # Concatenate
        print(f"  Concatenating {len(segments)} segment(s) into output...")
        cmd = [
            'ffmpeg',
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-fflags', '+genpts',
            '-i', list_path,
            '-c', 'copy',
            output_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg concat error:\n{result.stderr}")

        print(f"  Output saved to: {os.path.abspath(output_file)}")

    finally:
        # Cleanup temp files
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)
        # Also remove the concat list file
        list_path = os.path.join(temp_dir, 'concat_list.txt')
        if os.path.exists(list_path):
            os.remove(list_path)
        # Remove remaining files in temp dir
        try:
            for f in os.listdir(temp_dir):
                fp = os.path.join(temp_dir, f)
                if os.path.isfile(fp):
                    os.remove(fp)
            os.rmdir(temp_dir)
        except OSError:
            pass


def main():
    print("=" * 50)
    print("  Video Clipper - Segment Extractor")
    print("=" * 50)
    print()

    # Get input file
    input_file = input("Enter path to input video file: ").strip().strip('"')

    if not os.path.isfile(input_file):
        print(f"Error: File not found: {input_file}")
        sys.exit(1)

    print(f"\nLoading video info for: {input_file}")
    try:
        duration = get_video_duration(input_file)
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Collect segments
    segments = collect_segments(duration)

    # Get output file path
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    default_output = f"{base_name}_clipped.mp4"
    output_file = input(f"\nOutput file path [{default_output}]: ").strip().strip('"')
    if not output_file:
        output_file = default_output

    # Process
    print(f"\nProcessing...")
    try:
        extract_and_concat(input_file, segments, output_file)
        print("\nDone!")
    except RuntimeError as e:
        print(f"\nError: {e}")
        sys.exit(1)


def cli(args=None):
    """Command-line interface: video_clipper.py INPUT -o OUTPUT SEGMENT1 SEGMENT2 ...
    Each segment is START-END (e.g. 00:30-01:45).
    """
    import argparse

    parser = argparse.ArgumentParser(description='Extract and concatenate video segments.')
    parser.add_argument('input', help='Input video file')
    parser.add_argument('-o', '--output', default=None, help='Output file (default: <input>_clipped.mp4)')
    parser.add_argument('segments', nargs='*', help='Segments as START-END (e.g. 00:30-01:45). Can specify multiple.')
    parser.add_argument('--debug', action='store_true', help='Print debug info (ffmpeg commands)')

    parsed = parser.parse_args(args)

    if not os.path.isfile(parsed.input):
        print(f"Error: File not found: {parsed.input}")
        sys.exit(1)

    duration = get_video_duration(parsed.input)
    print(f"Video duration: {format_timestamp(duration)}")

    if parsed.segments:
        segments = []
        for seg in parsed.segments:
            parts = seg.split('-')
            if len(parts) != 2:
                print(f"Error: Invalid segment format '{seg}'. Use START-END (e.g. 00:30-01:45)")
                sys.exit(1)
            start = parse_timestamp(parts[0])
            end = parse_timestamp(parts[1])
            if start < 0 or end < 0:
                print(f"Error: Negative timestamps in '{seg}'.")
                sys.exit(1)
            if start >= duration or end > duration:
                print(f"Error: Segment '{seg}' out of range (video is {format_timestamp(duration)}).")
                sys.exit(1)
            if start >= end:
                print(f"Error: Start >= end in '{seg}'.")
                sys.exit(1)
            segments.append((start, end))
            print(f"  Added: {format_timestamp(start)} -> {format_timestamp(end)}")
    else:
        segments = collect_segments(duration)

    segments.sort(key=lambda x: x[0])

    if parsed.output:
        output_file = parsed.output
    else:
        base_name = os.path.splitext(os.path.basename(parsed.input))[0]
        output_file = f"{base_name}_clipped.mp4"

    print(f"\nProcessing {len(segments)} segment(s)...")
    print(f"  Output: {output_file}")

    try:
        extract_and_concat(parsed.input, segments, output_file, verbose=parsed.debug)
        print("\nDone!")
    except RuntimeError as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        cli()
    else:
        main()
