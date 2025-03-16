from socket import *
import os
import os.path
import chunkSave
import struct
import json
import time
import threading


def get_file():
    """Retrieve all files in the current directory (excluding directories)"""
    currentPath = "./"
    path = os.listdir(currentPath)
    files = ', '.join(path)
    return files

def send_heartbeat(peerSocket, tracker_ip, tracker_port):
    """Sends a periodic heartbeat/notification to the tracker to indicate that the peer is still active"""
    #add an event for a clean shutdown
    global keepRunning
    keepRunning = True

    while True:
        peer_info = {
            "type": "HEARTBEAT",
            "peer_address": peerSocket.getsockname()
        }
        try:
            peerSocket.sendto(json.dumps(peer_info).encode(), (tracker_ip, tracker_port))
            #print("Sent heartbeat to tracker.")
        except:
            print("Failed to send heartbeat. Exiting...")
            break
        for _ in range(60):
            if not keepRunning:
                break
            time.sleep(1)

def listAvailableFiles(udpSocket, trackerIP, trackerPort):
    #request files from the tracker
    peer_info = {
        "type": "LIST_FILES",
        "peer_udp_address": list(udpSocket.getsockname())
    }

    #converts to json and send to tracker
    list_request = json.dumps(peer_info)
    udpSocket.sendto(list_request.encode(), (trackerIP, trackerPort))

    #receive file list from tracker
    data, _ = udpSocket.recvfrom(8192)  #lrge buffer size for potentially many files

    try:
        #get the response
        file_list = json.loads(data.decode())
        return file_list

    except json.JSONDecodeError:
        print(f"Invalid response from tracker: {e}")
        print(f"Response data: {data.decode()[:100]}...")  # Print first 100 chars for debugging
        return []
    except Exception as e:
        print(f"Error processing tracker response: {str(e)}")
        return []


def check_files(shared_folder):
    file_chunks = {}
    
    # Get the file sizes
    file_sizes = chunkSave.get_files(os.path.join(shared_folder))
    
    for file in os.listdir(shared_folder):
        file_path = os.path.join(shared_folder, file)

        # Check if file exists and is a file (not a directory)
        if not os.path.exists(file_path):
            print(f"Error: File {file_path} not found.")
            continue
        
        if os.path.isdir(file_path):
            print(f"Skipping directory: {file_path}")
            continue

        if file in file_sizes:
            print(f"Processing file: {file} (Size: {file_sizes[file]} bytes)")
            # Generate file chunks
            chunkSave.split_chunks(shared_folder, file, file_sizes)
        else:
            print(f"Warning: {file} not found in file_sizes dictionary.")

    file_chunks = chunkSave.get_peer_file_chunks("./chunks")
    return file_chunks

def reg_peer(udpSocket, tcpSocket, tracker_port, tracker_ip, shared_folder):
    print(f"Files in {shared_folder}:", os.listdir(shared_folder))
    # Clear the chunks directory to remove old chunks
    chunk_dir = "./chunks"
    for file in os.listdir(chunk_dir):
        try:
            os.remove(os.path.join(chunk_dir, file))
        except Exception as e:
            print(f"Error removing file {file}: {e}")

    file_chunks = check_files(shared_folder)
    
    # Get addresses as tuples
    udp_address = udpSocket.getsockname()
    tcp_address = tcpSocket.getsockname()
    
    # Peer info message
    peer_info = {
        "type": "REGISTER",
        "peer_udp_address": list(udp_address),  # Convert to list for JSON serialization
        "peer_tcp_address": list(tcp_address),  # Convert to list for JSON serialization
        "files": file_chunks,
        "metadata": chunkSave.get_file_metadata(512000, shared_folder)
    }

    print(peer_info)

    # Convert to json and send to tracker
    register_request = json.dumps(peer_info)
    udpSocket.sendto(register_request.encode(), (tracker_ip, tracker_port))

    print(f"Sent peer file information to tracker: {peer_info}")

    # Receive acknowledgment from tracker
    data, _ = udpSocket.recvfrom(1024)
    print(f"Tracker Response: {data.decode()}")


