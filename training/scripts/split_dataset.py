#!/usr/bin/env python3
"""
Speaker-Aware Dataset Splitter for V-SHIELD Anti-Spoofing.
Guarantees strictly disjoint speaker subsets between Train, Validation, and Test
to prevent identity leakage and overly optimistic model evaluation.
"""

import os
import sys
import argparse
import csv
import random
from collections import defaultdict
from typing import Dict, List, Set

# Add repo root to path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

def verify_speaker_disjointness(records: List[Dict[str, str]]) -> bool:
    train_speakers: Set[str] = set()
    val_speakers: Set[str] = set()
    test_speakers: Set[str] = set()

    for r in records:
        spk = r.get("speaker_id", "").strip()
        split = (r.get("split", "") or "train").lower()
        if not spk:
            continue
        if "train" in split:
            train_speakers.add(spk)
        elif "dev" in split or "val" in split:
            val_speakers.add(spk)
        elif "eval" in split or "test" in split:
            test_speakers.add(spk)

    tv_overlap = train_speakers.intersection(val_speakers)
    tt_overlap = train_speakers.intersection(test_speakers)
    vt_overlap = val_speakers.intersection(test_speakers)

    if tv_overlap or tt_overlap or vt_overlap:
        print("[!] Speaker leakage detected:")
        if tv_overlap:
            print(f"    Train/Val Overlap: {len(tv_overlap)} speakers")
        if tt_overlap:
            print(f"    Train/Test Overlap: {len(tt_overlap)} speakers")
        if vt_overlap:
            print(f"    Val/Test Overlap: {len(vt_overlap)} speakers")
        return False

    print(f"[+] Verified disjoint speaker sets: Train={len(train_speakers)}, Val={len(val_speakers)}, Test={len(test_speakers)}")
    return True

def split_by_speaker(input_csv: str, output_csv: str, train_ratio: float = 0.70, val_ratio: float = 0.15, test_ratio: float = 0.15, seed: int = 42):
    random.seed(seed)
    assert abs((train_ratio + val_ratio + test_ratio) - 1.0) < 1e-4, "Split ratios must sum to 1.0"

    with open(input_csv, "r", encoding="utf-8") as f:
        records = list(csv.DictReader(f))

    print(f"[*] Total records loaded: {len(records)}")

    # Group records by speaker
    speaker_records: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for r in records:
        spk = r.get("speaker_id", "").strip() or "unidentified_speaker"
        speaker_records[spk].append(r)

    unique_speakers = list(speaker_records.keys())
    random.shuffle(unique_speakers)

    num_speakers = len(unique_speakers)
    num_train = int(num_speakers * train_ratio)
    num_val = int(num_speakers * val_ratio)

    train_spks = set(unique_speakers[:num_train])
    val_spks = set(unique_speakers[num_train:num_train + num_val])
    test_spks = set(unique_speakers[num_train + num_val:])

    # Strict mathematical disjointness check
    assert train_spks.isdisjoint(val_spks), "Train and Val speakers overlap!"
    assert train_spks.isdisjoint(test_spks), "Train and Test speakers overlap!"
    assert val_spks.isdisjoint(test_spks), "Val and Test speakers overlap!"

    # Re-assign splits
    split_records: List[Dict[str, str]] = []
    for spk, items in speaker_records.items():
        if spk in train_spks:
            assigned = "train"
        elif spk in val_spks:
            assigned = "val"
        else:
            assigned = "test"

        for item in items:
            item["split"] = assigned
            split_records.append(item)

    # Strict post-split verification
    if not verify_speaker_disjointness(split_records):
        raise ValueError("CRITICAL INTEGRITY FAILURE: Speaker leakage detected after splitting! Failing pipeline.")

    # Write output
    fieldnames = list(records[0].keys())
    os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(split_records)

    print(f"[+] Speaker-safe splitting completed. Output written to: {output_csv}")
    print(f"    Train: {len(train_spks)} speakers, {sum(1 for r in split_records if r['split'] == 'train')} files")
    print(f"    Val:   {len(val_spks)} speakers, {sum(1 for r in split_records if r['split'] == 'val')} files")
    print(f"    Test:  {len(test_spks)} speakers, {sum(1 for r in split_records if r['split'] == 'test')} files")

def main():
    parser = argparse.ArgumentParser(description="Split anti-spoof dataset by speaker ID.")
    parser.add_argument("--input-csv", required=True, help="Input metadata CSV")
    parser.add_argument("--output-csv", default="training/data/metadata/metadata_split.csv", help="Output split CSV")
    parser.add_argument("--train-ratio", type=float, default=0.70, help="Train speaker ratio")
    parser.add_argument("--val-ratio", type=float, default=0.15, help="Validation speaker ratio")
    parser.add_argument("--test-ratio", type=float, default=0.15, help="Test speaker ratio")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--verify-only", action="store_true", help="Only verify speaker disjointness of existing CSV")

    args = parser.parse_args()

    if args.verify_only:
        with open(args.input_csv, "r", encoding="utf-8") as f:
            records = list(csv.DictReader(f))
        ok = verify_speaker_disjointness(records)
        sys.exit(0 if ok else 1)
    else:
        split_by_speaker(
            input_csv=args.input_csv,
            output_csv=args.output_csv,
            train_ratio=args.train_ratio,
            val_ratio=args.val_ratio,
            test_ratio=args.test_ratio,
            seed=args.seed
        )

if __name__ == "__main__":
    main()
