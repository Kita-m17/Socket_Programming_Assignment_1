import os
import math
import hashlib
import json

def get_peer_file_chunks(shared_folder):
    """
    - Scans the shared filder and returns a dictionary with:
    - files_names as keys
    - list of available chunk numbers as values
    """
    file_chunks = {}

    #get all files in the shared folder
    files = os.listdir(shared_folder)
    for file in files:
        if "_chunk_" in file: #check if its a chunk
            parts = file.split("_chunk_")
            filename = parts[0]
            chunk_num = int(parts[1].split(".")[0]) #extract the chunk number

            #store chunks under the correct file
            if filename not in file_chunks:
                file_chunks[filename] = []
            file_chunks[filename].append(chunk_num)

    return file_chunks

def get_file_metadata(chunk_size, path):
    """Returns metadata about files in the current directory, including their sizes, number of chunks, and hashes"""
    file_metadata = []
    files = os.listdir(path)
    for file in files:
        file_path = os.path.join(path, file)

        # Ensure it's a file (not a directory)
        if os.path.isfile(file_path):
            file_size = os.path.getsize(file_path)

            # Calculate the number of chunks required
            num_chunks = file_size // chunk_size + (1 if file_size % chunk_size != 0 else 0)

            # Compute the file hash
            file_hash = hash_chunk(file_path)
            
            # Generate chunk hashes
            chunk_hashes = generate_chunk_hashes(file_path, chunk_size)
            
            file_metadata.append({
                "filename": file,
                "size": file_size,
                "num_chunks": num_chunks,
                "file_hash": file_hash,
                "chunk_hashes": chunk_hashes
            })
    return file_metadata

def generate_chunk_hashes(file_path, chunk_size):
    """Generates SHA-256 hashes for each chunk of the file"""
    chunk_hashes = []
    
    with open(file_path, "rb") as file:
        chunk_index = 0
        while chunk := file.read(chunk_size):
            chunk_hash = hash_chunk_with_data(chunk)
            chunk_hashes.append(chunk_hash)
            chunk_index += 1
            
    return chunk_hashes
            

def hash_chunk_with_data(data):
    """Returns the SHA-256 hash of the given chunk data."""
    sha256 = hashlib.sha256()
    sha256.update(data)
    return sha256.hexdigest()

def get_files(path = "./"):
    file_sizes = {}
    # path = './'
    file_dir = os.listdir(path)
    
    for file in file_dir:
        file_path = os.path.join(path, file)

        #ensure that its a file - not directory
        if os.path.isfile(file_path):
            file_bytes = os.path.getsize(file_path)
            file_sizes[file] = file_bytes
        #file_bytes = os.path.getsize(file)
        #file_sizes[file] = file_bytes
    return file_sizes

def make_directory(filename):
    dir_path = f"./{filename}"
    try:
        os.makedirs(dir_path, exist_ok=True)  # `exist_ok=True` avoids error if dir exists
        print(f"Directory {dir_path} successfully created")
    except PermissionError:
        print(f"Permission required to create {dir_path}")

def split_chunks(shared_folder, filename, file_sizes):
    """Splits a file into 512KB chunks, computes hashes, and saves them in a 'chunks' directory."""
    file_path = os.path.join(shared_folder, filename)
    
    if filename not in file_sizes:
        print(f"File {filename} not found in file_sizes dictionary.")
        return

    num_bytes = file_sizes[filename]
    chunk_hashes = []  # store hash, chunk_filename pairs
    
    # Create a directory to store chunks
    chunk_dir = "./chunks"
    os.makedirs(chunk_dir, exist_ok=True)

    with open(file_path, "rb") as file:
        chunk_index = 0
        while (chunk := file.read(512000)):  # Read up to 512KB
            chunk_filename = os.path.join(chunk_dir, f"{filename}_chunk_{chunk_index}.bin")

            # Hash chunk
            chunk_hash = hash_chunk_with_data(chunk)
            chunk_hashes.append((chunk_hash, chunk_filename))  # Store hash and filename

            with open(chunk_filename, "wb") as chunk_file:
                chunk_file.write(chunk)

            print(f"Saved {len(chunk)} bytes to {chunk_filename} with hash {chunk_hash[:10]}...")
            chunk_index += 1

    print(f"File {filename} split into {chunk_index} chunks with hashes.")
    
    # Create a separate file with hash information for verification
    hash_file = os.path.join(chunk_dir, f"{filename}_hashes.json")
    hash_data = {
        "filename": filename,
        "total_chunks": chunk_index,
        "chunk_hashes": {str(i): hash for i, (hash, _) in enumerate(chunk_hashes)}
    }
    
    with open(hash_file, "w") as f:
        json.dump(hash_data, f, indent=2)
    
    print(f"Chunk hash information saved to {hash_file}")
    
    return chunk_hashes