def request_files(udpSocket, file, trackerIP, trackerPort):
    # Request file from tracker
    peer_info = {
        "type": "REQUEST",
        "peer_udp_address": list(udpSocket.getsockname()),  # Convert to list
        "file_request": file
    }

    #convert to json and send to tracker
    file_request = json.dumps(peer_info)
    udpSocket.sendto(file_request.encode(), (trackerIP, trackerPort))

    # Receive list of peers with the file
    data, _ = udpSocket.recvfrom(4096)  # Increased buffer size
    
    try:
        # Parse the JSON response
        file_data = json.loads(data.decode())
        
        if 'error' in file_data:
            print(f"Error: {file_data['error']}")
        else:
            print(f"Available peers for {file}: {list(file_data['peers'].keys())}")
            download_file(file_data, udpSocket, trackerIP, trackerPort)
            
    except json.JSONDecodeError:
        print(f"Invalid response from tracker: {data.decode()}")
    except Exception as e:
        print(f"Error processing tracker response: {str(e)}")

def download_file(file_data, udpSocket, trackerIP, trackerPort):
    """Makes TCP connections with peers to download file chunks in parallel,
    distributing requests among available peers."""
    if not file_data:
        #checks if the file exists
        print("No file data received. Cannot download.")
        return
    
    filename = file_data['filename']
    total_chunks = file_data.get('total_chunks', 0)
    if total_chunks == 0:
        #tries to determine total chunks from the peers data
        all_chunks = set()
        for peer_info in file_data['peers'].values():
            all_chunks.update(peer_info['chunks'])
        total_chunks = len(all_chunks)
        print(f"Determined total chunks to be {total_chunks} based on peer data")
    
    #create directories for downloads and reassembled files
    chunk_dir = "./downloads"
    reassembled_dir = "./reassembled"
    os.makedirs(chunk_dir, exist_ok=True)
    os.makedirs(reassembled_dir, exist_ok=True)
    
    print(f"Downloading {filename} with {total_chunks} total chunks")
    
    #track which chunks we need to download and which are completed
    chunks_to_download = []
    for i in range(total_chunks):
        chunks_to_download.append(i)
    
    #keeps track of all the chunks that were downloaded
    downloaded_chunks = set()

    # Initialize progress tracking
    total_progress = 0
    bar_length = 50  # Length of the progress bar in characters

    #-----------
    maxRetries = 3
    retryCount = 0

    while retryCount < maxRetries and chunks_to_download:
        if retryCount > 0:
            print(f"\nRetry attempt {retryCount}/{maxRetries} for missing chunks...")

            #request updates peer information from the tracker for the missing chunks
            missingChunksInfo = request_chunks_info(filename, chunks_to_download, udpSocket, trackerIP, trackerPort)
            if(missingChunksInfo and 'peers' in missingChunksInfo):
                file_data['peers'] = missingChunksInfo['peers']
            else:
                print("Couldn't get updated peer information for missing chunks.")
    
        #analyze which peers have which chunks and distribute the load/allow different peers to send different chunks
        chunk_to_peers = {}
        peer_load = {}  #keep track of how many chunks we plan to download from each peer
    
        #map of chunks to peers
        for peer_key, peer_info in file_data['peers'].items():
            peer_ip = peer_info['ip']
            peer_port = peer_info['port']
            peer_address = (peer_ip, peer_port)
            peer_load[peer_address] = 0
            
            for chunk_num in peer_info['chunks']:
                if chunk_num not in chunk_to_peers:
                    chunk_to_peers[chunk_num] = []
                chunk_to_peers[chunk_num].append(peer_address)#keep track of chunk that the peer has to send
    
        #display the chunk distribution
        print(f"Found {len(file_data['peers'])} peers with the requested file")
        for peer_key, peer_info in file_data['peers'].items():
            available_chunks = [c for c in peer_info['chunks'] if c in chunks_to_download]
            print(f"Peer {peer_key} has {len(peer_info['chunks'])} chunks")

        # Assign chunks to peers using a round-robin approach for load balancing
        download_assignments = []  # List of (chunk_num, peer_address) tuples
    
        for chunk_num in list(chunks_to_download):
            if chunk_num not in chunk_to_peers or not chunk_to_peers[chunk_num]:
                print(f"No peers available for chunk {chunk_num}")
                chunks_to_download.remove(chunk_num)
                continue
            
            #find the peer with the lowest current load
            available_peers = chunk_to_peers[chunk_num]
            best_peer = min(available_peers, key=lambda p: peer_load[p])
            
            #assign this chunk to the best peer
            download_assignments.append((chunk_num, best_peer))
            peer_load[best_peer] += 1
            chunks_to_download.remove(chunk_num)
    
        #display the download plan
        print("\nDownload plan:")
        for chunk_num, peer in download_assignments:
            print(f"Chunk {chunk_num} will be downloaded from {peer[0]}:{peer[1]}")
        
        print("\nDownload progress:")

        # Reset the progress counter for this batch
        current_batch_count = 0
        total_batch_count = len(download_assignments)
        
        #execute downloads sequentially for stability
        for chunk_num, peer in download_assignments:
            # Update the progress bar for current chunk
            progress_percent = (current_batch_count / total_batch_count) * 100
            filled_length = int(bar_length * current_batch_count // total_batch_count)
            bar = '█' * filled_length + '-' * (bar_length - filled_length)
            
            # Clear the previous line
            print(f"\r[{bar}] {progress_percent:.1f}% - Downloading chunk {chunk_num} from {peer[0]}:{peer[1]}...", end='')
            
            success = download_chunk(chunk_num, peer, filename, chunk_dir)
            # Small delay between requests to prevent overwhelming peers
            if success:
                downloaded_chunks.add(chunk_num)
                current_batch_count += 1
                
                # Update progress for successful download
                progress_percent = (current_batch_count / total_batch_count) * 100
                filled_length = int(bar_length * current_batch_count // total_batch_count)
                bar = '█' * filled_length + '-' * (bar_length - filled_length)
                print(f"\r[{bar}] {progress_percent:.1f}% - Chunk {chunk_num} downloaded successfully.", end='')
            else:
                #if download failed, add chunk back to the list to retry
                chunks_to_download.append(chunk_num)
                print(f"\rFailed to download chunk {chunk_num}! Will retry later.")

            time.sleep(0.5)
        
        # Print newline after completion of batch
        print()
        
        retryCount += 1
        
        # Update overall progress
        total_progress = (len(downloaded_chunks) / total_chunks) * 100
        print(f"\nOverall progress: {total_progress:.1f}% ({len(downloaded_chunks)}/{total_chunks} chunks)")
    
    #check if we've downloaded all chunks
    expected_chunks = set(range(total_chunks))
    missing_chunks = expected_chunks - downloaded_chunks
    
    if not missing_chunks:
        print(f"\nAll {total_chunks} chunks downloaded successfully. Reassembling file...")
        
        try:
            chunkSave.reassemble_file(filename, chunk_dir, reassembled_dir)
            print(f"Successfully reassembled file: {os.path.join(reassembled_dir, filename)}")
            
            #notify tracker about our new chunks
            for chunk_num in downloaded_chunks:
                notify_tracker_of_chunk(filename, chunk_num, udpSocket, trackerIP, trackerPort)
            
            return True
        except Exception as e:
            print(f"Failed to reassemble file: {e}")
            return False
        
    else:
        print(f"\nDownload incomplete. Missing {len(missing_chunks)} chunks: {sorted(missing_chunks)}")
        return False

def download_chunk(chunk_num, peer_address, filename, chunk_dir):
    """Download a specific chunk from a specific peer."""
    peer_ip, peer_port = peer_address
    
    #check if we already have this chunk
    chunk_filename = os.path.join(chunk_dir, f"{filename}_chunk_{chunk_num}.bin")
    if os.path.exists(chunk_filename):
        return True
    
    try:
        #connect to the peer with the chunk
        tcpSocket = socket(AF_INET, SOCK_STREAM)
        tcpSocket.settimeout(30)  # Set a timeout to avoid hanging
        
        try:
            tcpSocket.connect((peer_ip, peer_port))
        except (ConnectionRefusedError, TimeoutError) as e:
            return False
        
        # Send chunk request
        request = {
            "type": "CHUNK_REQUEST",
            "filename": filename,
            "chunk_num": chunk_num
        }
        
        #send request length + request
        request_data = json.dumps(request).encode()
        length_bytes = struct.pack("!I", len(request_data))
        
        #try to send the data
        try:
            tcpSocket.sendall(length_bytes + request_data)
        except Exception as e:
            tcpSocket.close()
            return False
        
        #receive chunk data length
        try:
            length_bytes = tcpSocket.recv(4)

            if not length_bytes or len(length_bytes) < 4:
                tcpSocket.close()
                return False
            
        except socket.timeout:
            tcpSocket.close()
            return False
        
        data_length = struct.unpack("!I", length_bytes)[0]
        
        #Receive the chunk data
        data = b""
        remaining = data_length
        
        try:
            #loop until all expected data is received
            while remaining > 0:
                recv_size = min(4096, remaining)  # Get size of next chunk
                chunk_data = tcpSocket.recv(recv_size)

                if not chunk_data:  # Check if the connection was closed
                    break

                data += chunk_data  # Add chunk to the chunk data
                remaining -= len(chunk_data)  # Update remaining chunks to be received
                
                # Calculate and display download percentage for this chunk
                if data_length > 0:
                    percent_complete = ((data_length - remaining) / data_length) * 100
                    # We don't print here to avoid cluttering the terminal
                    # The parent function will handle the overall progress display

        except socket.timeout:
            tcpSocket.close()
            return False
        finally:
            tcpSocket.close()
        
        if len(data) != data_length:
            return False
        
        # Save chunk to file
        with open(chunk_filename, "wb") as f:
            f.write(data)
        
        return True
        
    except Exception as e:
        return False
    
def request_chunks_info(filename, missing_chunks, udpSocket, trackerIP, trackerPort):
    """request updated info about specific chunks from the tracker"""
    peer_info = {
        "type": "REQUEST_CHUNKS",
        "peer_udp_address": list(udpSocket.getsockname()),
        "filename": filename,
        "chunks": missing_chunks
    }

    try:
        udpSocket.sendto(json.dumps(peer_info).encode(), (trackerIP, trackerPort))

        data, addr = udpSocket.recvfrom(4096)

        try:
            response = json.loads(data.decode())
            return response
        except json.JSONDecodeError:
            print(f"Invalid response from the tracker: {data.decode()}")
            return None
    except Exception as e:
        print("Error requesting chunk information: {e}")
        return None


def notify_tracker_of_chunk(filename, chunk_num, udpSocket, trackerIP, trackerPort):
    """Notify the tracker that we now have a new chunk"""
    try:
        peer_info = {
            "type": "RESEED",
            "peer_udp_address": list(udpSocket.getsockname()),
            "filename": filename,
            "chunk": chunk_num
        }
        
        udpSocket.sendto(json.dumps(peer_info).encode(), (trackerIP, trackerPort))
        
        # Receive acknowledgment
        data, _ = udpSocket.recvfrom(1024)
        print(f"Tracker response for chunk {chunk_num}: {data.decode()}")
    except Exception as e:
        print(f"Failed to notify tracker about chunk {chunk_num}: {e}")
                    
def notify_single_chunk(filename, chunk, udpSocket, trackerIP, trackerPort):
    """Notifies the tracker that we now have a new chunk"""
    peer_info = {
        "type": "RESEED",
        "peer_udp_address": list(udpSocket.getsockname()),
        "filename": filename,
        "chunk": chunk
    }
    
    try:
        udpSocket.sendto(json.dumps(peer_info).encode(), (trackerIP, trackerPort))
        
        # Receive acknowledgment
        data, _ = udpSocket.recvfrom(1024)
        print(f"Tracker updated: now seeding chunk {chunk} of {filename}")
    except Exception as e:
        print(f"Failed to notify tracker about chunk {chunk}: {str(e)}")

def handle_client(client_socket, client_address, shared_folder):
    """Handles a client connection requesting chunks"""
    print(f"Handling connection from {client_address}")
    
    try:
        while True:  # Loop to handle multiple requests
            # Receive request length
            length_bytes = client_socket.recv(4)
            if not length_bytes or len(length_bytes) < 4:
                print("Client closed connection or sent invalid data")
                break
                
            data_length = struct.unpack("!I", length_bytes)[0]
            
            # Receive request data
            data = b""
            remaining = data_length
            
            while remaining > 0:
                chunk = client_socket.recv(min(4096, remaining))
                if not chunk:
                    print("Client closed connection during data reception")
                    return
                data += chunk
                remaining -= len(chunk)
            
            if len(data) != data_length:
                print(f"Warning: Received {len(data)} bytes, expected {data_length}")
                break
            
            # Parse request
            try:
                request = json.loads(data.decode())
            except json.JSONDecodeError:
                print("Invalid JSON received")
                break
            
            if request["type"] == "CHUNK_REQUEST":
                filename = request["filename"]
                chunk_num = request["chunk_num"]
                
                print(f"Received request for chunk {chunk_num} of {filename}")
                
                # Read the chunk from disk
                chunk_path = f"./chunks/{filename}_chunk_{chunk_num}.bin"
                
                if not os.path.exists(chunk_path):
                    print(f"Error: Chunk file {chunk_path} not found")
                    # Send error response
                    error_response = json.dumps({"error": "Chunk not found"}).encode()
                    length_bytes = struct.pack("!I", len(error_response))
                    client_socket.sendall(length_bytes + error_response)
                    continue
                
                # Read chunk data
                with open(chunk_path, "rb") as f:
                    chunk_data = f.read()
                
                # Send data length + data
                length_bytes = struct.pack("!I", len(chunk_data))
                client_socket.sendall(length_bytes + chunk_data)
                
                print(f"Sent chunk {chunk_num} of {filename} ({len(chunk_data)} bytes)")
            
            else:
                print(f"Unknown request type: {request['type']}")
                break
                
    except ConnectionResetError:
        print(f"Connection reset by client {client_address}")
    except Exception as e:
        print(f"Error handling client: {e}")
    
    finally:
        client_socket.close()
        print(f"Connection closed with {client_address}")

def accept_connections(tcpSocket, shared_folder):
    """Listens for incoming TCP connections and handles file chunk requests"""
    print(f"Listening for incoming connections on {tcpSocket.getsockname()}")
    
    while True:
        try:
            client_socket, client_address = tcpSocket.accept()
            print(f"Accepted connection from {client_address}")
            
            # Handle client in a new thread to allow multiple simultaneous connections
            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address, shared_folder)
            )
            client_thread.daemon = True  # Thread will exit when main thread exits
            client_thread.start()
            
        except Exception as e:
            print(f"Error accepting connection: {e}")
            time.sleep(1)  # Avoid CPU spike in case of repeated errors

