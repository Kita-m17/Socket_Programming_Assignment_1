from socket import *
import os
import os.path
import chunkSave
import struct
import json
import time
import threading

#tracker informartion
trackerIP = '137.158.160.145'
trackerPort = 12345

def get_file():
    """Retrieve all files in the current directory (excluding directories)"""
    currentPath = "./"
    path = os.listdir(currentPath)
    files = ', '.join(path)
    return files

def send_heartbeat(peerSocket, tracker_ip, tracker_port):
    """Sends a periodic heartbeat/notification to the tracker to indicate that the peer is still active"""
    peer_info = {
        "type": "HEARTBEAT",
        "peer_address": peerSocket.getsockname()
        }
    try:
        peerSocket.sendto(json.dumps(peer_info).encode(), (tracker_ip, tracker_port))
        print("Sent heartbeat to tracker.")
    except:
        print("Failed to send heartbeat. Exiting...")

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

def reg_peer(peerSocket,  tracker_port, tracker_ip):
    """
    Sends the peer's file chunk information to the tracker
    -peer_socket - socket to communicate to with the tracker
    -shared_filder - dir containing the files to share
    -tracker_port - port of the tracker
    -tracker_ip - IP address of the tracker
    -peer_port - port of the peer
    """
    shared_folder = input("Enter the folder to share: format = ./folderName\n")

    print(f"Files in {shared_folder}:", os.listdir(shared_folder))

    file_chunks = check_files(shared_folder)
    #add socket info of peer
    # Peer info message
    listenSocketPort = startListening()
    peer_info = {
        "type": "REGISTER",
        "peer_address": peerSocket.getsockname(),
        "files": file_chunks, # Stores file names and their chunks
        "metadata": chunkSave.get_file_metadata(512000, shared_folder),
        "listening_socket_port": listenSocketPort
    }

    #convert to json and send to tracker
    register_request = json.dumps(peer_info)
    peerSocket.sendto(register_request.encode(), (tracker_ip, tracker_port))

    print(f"Sent peer file information to tracker: {peer_info}")

    # Receive acknowledgment from tracker
    data, _ = peerSocket.recvfrom(1024)
    print(f"Tracker Response: {data.decode()}")

def request_files(peerSocket, file):
    # Request file from tracker

    peer_info = {
        "type": "REQUEST",
        "peer_address": peerSocket.getsockname(),
        "file_request": file
    }

    #convert to json and send to tracker
    file_request = json.dumps(peer_info)
    peerSocket.sendto(file_request.encode(), (trackerIP, trackerPort))

    # Receive list of peers with the file
    response, _ = peerSocket.recvfrom(1024)

    try:
      data = json.loads(response.decode())  

      if "error" in data:
           print(f"Tracker error: {data['error']}")
           return None
      
      print(data)
      return data
    
    except json.JSONDecodeError:
        print(f"Error parsing response: {response.decode()}")
        return None
    
def request_files(udpSocket, file):
    # Request file from tracker

    peer_info = {
        "type": "REQUEST",
        "peer_udp_address": udpSocket.getsockname(),
        "file_request": file
    }

    #convert to json and send to tracker
    file_request = json.dumps(peer_info)
    udpSocket.sendto(file_request.encode(), (trackerIP, trackerPort))

    # Receive list of peers with the file
    data, _ = udpSocket.recvfrom(1024)

    if(data.decode() == 'No peers with file'):
        print('No peers with file')

    else:
        peer_list = data.decode().split(", ")

        # Assume the peer now requests and downloads the chunks from other peers
        # Code for chunk downloading and assembly would go here...
        print(f"Available peers for {file}: {peer_list}")

