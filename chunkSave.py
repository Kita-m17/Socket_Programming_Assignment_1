import os
import math

def get_files():
    file_sizes = {}
    path = './'
    file_dir = os.listdir(path)
    for file in file_dir:
        file_bytes = os.path.getsize(file)
        file_sizes[file] = file_bytes
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
    
    # Create a directory to store chunks
    chunk_dir = "./chunks"
    os.makedirs(chunk_dir, exist_ok=True)

    with open(file_path, "rb") as file:
        chunk_index = 0
        while (chunk := file.read(512000)):  # Read up to 512KB
            chunk_filename = os.path.join(chunk_dir, f"{filename}_chunk_{chunk_index}.bin")
            with open(chunk_filename, "wb") as chunk_file:
                chunk_file.write(chunk)
            print(f"Saved {len(chunk)} bytes to {chunk_filename}")
            chunk_index += 1

    print(f"File {filename} split into {chunk_index} chunks.")

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
file_sizes = get_files()

# Print file names and sizes, then split them into chunks
for file, size in file_sizes.items():
    print(f"\nProcessing file: {file}")
    print(f"File size: {size} bytes")
    split_chunks(file, file_sizes)
    reassemble_file(file)