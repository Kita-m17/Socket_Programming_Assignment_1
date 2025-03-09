import os
import math
import hashlib

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

def get_file_metadata(chunk_size):
    """Returns metadata about files in the current directory, including their sizes, number of chunks, and hashes"""
    file_metadata = []
    path = './'
    files = os.listdir(path)
    for file in files:
        file_path = os.path.join(path, file)

        # Ensure it's a file (not a directory)
        if os.path.isfile(file_path):
            file_size = os.path.getsize(file_path)

            # Calculate the number of chunks required
            num_chunks = file_size // chunk_size + (1 if file_size % chunk_size != 0 else 0)

            #compute the file hash
            file_hash = hash_chunk(file_path)
            
            file_metadata.append(
                { "Filename": file,
                 "size": file_size,
                 "num_chunks": num_chunks,
                 "hash": file_hash
                })
    return file_metadata
            

def hash_chunk_with_data(data):
    """Returns the SHA-256 hash of the given chunk data."""
    sha256 = hashlib.sha256()
    sha256.update(data)
    return sha256.hexdigest()

def get_files():
    file_sizes = {}
    path = './'
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

def split_chunks(filename, file_sizes):
    """Splits a file into 512KB chunks and saves them in a 'chunks' directory."""
    file_path = f"./{filename}"
    
    if filename not in file_sizes:
        print(f"File {filename} not found in file_sizes dictionary.")
        return

    num_bytes = file_sizes[filename]
    chunk_hashes = [] #stpre hash, chunk_filename
    
    # Create a directory to store chunks
    chunk_dir = "./chunks"
    os.makedirs(chunk_dir, exist_ok=True)

    with open(file_path, "rb") as file:
        chunk_index = 0
        while (chunk := file.read(512000)):  # Read up to 512KB
            chunk_filename = os.path.join(chunk_dir, f"{filename}_chunk_{chunk_index}.bin")

            #hash chunk
            chunk_hash = hash_chunk_with_data(chunk)

            with open(chunk_filename, "wb") as chunk_file:
                chunk_file.write(chunk)

            chunk_hashes.append((chunk_hash, chunk_filename)) # Store hash and filename
            print(f"Saved {len(chunk)} bytes to {chunk_filename}")

            chunk_index += 1

    print(f"File {filename} split into {chunk_index} chunks.")

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
    """Reassembles split file chunks into the original file."""
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all chunk files related to this filename
    chunk_files = [f for f in os.listdir(chunk_dir) if f.startswith(original_filename + "_chunk_")]
    
    if not chunk_files:
        print(f"No chunks found for {original_filename}.")
        return
    
    # Sort chunk files by their index
    chunk_files.sort(key=lambda x: int(x.split("_chunk_")[-1].split(".bin")[0]))  

    output_file = os.path.join(output_dir, original_filename)
    
    with open(output_file, "wb") as outfile:
        for chunk_file in chunk_files:
            chunk_path = os.path.join(chunk_dir, chunk_file)
            with open(chunk_path, "rb") as infile:
                outfile.write(infile.read())  # Append chunk data
            
            print(f"Reassembled {chunk_file} into {output_file}")

    print(f"\nReassembly complete: {output_file}")


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