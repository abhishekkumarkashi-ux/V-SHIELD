import os
import glob
import json
import librosa
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import yaml

def load_config():
    with open("ml/config.yaml", "r") as f:
        return yaml.safe_load(f)

def parse_asvspoof_protocols(raw_dir):
    """
    Parses ASVspoof 2019 protocol files and returns a unified DataFrame.
    Protocol format: SPEAKER_ID AUDIO_FILE_NAME SYSTEM_ID(Attack) - KEY(bonafide/spoof)
    """
    raw_path = Path(raw_dir)
    protocol_files = list(raw_path.rglob("*.txt"))
    
    metadata = []
    
    print("Indexing audio files (this takes a moment)...")
    all_flacs = list(raw_path.rglob("*.flac"))
    flac_map = {f.stem: str(f) for f in all_flacs}
    
    for proto_file in protocol_files:
        # ASVspoof2019 protocols are usually named like: ASVspoof2019.LA.cm.train.trn.txt
        name_parts = proto_file.name.split('.')
        if len(name_parts) < 4 or "ASVspoof2019" not in proto_file.name:
            continue
            
        scenario = name_parts[1] # LA or PA
        partition = name_parts[3] # train, dev, or eval
        
        with open(proto_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    speaker_id = parts[0]
                    file_id = parts[1]
                    attack_id = parts[3]
                    label = parts[4]
                    
                    file_path = flac_map.get(file_id, "")
                    
                    metadata.append({
                        "file_path": file_path,
                        "speaker_id": speaker_id,
                        "partition": partition,
                        "scenario": scenario,
                        "label": label,
                        "attack_id": attack_id
                    })
    
    return pd.DataFrame(metadata)

def inspect_dataset(raw_dir, metadata_dir):
    print("Parsing ASVspoof protocol files...")
    df = parse_asvspoof_protocols(raw_dir)
    
    if df.empty:
        print("ERROR: Could not parse ASVspoof protocols. Ensure the dataset is downloaded and extracted properly.")
        return
        
    print(f"Parsed {len(df)} metadata records.")
    
    # Save the unified metadata
    os.makedirs(metadata_dir, exist_ok=True)
    metadata_csv_path = os.path.join(metadata_dir, "asvspoof_metadata.csv")
    df.to_csv(metadata_csv_path, index=False)
    print(f"Saved metadata to {metadata_csv_path}")
    
    print("\nExtracting detailed audio statistics (sampling subset to save time)...")
    
    # Analyze a subset for duration/sample rate due to large dataset size
    # Prioritize missing files identification
    missing_files = df[df["file_path"] == ""]
    valid_files = df[df["file_path"] != ""]
    
    sample_df = valid_files.sample(min(1000, len(valid_files)))
    
    durations = []
    sample_rates = set()
    audio_formats = set()
    corrupt_count = 0
    
    for _, row in tqdm(sample_df.iterrows(), total=len(sample_df), desc="Analyzing audio"):
        file_path = Path(row["file_path"])
        audio_formats.add(file_path.suffix)
        try:
            y, sr = librosa.load(file_path, sr=None, mono=False)
            durations.append(librosa.get_duration(y=y, sr=sr))
            sample_rates.add(sr)
        except Exception:
            corrupt_count += 1

    # Compile the report
    report = {
        "dataset_name": "ASVspoof 2019",
        "total_files": len(df),
        "missing_files_in_disk": len(missing_files),
        "corrupted_files_in_sample": corrupt_count,
        "scenarios": {
            "LA": len(df[df["scenario"] == "LA"]),
            "PA": len(df[df["scenario"] == "PA"])
        },
        "partitions": {
            "train": len(df[df["partition"] == "train"]),
            "dev": len(df[df["partition"] == "dev"]),
            "eval": len(df[df["partition"] == "eval"])
        },
        "labels": {
            "bonafide": len(df[df["label"] == "bonafide"]),
            "spoof": len(df[df["label"] == "spoof"])
        },
        "attack_ids": list(df["attack_id"].unique()),
        "speaker_counts": len(df["speaker_id"].unique()),
        "audio_formats": list(audio_formats),
        "sample_rates": list(sample_rates),
        "duration_stats": {
            "avg_seconds": sum(durations) / len(durations) if durations else 0,
            "min_seconds": min(durations) if durations else 0,
            "max_seconds": max(durations) if durations else 0
        },
        "class_balance": {
            "bonafide_percent": len(df[df["label"] == "bonafide"]) / len(df) * 100 if len(df) > 0 else 0,
            "spoof_percent": len(df[df["label"] == "spoof"]) / len(df) * 100 if len(df) > 0 else 0
        }
    }
    
    # Save JSON report
    report_json_path = os.path.join(metadata_dir, "dataset_report.json")
    with open(report_json_path, "w") as f:
        json.dump(report, f, indent=4)
        
    # Save TXT report
    report_txt_path = os.path.join(metadata_dir, "dataset_report.txt")
    with open(report_txt_path, "w") as f:
        f.write("=== V-SHIELD Dataset Validation Report ===\n")
        for key, value in report.items():
            if isinstance(value, dict):
                f.write(f"\n{key.capitalize()}:\n")
                for k, v in value.items():
                    f.write(f"  - {k}: {v}\n")
            elif isinstance(value, list):
                f.write(f"{key.capitalize()}: {', '.join(map(str, value))}\n")
            else:
                f.write(f"{key.capitalize()}: {value}\n")
                
        f.write("\n=== Suitability Analysis ===\n")
        f.write("This dataset represents the gold standard for voice anti-spoofing research.\n")
        f.write("It includes distinct partitions for Logical Access (TTS/VC) and Physical Access (Replay), ")
        f.write("which maps perfectly to V-SHIELD's threat model.\n")
        f.write("The speaker-disjoint partitions prevent data leakage.\n")
                
    print(f"\nReport generated successfully: {report_txt_path}")
    print("Dataset validation complete.")

if __name__ == "__main__":
    config = load_config()
    inspect_dataset(config["dataset"]["raw_dir"], config["dataset"]["metadata_dir"])