def reseed(udpSocket, tcpSocket, shared_folder, tracker_ip, tracker_port):
    # exit(udpSocket, tcpSocket, tracker_ip, tracker_port)
    
    # file_chunks = check_files(shared_folder)
     # First, notify the tracker to remove all our existing chunks
    peer_info = {
        "type": "EXIT",
        "peer_udp_address": list(udpSocket.getsockname()),
        "peer_tcp_address": list(tcpSocket.getsockname())
    }

    request = json.dumps(peer_info)
    udpSocket.sendto(request.encode(), (tracker_ip, tracker_port))
    
    # Wait for acknowledgment from tracker
    try:
        data, _ = udpSocket.recvfrom(1024)
        print(f"Tracker response: {data.decode()}")
    except Exception as e:
        print(f"Error receiving response from tracker: {e}")
        return

    # Clear the chunks directory to remove old chunks
    chunk_dir = "./chunks"
    for file in os.listdir(chunk_dir):
        try:
            os.remove(os.path.join(chunk_dir, file))
        except Exception as e:
            print(f"Error removing file {file}: {e}")

    # Now process the new files from the shared folder
    file_chunks = check_files(shared_folder)
    # Re-register with the tracker
    # Get addresses as tuples
    udp_address = udpSocket.getsockname()
    tcp_address = tcpSocket.getsockname()

    # Peer info message
    peer_info = {
        "type": "REGISTER",
        "peer_udp_address": list(udp_address),
        "peer_tcp_address": list(tcp_address),
        "files": file_chunks,
        "metadata": chunkSave.get_file_metadata(512000, shared_folder)
    }

     # Convert to json and send to tracker
    register_request = json.dumps(peer_info)
    udpSocket.sendto(register_request.encode(), (tracker_ip, tracker_port))

    # reg_peer( udpSocket, tcpSocket, tracker_port, tracker_ip, shared_folder)
    
    print(f"Sent new peer file information to tracker")
    
    # Receive acknowledgment from tracker
    data, _ = udpSocket.recvfrom(1024)
    print(f"Tracker Response: {data.decode()}")

