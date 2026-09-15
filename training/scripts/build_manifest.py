#!/usr/bin/env python3
"""
Manifest Generator for V-SHIELD Anti-Spoofing Datasets.
Scans raw dataset directories via the appropriate adapter and builds standardized CSV metadata.
"""

import os
import sys
import argparse
import csv
import soundfile as sf
from typing import List

# Add repo root to path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from training.datasets import get_dataset_adapter, AudioSampleRecord

def build_manifest(dataset_name: str, dataset_root: str, output_csv: str, splits: List[str], scan_audio_info: bool = False):
    print(f"[*] Initializing adapter for dataset: {dataset_name}")
    adapter = get_dataset_adapter(dataset_name)

    if not os.path.exists(dataset_root):
        raise FileNotFoundError(f"Dataset root directory does not exist: {dataset_root}")

    all_records: List[AudioSampleRecord] = []

    for split in splits:
        print(f"[*] Parsing split '{split}' from {dataset_root}...")
        try:
            split_records = adapter.parse_split(dataset_root, split)
            print(f"    Found {len(split_records)} records in split '{split}'.")
            all_records.extend(split_records)
        except Exception as e:
            print(f"[!] FATAL: Failed parsing split '{split}' under '{dataset_root}': {e}")
            raise

    if not all_records:
        raise ValueError(f"No records parsed from {dataset_root}. Check dataset structure and protocol files.")

    # Optionally scan audio headers with soundfile.info (lazy metadata inspection)
    if scan_audio_info:
        print(f"[*] Inspecting audio headers for {len(all_records)} files (sample rate & duration)...")
        for idx, rec in enumerate(all_records):
            if os.path.exists(rec.file_path):
                try:
                    info = sf.info(rec.file_path)
                    rec.sample_rate = info.samplerate
                    rec.duration_seconds = round(info.duration, 3)
                    rec.num_samples = info.frames
                except Exception:
                    pass
            if (idx + 1) % 5000 == 0:
                print(f"    Processed {idx + 1}/{len(all_records)} audio headers...")

    os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)

    # Write standardized CSV
    fieldnames = [
        "file_path", "speaker_id", "label", "label_name", 
        "attack_type", "dataset", "split", 
        "sample_rate", "duration_seconds", "num_samples"
    ]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in all_records:
            writer.writerow(rec.to_dict())

    # Summary Statistics
    total = len(all_records)
    bonafide = sum(1 for r in all_records if r.label == 0)
    spoof = sum(1 for r in all_records if r.label == 1)
    unique_speakers = len({r.speaker_id for r in all_records})

    print(f"\n[+] Manifest created successfully at: {output_csv}")
    print(f"    Total files: {total}")
    print(f"    Bonafide (0): {bonafide} ({round((bonafide / total) * 100, 2)}%)")
    print(f"    Spoof (1):    {spoof} ({round((spoof / total) * 100, 2)}%)")
    print(f"    Unique Speakers: {unique_speakers}")

def main():
    parser = argparse.ArgumentParser(description="Generate V-SHIELD standardized anti-spoof dataset manifest.")
    parser.add_argument("--dataset", "--dataset-name", dest="dataset_name", default="ASVspoof2019_LA",
                        help="Dataset identifier (e.g., asvspoof2019, ASVspoof2019_LA, ASVspoof2021_DF, in_the_wild)")
    parser.add_argument("--root", "--dataset-root", dest="dataset_root",
                        default=os.environ.get("VSHIELD_DATASET_ROOT", "training/data/raw/ASVspoof2019_LA"),
                        help="Path to raw dataset root folder (supports env var VSHIELD_DATASET_ROOT)")
    parser.add_argument("--output-csv", default="training/data/metadata/metadata.csv",
                        help="Path to output manifest CSV")
    parser.add_argument("--splits", nargs="+", default=["train", "dev", "eval"],
                        help="List of splits to parse (e.g., train dev eval)")
    parser.add_argument("--scan-audio-info", action="store_true",
                        help="Inspect audio headers for duration and sample rate")

    args = parser.parse_args()

    root_path = args.dataset_root
    if not os.path.isabs(root_path):
        root_path = os.path.join(repo_root, root_path)

    out_csv = args.output_csv
    if not os.path.isabs(out_csv):
        out_csv = os.path.join(repo_root, out_csv)

    try:
        build_manifest(
            dataset_name=args.dataset_name,
            dataset_root=root_path,
            output_csv=out_csv,
            splits=args.splits,
            scan_audio_info=args.scan_audio_info
        )
    except Exception as e:
        print(f"\n[!] DATASET DISCOVERY ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
