from socket import *
import os
import os.path
import chunkSave
import struct
import json
import time
import threading

#tracker informartion
trackerIP = '137.158.160.145' #"192.168.56.1" #196.47.210.277" #'137.158.160.145' #"192.168.56.1"  #'196.24.164.174'
trackerPort = 12345
listeningPort = 12000


def get_file():
    """Retrieve all files in the current directory (excluding directories)"""
    currentPath = "./"
    path = os.listdir(currentPath)
    files = ', '.join(path)
    return files

def send_heartbeat(peerSocket, tracker_ip, tracker_port):
    """Sends a periodic heartbeat/notification to the tracker to indicate that the peer is still active"""
    while True:
        peer_info = {
            "type": "HEARTBEAT",
            "peer_address": peerSocket.getsockname()
        }
        try:
            peerSocket.sendto(json.dumps(peer_info).encode(), (tracker_ip, tracker_port))
            print("Sent heartbeat to tracker.")
        except:
            print("Failed to send heartbeat. Exiting...")
            break
        time.sleep(60) # Send every 60 seconds

def check_files(shared_folder):
    #get the file sizes
    file_sizes = chunkSave.get_files(os.path.join(shared_folder))
    
    for file in os.listdir(shared_folder):
        file_path = os.path.join(shared_folder, file)

        if not os.path.exists(file_path):
            print(f"Error: File {file_path} not found.")
            return
        
        if os.path.isdir(file_path):
            print(f"Skipping directory: {file_path}")
            continue
        
        # print(f"Processing file: {file} (Size: {file_sizes[file]} bytes)")

        # # Generate file chunks
        # chunkSave.split_chunks(file,  file_sizes)
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

    # Convert to json and send to tracker
    register_request = json.dumps(peer_info)
    udpSocket.sendto(register_request.encode(), (tracker_ip, tracker_port))

    print(f"Sent peer file information to tracker: {peer_info}")

    # Receive acknowledgment from tracker
    data, _ = udpSocket.recvfrom(1024)
    print(f"Tracker Response: {data.decode()}")


def request_files(udpSocket, file):
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
            download_file(file_data, udpSocket)
            
    except json.JSONDecodeError:
        print(f"Invalid response from tracker: {data.decode()}")
    except Exception as e:
        print(f"Error processing tracker response: {str(e)}")

def download_file(file_data, udpSocket):
    print("About to download")
    """Establishes TCP connections with peers to download file chunks in parallel"""
    if not file_data:
        print("No file data received. Cannot download.")
        return
    
    filename = file_data['filename']
    total_chunks = file_data['total_chunks']
    received_chunks = {}  # Store received chunks: {chunk_num: data}
    
    # Create a directory to store downloaded chunks
    chunk_dir = "./downloads"
    os.makedirs(chunk_dir, exist_ok=True)
    
    print(f"Downloading {filename} with {total_chunks} total chunks")
    
    # Create a lock for thread-safe access to received_chunks
    chunks_lock = threading.Lock()
    
    # Function to download chunks from a specific peer
    def download_from_peer(ip, port, chunks_to_request):
        try:
            # Connect to the peer
            tcpSocket = socket(AF_INET, SOCK_STREAM)
            tcpSocket.connect((ip, port))
            tcpSocket.settimeout(30)  # Set a timeout to avoid hanging
            
            # Request each chunk from this peer
            for chunk_num in chunks_to_request:
                with chunks_lock:
                    if chunk_num in received_chunks:
                        print(f"Chunk {chunk_num} already received, skipping")
                        continue
                
                # Send chunk request
                request = {
                    "type": "CHUNK_REQUEST",
                    "filename": filename,
                    "chunk_num": chunk_num
                }
                
                # Send request length + request
                request_data = json.dumps(request).encode()
                length_bytes = struct.pack("!I", len(request_data))
                tcpSocket.sendall(length_bytes + request_data)
                
                # Receive chunk data
                length_bytes = tcpSocket.recv(4)
                if not length_bytes:
                    print(f"Connection closed by peer {ip}:{port} while receiving length")
                    break
                    
                data_length = struct.unpack("!I", length_bytes)[0]
                
                # Receive the chunk data
                data = b""
                remaining = data_length
                
                while remaining > 0:
                    chunk = tcpSocket.recv(min(4096, remaining))
                    if not chunk:
                        print(f"Connection closed by peer {ip}:{port} while receiving data")
                        break
                    data += chunk
                    remaining -= len(chunk)
                
                if len(data) != data_length:
                    print(f"Warning: Received {len(data)} bytes, expected {data_length}")
                    continue
                
                # Save chunk to file
                chunk_filename = os.path.join(chunk_dir, f"{filename}_chunk_{chunk_num}.bin")
                with open(chunk_filename, "wb") as f:
                    f.write(data)
                
                with chunks_lock:
                    received_chunks[chunk_num] = chunk_filename
                print(f"Received chunk {chunk_num} of {filename} from {ip}:{port}")
                notify_single_chunk(filename, chunk_num, udpSocket)
            
            # Close connection after all chunks from this peer
            #test this
            tcpSocket.close()
            
        except Exception as e:
            print(f"Error connecting to peer {ip}:{port}: {e}")
            try:
                tcpSocket.close()
            except:
                pass
    
    # Create download threads for each peer
    download_threads = []
    for peer_key, peer_info in file_data['peers'].items():
        ip = peer_info['ip']
        port = peer_info['port']
        chunks_to_request = peer_info['chunks']
        
        thread = threading.Thread(
            target=download_from_peer,
            args=(ip, port, chunks_to_request)
        )
        thread.daemon = True
        download_threads.append(thread)
        thread.start()
    
    # Wait for all download threads to complete
    for thread in download_threads:
        thread.join()
    
    # Check if we got all chunks
    if len(received_chunks) == total_chunks:
        print(f"All chunks of {filename} received. Reassembling...")
        chunkSave.reassemble_file(filename, chunk_dir, "./reassembled")
        print(f"File reassembled successfully: ./reassembled/{filename}")
        
        # Update tracker that we now have the file
        notify_new_chunks(filename, list(received_chunks.keys()), udpSocket)
    else:
        print(f"Downloaded {len(received_chunks)}/{total_chunks} chunks of {filename}")
        missing_chunks = [i for i in range(total_chunks) if i not in received_chunks]
        print(f"Missing chunks: {missing_chunks}")

