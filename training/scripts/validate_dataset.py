#!/usr/bin/env python3
"""
Dataset Validation Tool for V-SHIELD Anti-Spoofing Pipelines.
Audits manifest CSVs and audio files for corruption, missing paths, NaNs/Infs,
duplicate entries, abnormal durations, format mismatches, and speaker leakage.
"""

import os
import sys
import argparse
import csv
import soundfile as sf
import numpy as np
from collections import defaultdict
from typing import Dict, List, Set, Any

# Add repo root to path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

def validate_dataset(manifest_csv: str, check_audio_content: bool = True, max_files_to_check: int = None) -> Dict[str, Any]:
    if not os.path.exists(manifest_csv):
        raise FileNotFoundError(f"Manifest file not found: {manifest_csv}")

    print(f"[*] Validating dataset manifest: {manifest_csv}")

    records: List[Dict[str, str]] = []
    with open(manifest_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)

    total_files = len(records)
    print(f"[*] Total records in manifest: {total_files}")

    bonafide_count = 0
    spoof_count = 0
    speakers: Set[str] = set()
    train_speakers: Set[str] = set()
    val_speakers: Set[str] = set()
    test_speakers: Set[str] = set()

    missing_files: List[str] = []
    duplicate_paths: List[str] = []
    corrupt_files: List[str] = []
    invalid_labels: List[str] = []
    missing_speakers: List[str] = []
    sample_rate_mismatches: List[str] = []
    stereo_files: List[str] = []
    zero_length_files: List[str] = []
    nan_inf_files: List[str] = []
    abnormal_duration_files: List[str] = []

    # Track distributions
    sample_rate_dist: Dict[int, int] = defaultdict(int)
    channel_dist: Dict[int, int] = defaultdict(int)
    durations: List[float] = []
    seen_paths: Set[str] = set()

    for idx, row in enumerate(records):
        fpath = row.get("file_path", "")
        spk = row.get("speaker_id", "").strip()
        raw_label = row.get("label", "").strip()
        split = (row.get("split", "") or "train").lower()

        # 1. Duplicate check
        if fpath in seen_paths:
            duplicate_paths.append(fpath)
        else:
            seen_paths.add(fpath)

        # 2. Speaker validation
        if not spk:
            missing_speakers.append(fpath)
        else:
            speakers.add(spk)
            if "train" in split:
                train_speakers.add(spk)
            elif "dev" in split or "val" in split:
                val_speakers.add(spk)
            elif "eval" in split or "test" in split:
                test_speakers.add(spk)

        # 3. Label validation (must be 0 or 1)
        if raw_label not in ("0", "1"):
            invalid_labels.append(fpath)
        else:
            if raw_label == "0":
                bonafide_count += 1
            else:
                spoof_count += 1

        # 4. Physical file checks
        if not os.path.exists(fpath):
            missing_files.append(fpath)
            continue

        # Optional in-depth audio content audit
        if check_audio_content and (max_files_to_check is None or idx < max_files_to_check):
            try:
                info = sf.info(fpath)
                sample_rate_dist[info.samplerate] += 1
                channel_dist[info.channels] += 1
                durations.append(info.duration)
                
                # Check sample rate (expected 16kHz)
                if info.samplerate != 16000:
                    sample_rate_mismatches.append(f"{fpath} ({info.samplerate}Hz)")

                # Check channels (mono expected)
                if info.channels != 1:
                    stereo_files.append(f"{fpath} ({info.channels} channels)")

                # Check duration
                if info.frames == 0 or info.duration <= 0.0:
                    zero_length_files.append(fpath)
                elif info.duration > 60.0 or info.duration < 0.2:
                    abnormal_duration_files.append(f"{fpath} ({info.duration}s)")

                # Read audio samples to verify finite values
                data, _ = sf.read(fpath, dtype="float32")
                if not np.all(np.isfinite(data)):
                    nan_inf_files.append(fpath)

            except Exception as e:
                corrupt_files.append(f"{fpath}: {str(e)}")

    # 5. Speaker Leakage Detection
    train_val_overlap = train_speakers.intersection(val_speakers)
    train_test_overlap = train_speakers.intersection(test_speakers)
    val_test_overlap = val_speakers.intersection(test_speakers)

    has_speaker_leakage = bool(train_val_overlap or train_test_overlap or val_test_overlap)

    # Calculate valid/invalid files count
    invalid_file_set = set(missing_files) | set(corrupt_files) | set(zero_length_files) | set(nan_inf_files) | set(invalid_labels)
    valid_files_count = total_files - len(invalid_file_set)

    # Duration stats
    dur_stats = {}
    if durations:
        dur_stats = {
            "min_sec": round(float(np.min(durations)), 3),
            "max_sec": round(float(np.max(durations)), 3),
            "mean_sec": round(float(np.mean(durations)), 3),
            "median_sec": round(float(np.median(durations)), 3)
        }

    is_valid = (
        len(missing_files) == 0 and
        len(corrupt_files) == 0 and
        len(duplicate_paths) == 0 and
        len(invalid_labels) == 0 and
        len(missing_speakers) == 0 and
        len(nan_inf_files) == 0 and
        len(zero_length_files) == 0 and
        not has_speaker_leakage
    )

    report_status = "PASS" if is_valid else "FAIL"

    print("\n" + "=" * 55)
    print("           V-SHIELD DATASET VALIDATION REPORT")
    print("=" * 55)
    print(f"Total files:            {total_files}")
    print(f"Valid files:            {valid_files_count}")
    print(f"Invalid / Problem files:{len(invalid_file_set)}")
    print(f"Missing files:          {len(missing_files)}")
    print(f"Corrupt / Unreadable:   {len(corrupt_files)}")
    print(f"Duplicate paths:        {len(duplicate_paths)}")
    print(f"Invalid labels:         {len(invalid_labels)}")
    print(f"Zero-length files:      {len(zero_length_files)}")
    print(f"NaN / Inf audio files:  {len(nan_inf_files)}")
    print(f"Abnormal duration:      {len(abnormal_duration_files)}")
    print("-" * 55)
    print("LABEL & SPEAKER DISTRIBUTION:")
    print(f"  Bonafide (0):         {bonafide_count}")
    print(f"  Spoof (1):            {spoof_count}")
    ratio_str = f"1 : {spoof_count / bonafide_count:.2f}" if bonafide_count > 0 else "N/A"
    print(f"  Class Ratio (B : S):  {ratio_str}")
    print(f"  Total unique speakers:{len(speakers)}")
    print(f"  Train speakers:       {len(train_speakers)}")
    print(f"  Validation speakers:  {len(val_speakers)}")
    print(f"  Test speakers:        {len(test_speakers)}")
    print("-" * 55)
    print("AUDIO SPECS DISTRIBUTION:")
    print(f"  Sample Rates:         {dict(sample_rate_dist) if sample_rate_dist else 'Not inspected'}")
    print(f"  Channels:             {dict(channel_dist) if channel_dist else 'Not inspected'}")
    if dur_stats:
        print(f"  Duration (s):         Min={dur_stats['min_sec']}, Max={dur_stats['max_sec']}, Mean={dur_stats['mean_sec']}")
    print("-" * 55)
    
    if has_speaker_leakage:
        print("SPEAKER LEAKAGE:        DETECTED (CRITICAL INTEGRITY FAILURE)")
        if train_val_overlap:
            print(f"  - Train/Val Overlap:  {list(train_val_overlap)[:5]} ({len(train_val_overlap)} speakers)")
        if train_test_overlap:
            print(f"  - Train/Test Overlap: {list(train_test_overlap)[:5]} ({len(train_test_overlap)} speakers)")
        if val_test_overlap:
            print(f"  - Val/Test Overlap:   {list(val_test_overlap)[:5]} ({len(val_test_overlap)} speakers)")
    else:
        print("SPEAKER LEAKAGE:        NONE (Verified Disjoint Partitions)")

    print(f"Status:                 {report_status}")
    print("=" * 55)

    return {
        "status": report_status,
        "total_files": total_files,
        "valid_files": valid_files_count,
        "invalid_files": len(invalid_file_set),
        "bonafide": bonafide_count,
        "spoof": spoof_count,
        "unique_speakers": len(speakers),
        "train_speakers": len(train_speakers),
        "val_speakers": len(val_speakers),
        "test_speakers": len(test_speakers),
        "missing_files": len(missing_files),
        "corrupt_files": len(corrupt_files),
        "duplicate_paths": len(duplicate_paths),
        "sample_rate_distribution": dict(sample_rate_dist),
        "channel_distribution": dict(channel_dist),
        "duration_statistics": dur_stats,
        "has_speaker_leakage": has_speaker_leakage,
    }

def main():
    parser = argparse.ArgumentParser(description="Validate V-SHIELD anti-spoof dataset manifest and audio files.")
    parser.add_argument("--manifest-csv", default="training/data/metadata/metadata.csv", help="Path to manifest CSV")
    parser.add_argument("--no-audio-check", action="store_true", help="Skip reading physical audio samples (manifest-only audit)")
    parser.add_argument("--max-check", type=int, default=None, help="Limit number of audio files checked for faster audit")

    args = parser.parse_args()
    res = validate_dataset(
        manifest_csv=args.manifest_csv,
        check_audio_content=not args.no_audio_check,
        max_files_to_check=args.max_check
    )
    if res["status"] != "PASS":
        print(f"\n[!] DATASET VALIDATION FAILED with status: {res['status']}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
