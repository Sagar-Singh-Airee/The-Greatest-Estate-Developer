import tarfile
import os
import sys
import base64
import io

def build_single_file_submission(output_filename="submission.py"):
    """
    Packages the agent into a single submission.py file by base64-encoding
    a tar.gz of the source code. When run in Kaggle, the script decodes itself,
    extracts the code to a temporary directory, and imports the main agent.
    This guarantees 100% compatibility with single-file Kaggle environments 
    without dealing with complex import concatenations.
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    src_dir = os.path.join(project_root, "src", "estate_developer")
    main_file = os.path.join(project_root, "kaggle", "main.py")
    
    if not os.path.exists(src_dir) or not os.path.exists(main_file):
        print("Error: Could not find source files.")
        sys.exit(1)

    print("Compressing project into memory...")
    
    # 1. Create a tar.gz in memory
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w:gz") as tar:
        tar.add(main_file, arcname="main.py")
        tar.add(src_dir, arcname="estate_developer")
        
    tar_bytes = tar_stream.getvalue()
    
    # 2. Base64 encode the tar.gz
    encoded_tar = base64.b64encode(tar_bytes).decode('ascii')
    
    # 3. Write the self-extracting submission.py
    print(f"Writing {output_filename}...")
    
    submission_code = f'''"""
Kaggriculture Agent - The Greatest Estate Developer
Auto-generated single-file submission.
"""
import os
import sys
import base64
import tarfile
import io

# 1. The base64 encoded payload of the agent's multi-file source code
PAYLOAD = "{encoded_tar}"

# 2. Extract payload to a temporary directory
ENV_DIR = "/tmp/estate_agent"

def _bootstrap():
    if not os.path.exists(ENV_DIR):
        os.makedirs(ENV_DIR, exist_ok=True)
        tar_bytes = base64.b64decode(PAYLOAD)
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tar:
            
            # Python 3.12+ safe extraction
            if hasattr(tarfile, "data_filter"):
                tar.extractall(ENV_DIR, filter="data")
            else:
                tar.extractall(ENV_DIR)
                
    if ENV_DIR not in sys.path:
        sys.path.insert(0, ENV_DIR)

_bootstrap()

# 3. Import the actual agent from the extracted main.py
from main import agent

'''
    
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(submission_code)
        
    print(f"Done! Created {output_filename} ({os.path.getsize(output_filename) / 1024:.1f} KB)")
    print(f"You can now submit {output_filename} to Kaggle.")

if __name__ == "__main__":
    build_single_file_submission("submission.py")