def checkTracker(udpSocket, trackerIP, trackerPort):
    """check if the tracker exists and is reachable"""
    try:
        #ping the tracker
        pingMssg= {
            "type":"PING"
        }
        udpSocket.sendto(json.dumps(pingMssg).encode(), (trackerIP, trackerPort))
        
        #set a timeout for the response
        udpSocket.settimeout(5)
        try:
            data, _ = udpSocket.recvfrom(1024)
            udpSocket.settimeout(None)
            return True
        
        except timeout:
            print("Tracker did not respond")
            udpSocket.settimeout(None)
            return False
    except Exception as e:
        print(f"Error checking tracker: {e}")
        return False
    
def update_availability(udpSocket, tcpSocket, shared_folder, tracker_ip, tracker_port):
    """Update file availability by rescanning the shared folder and notifying the tracker"""
    print(f"Updating file availability from {shared_folder}...")
    
    # First, notify the tracker to remove all our existing chunks
    peer_info = {
        "type": "EXIT",
        "peer_udp_address": list(udpSocket.getsockname()),
        "peer_tcp_address": list(tcpSocket.getsockname())
    }

    request = json.dumps(peer_info)
    udpSocket.sendto(request.encode(), (tracker_ip, tracker_port))
    
    # Wait for acknowledgment from tracker
    try:
        data, _ = udpSocket.recvfrom(1024)
        print(f"Tracker response: {data.decode()}")
    except Exception as e:
        print(f"Error receiving response from tracker: {e}")
        return {}
    
    # Clear existing chunks directory to remove old chunks
    chunk_dir = "./chunks"
    for file in os.listdir(chunk_dir):
        try:
            os.remove(os.path.join(chunk_dir, file))
        except Exception as e:
            print(f"Error removing file {file}: {e}")
    
    # Rescan the shared folder and create fresh chunks
    file_chunks = check_files(shared_folder)
    
    # Get addresses as tuples
    udp_address = udpSocket.getsockname()
    tcp_address = tcpSocket.getsockname()
    
    # Prepare update message
    update_info = {
        "type": "REGISTER",  # Re-register with updated information
        "peer_udp_address": list(udp_address),
        "peer_tcp_address": list(tcp_address),
        "files": file_chunks,
        "metadata": chunkSave.get_file_metadata(512000, shared_folder)
    }
    
    # Convert to JSON and send to tracker
    update_request = json.dumps(update_info)
    udpSocket.sendto(update_request.encode(), (tracker_ip, tracker_port))
    
    # Receive acknowledgment from tracker
    data, _ = udpSocket.recvfrom(1024)
    print(f"Tracker Response: {data.decode()}")
    
    return file_chunks
    