def download_file(file_data):
    """Establishes TCP connections with peers to download file chunks"""
    if not file_data:
        print("No file data received. Cannot download.")
        return
    
    filename = file_data['filename']
    total_chunks = file_data['total_chunks']
    received_chunks = {}  # Store received chunks: {chunk_number: data}
    
    # Create a directory to store downloaded chunks
    chunk_dir = "./downloads"
    os.makedirs(chunk_dir, exist_ok=True)
    
    print(f"Downloading {filename} with {total_chunks} total chunks")
    
    # For each available peer, request their chunks
    for peer_key, peer_info in file_data['peers'].items():
        ip = peer_info['ip']
        port = peer_info['port']
        chunks_to_request = peer_info['chunks']
        
        print(f"Connecting to peer {ip}:{port} for chunks {chunks_to_request}")
        
        try:
            # Connect to the peer
            tcpSocket = socket(AF_INET, SOCK_STREAM)
            tcpSocket.connect((ip, port))
            
            # Request each chunk from this peer
            for chunk_num in chunks_to_request:
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
                    print("Connection closed by peer")
                    break
                    
                data_length = struct.unpack("!I", length_bytes)[0]
                
                # Receive the chunk data in chunks to handle large files
                data = b""
                remaining = data_length
                
                while remaining > 0:
                    chunk = tcpSocket.recv(min(4096, remaining))
                    if not chunk:
                        break
                    data += chunk
                    remaining -= len(chunk)
                
                if len(data) != data_length:
                    print(f"Warning: Received {len(data)} bytes, expected {data_length}")
                
                # Save chunk to file
                chunk_filename = os.path.join(chunk_dir, f"{filename}_chunk_{chunk_num}.bin")
                with open(chunk_filename, "wb") as f:
                    f.write(data)
                
                received_chunks[chunk_num] = chunk_filename
                print(f"Received chunk {chunk_num} of {filename}, saved to {chunk_filename}")
            
            tcpSocket.close()
            
        except Exception as e:
            print(f"Error connecting to peer {ip}:{port}: {e}")
            continue
    
    # Check if we got all chunks
    if len(received_chunks) == total_chunks:
        print(f"All chunks of {filename} received. Reassembling...")
        chunkSave.reassemble_file(filename, chunk_dir, "./reassembled")
        print(f"File reassembled successfully: ./reassembled/{filename}")
        
        # Update tracker that we now have the file
        notify_new_chunks(filename, list(received_chunks.keys()))
    else:
        print(f"Downloaded {len(received_chunks)}/{total_chunks} chunks of {filename}")
        missing_chunks = [i for i in range(total_chunks) if i not in received_chunks]
        print(f"Missing chunks: {missing_chunks}")

def notify_new_chunks(filename, chunks):
    """Notifies the tracker that we now have new chunks"""
    udpSocket = socket(AF_INET, SOCK_DGRAM)
    udpSocket.bind(("", 0))
    
    for chunk in chunks:
        peer_info = {
            "type": "RESEED",
            "peer_address": udpSocket.getsockname(),
            "filename": filename,
            "chunk": chunk
        }
        
        udpSocket.sendto(json.dumps(peer_info).encode(), (trackerIP, trackerPort))
        
        # Receive acknowledgment
        data, _ = udpSocket.recvfrom(1024)
        print(f"Tracker response for chunk {chunk}: {data.decode()}")
    
    udpSocket.close()

# Handle incoming TCP connections to serve chunks
def handle_client(client_socket, client_address, shared_folder):
    """Handles a client connection requesting chunks"""
    print(f"Handling connection from {client_address}")
    
    try:
        # Receive request length
        length_bytes = client_socket.recv(4)
        if not length_bytes:
            print("Client closed connection")
            client_socket.close()
            return
            
        data_length = struct.unpack("!I", length_bytes)[0]
        
        # Receive request data
        data = b""
        remaining = data_length
        
        while remaining > 0:
            chunk = client_socket.recv(min(4096, remaining))
            if not chunk:
                break
            data += chunk
            remaining -= len(chunk)
        
        if len(data) != data_length:
            print(f"Warning: Received {len(data)} bytes, expected {data_length}")
            client_socket.close()
            return
        
        # Parse request
        request = json.loads(data.decode())
        
        if request["type"] == "CHUNK_REQUEST":
            filename = request["filename"]
            chunk_num = request["chunk_num"]
            
            print(f"Received request for chunk {chunk_num} of {filename}")
            
            # Read the chunk from disk
            chunk_path = f"./chunks/{filename}_chunk_{chunk_num}.bin"
            
            if not os.path.exists(chunk_path):
                print(f"Error: Chunk file {chunk_path} not found")
                client_socket.close()
                return
            
            # Read chunk data
            with open(chunk_path, "rb") as f:
                chunk_data = f.read()
            
            # Send data length + data
            length_bytes = struct.pack("!I", len(chunk_data))
            client_socket.sendall(length_bytes + chunk_data)
            
            print(f"Sent chunk {chunk_num} of {filename} ({len(chunk_data)} bytes)")
        
        else:
            print(f"Unknown request type: {request['type']}")
    
    except Exception as e:
        print(f"Error handling client: {e}")
    
    finally:
        client_socket.close()

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

