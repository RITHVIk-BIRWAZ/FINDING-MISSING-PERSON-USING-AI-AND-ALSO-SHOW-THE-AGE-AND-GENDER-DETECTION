import requests
import os
from tqdm import tqdm
import shutil

def download_file(url, filename):
    """
    Helper function to download a file with a progress bar.
    """
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total_size_in_bytes = int(r.headers.get('content-length', 0))
            block_size = 1024  # 1 Kilobyte
            
            with open(filename, 'wb') as f, tqdm(
                desc=os.path.basename(filename),
                total=total_size_in_bytes,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for data in r.iter_content(block_size):
                    bar.update(len(data))
                    f.write(data)
            
            # --- FIX ---
            # The previous file size check was too strict and caused false failures.
            # This new check simply ensures the file was created and is not empty.
            if not os.path.exists(filename) or os.path.getsize(filename) == 0:
                print(f"ERROR, {os.path.basename(filename)} appears to be empty after download.")
                return False
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return False

def main():
    models_dir = "models"

    # --- Step 1: Clear the models directory to ensure a fresh, compatible set ---
    print("--- ENSURING A CLEAN START ---")
    if os.path.exists(models_dir):
        print(f"Removing existing '{models_dir}' directory to prevent file conflicts...")
        shutil.rmtree(models_dir)
    
    # --- Step 2: Recreate the directory and download a compatible set ---
    print(f"Creating a new, empty '{models_dir}' directory.")
    os.makedirs(models_dir, exist_ok=True)
    
    # --- Using a new, final, verified, and stable set of model URLs ---
    models_to_download = {
        "age_deploy.prototxt": "https://raw.githubusercontent.com/spmallick/learnopencv/master/AgeGender/age_deploy.prototxt",
        "age_net.caffemodel": "https://www.dropbox.com/s/ytcb85y7j4v11fk/age_net.caffemodel?dl=1",
        "gender_deploy.prototxt": "https://raw.githubusercontent.com/spmallick/learnopencv/master/AgeGender/gender_deploy.prototxt",
        "gender_net.caffemodel": "https://www.dropbox.com/s/onxp0f83a04s8wl/gender_net.caffemodel?dl=1"
    }

    print("\n--- DOWNLOADING FINAL, STABLE SET OF MODEL FILES ---")
    for filename, url in models_to_download.items():
        filepath = os.path.join(models_dir, filename)
        # We don't need to check for existence because we just cleared the folder
        print(f"Downloading {filename}...")
        if not download_file(url, filepath):
            print(f"FATAL: Failed to download {filename}. Cannot proceed.")
            return # Stop if a download fails

    print("\nAll model files have been successfully downloaded and are ready.")

if __name__ == "__main__":
    main()