def exit(udpSocket, tcpSocket, trackerIP, trackerPort):
    global keepRunning
    keepRunning = False

    peer_info = { 
        "type": "EXIT",
        "peer_udp_address": list(udpSocket.getsockname()),  # Convert to list
        "peer_tcp_address": list(tcpSocket.getsockname())   # Convert to list
    }
    request = json.dumps(peer_info)
    
    udpSocket.sendto(request.encode(), (trackerIP, trackerPort))

    #tracker response
    data, addr = udpSocket.recvfrom(4096)
    print(f"Tracker Response: {data.decode()}")

def main():
    #register with the socket
    #tracker informartion
    trackerIP = '137.158.160.145' 
    trackerPort = 12345

    udpSocket = socket(AF_INET, SOCK_DGRAM)
    udpSocket.bind(('196.42.84.95',12005))

    tcpSocket = socket(AF_INET, SOCK_STREAM)
    tcpSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)  # Allow reuse of the address
    tcpSocket.bind(('196.42.84.95', 12003))
    tcpSocket.listen(5)  # Increase backlog

    print("Peer script started!")
    
    prompts = "1. REQUEST a File (Become a Leecher)" \
            "\n2. Send a File (Become a Seeder)" \
            "\n3. Update Availability" \
            "\n4. EXIT the Network" \
            "\n5. LIST available files in the network"

    #register peer in the system
    try:
        shared_folder = input("Enter the folder to share: format = ./folderName\n")
        
        reg_peer(udpSocket, tcpSocket, trackerPort, trackerIP, shared_folder)
        
        # Start TCP listener in a separate thread
        tcp_listener_thread = threading.Thread(
            target=accept_connections,
            args=(tcpSocket, shared_folder), 
            daemon=True
        )
        tcp_listener_thread.start()
        
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(
            target=send_heartbeat,
            args=(udpSocket, trackerIP, trackerPort),
            daemon=True
        )
        heartbeat_thread.start()
        
        print("\n" + prompts)
        peerMssg = input("Enter a prompt (1, 2, 3, 4, 5): ")
            
        # Main I/O loop
        while True:
            
            if peerMssg == "1":
                # Request a file (become a leecher)
                file_request = input("Enter the filename you're looking for: ")
                check_files(shared_folder)
                request_files(udpSocket, file_request, trackerIP, trackerPort)
                
            elif peerMssg == "2":
                # Update shared folder (become a seeder for additional files)
                new_folder = input("Enter new folder to share (or press Enter to use current folder): ")
                if new_folder:
                    shared_folder = new_folder
                # file_chunks = check_files(shared_folder)
                print(f"Now sharing files from {shared_folder}")
                reseed(udpSocket, tcpSocket, shared_folder, trackerIP, trackerPort)
                
            elif peerMssg == "3":
                # Update availability
                file_chunks = update_availability(udpSocket, tcpSocket, shared_folder, trackerIP, trackerPort)
                print(f"Updated file availability. Currently sharing {len(file_chunks)} files.")
                    
            elif peerMssg == "4":
                # Exit the network
                print("Shutting down...")
                exit(udpSocket, tcpSocket, trackerIP, trackerPort)
                break
            elif peerMssg == "5":
                # List available files in the network
                available_files = listAvailableFiles(udpSocket, trackerIP, trackerPort)
                
                print(tuple(available_files.get("files")))
            else:
                print("No files available in the network.")


            print("\n" + prompts)
            peerMssg = input("Enter a prompt (1, 2, 3, 4, 5): ")
                
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Peer shutting down gracefully...")
    finally:
        # Clear the chunks directory to remove old chunks
        chunk_dir = "./chunks"
        for file in os.listdir(chunk_dir):
            try:
                os.remove(os.path.join(chunk_dir, file))
            except Exception as e:
                print(f"Error removing file {file}: {e}")
        udpSocket.close()
        tcpSocket.close()
        

if __name__ == '__main__':
    main()