#hashing provides integrity verification, ensuring that the file wasnt corrupted of tampered with during transmission
#it assists with unique identification between diff verions of the file with the same name
#data validation: the receiver can hash the reassembled file and compare it with the original hash
def hash_chunk(file_path):
    """Returns the SHA-256 hash of the given chunk data."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as file:
        while chunk:= file.read(512000):
            sha256.update(chunk)
    return sha256.hexdigest()

def reassemble_file(original_filename, chunk_dir="./chunks", output_dir="./reassembled"):
    """Reassembles split file chunks into the original file with hash verification."""
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all chunk files related to this filename
    chunk_files = [f for f in os.listdir(chunk_dir) if f.startswith(original_filename + "_chunk_")]
    
    if not chunk_files:
        print(f"No chunks found for {original_filename}.")
        return
    
    # Sort chunk files by their index
    chunk_files.sort(key=lambda x: int(x.split("_chunk_")[-1].split(".bin")[0]))  

    # Check if we have hash information for verification
    hash_file = os.path.join(chunk_dir, f"{original_filename}_hashes.json")
    hash_data = None
    if os.path.exists(hash_file):
        try:
            with open(hash_file, "r") as f:
                hash_data = json.load(f)
            print(f"Found hash information for {original_filename}. Verification enabled.")
        except Exception as e:
            print(f"Error loading hash file: {e}")
    
    # Track verification results
    verified_chunks = 0
    failed_chunks = []

    output_file = os.path.join(output_dir, original_filename)
    
    with open(output_file, "wb") as outfile:
        for i, chunk_file in enumerate(chunk_files):
            chunk_path = os.path.join(chunk_dir, chunk_file)
            
            # Verify hash if available
            if hash_data and "chunk_hashes" in hash_data and str(i) in hash_data["chunk_hashes"]:
                with open(chunk_path, "rb") as f:
                    chunk_data = f.read()
                
                actual_hash = hash_chunk_with_data(chunk_data)
                expected_hash = hash_data["chunk_hashes"][str(i)]
                
                if actual_hash == expected_hash:
                    verified_chunks += 1
                    print(f"✓ Chunk {i} verified successfully.")
                else:
                    failed_chunks.append(i)
                    print(f"⚠ Hash verification FAILED for chunk {i}!")
                    print(f"  Expected: {expected_hash}")
                    print(f"  Actual:   {actual_hash}")
            
            # Append chunk data to output file
            with open(chunk_path, "rb") as infile:
                outfile.write(infile.read())
            
            print(f"Reassembled {chunk_file} into {output_file}")

    # Print verification summary if hash verification was performed
    if hash_data:
        total_chunks = len(chunk_files)
        if failed_chunks:
            print(f"\n⚠ WARNING: {len(failed_chunks)} out of {total_chunks} chunks failed verification!")
            print(f"Failed chunks: {failed_chunks}")
            print("The reassembled file may be corrupted.")
        else:
            print(f"\n✓ All {total_chunks} chunks verified successfully.")
    
    print(f"\nReassembly complete: {output_file}")
    
    # Calculate and display the file hash
    file_hash = hash_chunk(output_file)
    print(f"Final file hash: {file_hash}")
    
    # Verify against original file hash if available
    if hash_data and "file_hash" in hash_data:
        if file_hash == hash_data["file_hash"]:
            print("✓ Complete file hash verified successfully!")
        else:
            print("⚠ WARNING: Complete file hash verification failed!")
            print(f"  Expected: {hash_data['file_hash']}")
            print(f"  Actual:   {file_hash}")




# Get file sizes and store them in a dictionary
# file_sizes = get_files()

# # Print file names and sizes, then split them into chunks
# for file, size in file_sizes.items():
#     print(f"\nProcessing file: {file}")
#     print(f"File size: {size} bytes")
#     split_chunks(file, file_sizes)
#     reassemble_file(file)
# #split_chunks()
# file_chunks = get_peer_file_chunks("./chunks")
# print(file_chunks)
