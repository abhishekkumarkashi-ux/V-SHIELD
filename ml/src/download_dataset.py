import os
import sys
import yaml
import zipfile
from pathlib import Path
from dotenv import load_dotenv
from kaggle.api.kaggle_api_extended import KaggleApi

# Load environment variables
load_dotenv()

def load_config():
    with open("ml/config.yaml", "r") as f:
        return yaml.safe_load(f)

def verify_credentials():
    username = os.getenv("KAGGLE_USERNAME")
    key = os.getenv("KAGGLE_KEY")
    
    if not username or not key:
        print("ERROR: KAGGLE_USERNAME or KAGGLE_KEY not found in environment.")
        print("Please configure them in the .env file at the root of the project.")
        sys.exit(1)
    
    # Kaggle API automatically picks up KAGGLE_USERNAME and KAGGLE_KEY from env
    try:
        api = KaggleApi()
        api.authenticate()
        print(f"Successfully authenticated with Kaggle as {username}.")
        return api
    except Exception as e:
        print(f"ERROR: Kaggle authentication failed: {e}")
        sys.exit(1)

def download_and_extract(api, dataset_id, raw_dir):
    print(f"\nTarget Dataset: {dataset_id}")
    print(f"Target Directory: {raw_dir}")
    
    raw_path = Path(raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)
    
    # Check if we already have files in the raw directory (simple check)
    existing_files = list(raw_path.glob("*"))
    if len(existing_files) > 0 and any(f.is_dir() or f.suffix in ['.wav', '.flac', '.csv', '.txt'] for f in existing_files):
        print("\nDataset files already appear to exist in the raw directory. Skipping download.")
        return
        
    print(f"\nDownloading dataset {dataset_id}...")
    try:
        api.dataset_download_files(dataset_id, path=raw_path, unzip=True)
        print("Download and extraction completed successfully!")
    except Exception as e:
        print(f"ERROR: Failed to download dataset: {e}")
        sys.exit(1)

def summarize_download(raw_dir):
    print("\n--- Dataset Summary ---")
    raw_path = Path(raw_dir)
    
    total_size = 0
    file_types = {}
    total_files = 0
    
    for item in raw_path.rglob('*'):
        if item.is_file():
            total_files += 1
            total_size += item.stat().st_size
            ext = item.suffix.lower()
            file_types[ext] = file_types.get(ext, 0) + 1
            
    print(f"Total Files: {total_files}")
    print(f"Total Size: {total_size / (1024**3):.2f} GB")
    print("\nFile Formats Distribution:")
    for ext, count in file_types.items():
        print(f"  {ext if ext else 'No extension'}: {count} files")
        
    print("\nRoot Folder Structure:")
    for item in raw_path.iterdir():
        if item.is_dir():
            print(f"  📁 {item.name}/")
        else:
            print(f"  📄 {item.name}")

if __name__ == "__main__":
    config = load_config()
    
    # Use dataset ID from env or fallback to config
    dataset_id = os.getenv("KAGGLE_DATASET", config["dataset"].get("kaggle_id"))
    
    if not dataset_id:
        print("ERROR: Kaggle dataset identifier is not set.")
        print("Please provide it via KAGGLE_DATASET in .env or update ml/config.yaml.")
        sys.exit(1)
        
    api = verify_credentials()
    download_and_extract(api, dataset_id, config["dataset"]["raw_dir"])
    summarize_download(config["dataset"]["raw_dir"])