def notify_single_chunk(filename, chunk, udpSocket):
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

def notify_new_chunks(filename, chunks, udpSocket):
    """Notifies the tracker that we now have new chunks"""
    #udpSocket = socket(AF_INET, SOCK_DGRAM)
    #udpSocket.bind(("", 0))
    
    for chunk in chunks:
        peer_info = {
            "type": "RESEED",
            "peer_udp_address": list(udpSocket.getsockname()),
            "filename": filename,
            "chunk": chunk
        }
        
        udpSocket.sendto(json.dumps(peer_info).encode(), (trackerIP, trackerPort))
        
        # Receive acknowledgment
        data, _ = udpSocket.recvfrom(1024)
        print(f"Tracker response for chunk {chunk}: {data.decode()}")
    
    #udpSocket.close()

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


def startListening(port_number=0):
    listenSocket = socket(AF_INET, SOCK_STREAM)
    listenSocket.bind(('', port_number))
    tcp_port = listenSocket.getsockname()[1]
    listenSocket.listen(10)

    listener_thread = threading.Thread(target=accept_connections, daemon=True)
    listener_thread.start()

    print(f"Socket at port {tcp_port} is now listening")
    #possibly return the port and ip (getsockname)
    return listenSocket.getsockname()

def reseed(udpSocket, tcpSocket, shared_folder, tracker_ip, tracker_port):
    file_chunks = check_files(shared_folder)
    
    # peer_address = peerSocket.getsockname()
    
    peer_info = {
        "type": "RESEED",
        "peer_udp_address": udpSocket.getsockname(),
        "peer_tcp_address": tcpSocket.getsockname(),
        "file_chunks": file_chunks
    }

    request = json.dumps(peer_info)
    udpSocket.sendto(request.encode(), (tracker_ip, tracker_port))

def exit(udpSocket, tcpSocket):
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
    host = gethostbyname(gethostname())
    udpSocket = socket(AF_INET, SOCK_DGRAM)
    udpSocket.bind((host,12001))

    tcpSocket = socket(AF_INET, SOCK_STREAM)
    tcpSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)  # Allow reuse of the address
    tcpSocket.bind((host, listeningPort))
    tcpSocket.listen(5)  # Increase backlog

    print("Peer script started!")

    # Heading = "********************SEEDSTORM BitTorrent System********************" \
    #         "\n-Welcome to the SEEDSTORM BitTorrent System." \
    #         "\n-A high-speed, peer-to-peer file-sharing network where peers connect, share, and storm data across the network." \
    #         "\n-Tracker Connection: We use UDP to track and connect peers." \
    #         "\n-File Transfer: Peers communicate via TCP for reliable data exchange" \
    #         "\n-Seeders keep the network alive" \
    #         "\n-Leechers get the files they need.\n"

    prompts = "1. REGISTER with the Tracker" \
            "\n2. REQUEST a File (Become a Leecher)" \
            "\n3. Send a File (Become a Seeder)" \
            "\n4. Update Availability" \
            "\n5. EXIT the Network"

    # print(Heading)

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
        
        # Main I/O loop
        while True:
            print("\n" + prompts)
            peerMssg = input("Enter a prompt (1, 2, 3, 4, 5): ")
            
            if peerMssg == "1":
                # Register with tracker (already done initially)
                print("Already registered with tracker.")
                
            elif peerMssg == "2":
                # Request a file (become a leecher)
                file_request = input("Enter the filename you're looking for: ")
                request_files(udpSocket, file_request)
                
            elif peerMssg == "3":
                # Update shared folder (become a seeder for additional files)
                new_folder = input("Enter new folder to share (or press Enter to use current folder): ")
                if new_folder:
                    shared_folder = new_folder
                file_chunks = check_files(shared_folder)
                print(f"Now sharing {len(file_chunks)} files from {shared_folder}")
                
            elif peerMssg == "4":
                # Update availability
                file_chunks = check_files(shared_folder)
                print(f"Updated file availability. Currently sharing {len(file_chunks)} files.")
                
            elif peerMssg == "5":
                # Exit the network
                print("Shutting down...")
                exit(udpSocket, tcpSocket)
                break
                
            else:
                print("Invalid option. Please try again.")
                
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Peer shutting down gracefully...")
    finally:
        udpSocket.close()
        tcpSocket.close()
    

if __name__ == '__main__':
    main()