def accept_connections():
    return

def reseed(peerSocket, shared_folder, tracker_ip, tracker_port):
    file_chunks = check_files(shared_folder)
    
    peer_address = peerSocket.getsockname()
    
    peer_info = {
        "type": "RESEED",
        "peer_address": peer_address,
        "file_chunks": file_chunks
    }

    request = json.dumps(peer_info)
    peerSocket.sendto(request.encode(), (tracker_ip, tracker_port))

def exit(peerSocket):
    peer_info = { "type": "EXIT",
                "peer_address": peerSocket.getsockname()
                }
    request = json.dumps(peer_info)
    
    peerSocket.sendto(request.encode(), (trackerIP, trackerPort))

    #tracker response
    data, addr = peerSocket.recvfrom(4096)
    print(f"Tracker Response: {data.decode()}")

def main():
    #register with the socket
    #tracker informartion
    host = gethostbyname(gethostname())
    peerSocket = socket(AF_INET, SOCK_DGRAM)
    peerSocket.bind((host,18))
    print("Peer script started!")

    Heading = "********************SEEDSTORM BitTorrent System********************" \
            "\n-Welcome to the SEEDSTORM BitTorrent System." \
            "\n-A high-speed, peer-to-peer file-sharing network where peers connect, share, and storm data across the network." \
            "\n-Tracker Connection: We use UDP to track and connect peers." \
            "\n-File Transfer: Peers communicate via TCP for reliable data exchange" \
            "\n-Seeders keep the network alive" \
            "\n-Leechers get the files they need.\n"

    prompts = "1. REGISTER with the Tracker" \
            "\n2. REQUEST a File (Become a Leecher)" \
            "\n3. Send a File (Become a Seeder)" \
            "\n4. Update Availability" \
            "\n5. EXIT the Network"

    print(Heading)
    #register peer in the system
    reg_peer(peerSocket, trackerPort, trackerIP)

    #register peer in the system
    #reg_peer(peerSocket, trackerPort, trackerIP)
    #port = 12000
    #listeningSocket = socket(AF_INET, SOCK_STREAM)
    #listeningSocket.bind("", 12000)
    #tcp_port = listeningSocket.getsockname()[1]
    #listeningSocket.listen(1)
    #listener_thread = threading.Thread(target=accept_connections, daemon=True)
    #listener_thread.start()

    # Start heartbeat thread
    # heartbeat_thread = threading.Thread(target=send_heartbeat, args=(peerSocket, trackerIP, trackerPort))
    # heartbeat_thread.daemon = True
    # heartbeat_thread.start()

    print(prompts)

    peerMssg = input("Enter a prompt: 1, 4: ")
    try:
        while True:
            
            if peerMssg == "4":
                print("Shutting down...")
                exit(peerSocket)
                break
            elif peerMssg == "1":
                #seeder requests for a file
                file_request = input("Enter the file/file chunk you're looking for: ")
                request_files(peerSocket, file_request)
                peerMssg = input("Enter a prompt: 1, 4: ")
            #send_heartbeat(peerSocket, trackerIP, trackerPort)
            time.sleep(1)

    except:
        print("Peer shutting down gracefully...")
        
    #time.sleep(300) #exit if offline for 5 min or more
    peerSocket.close()
    

if __name__ == '__main__':
    main()