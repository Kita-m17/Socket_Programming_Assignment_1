from socket import *
import os
import os.path
import chunkSave
import struct
import json
import time
import threading

#tracker informartion
trackerIP = '196.24.164.174'
trackerPort = 65135

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
    
def download_file(file_data, socket):
    """Establishes TCP connection with Peer to download file chunks"""
    filename = file_data['filename']
    chunks_per_perr = file_data['total_chunks']
    received_chunks = {} #store received chunks

    for peer_key, peer_info in file_data['peers'].items():
        ip = peer_info['ip']
        port = peer_info['port']
        chunks_to_request = peer_info['chunks']

        try:
            TCPsocket = socket(socket.AF_INET, SOCK_STREAM)
            TCPsocket.connect(ip, port)

            print(f"Connected to {ip}, at port number {port}")
            #request all chunks this peer has



def startListening():
    listenSocket = socket(socket.AF_INET, SOCK_STREAM)
    listenSocket.bind(('12600', tcp_port))
    tcp_port = listenSocket.getsockname()[1]
    listenSocket.listen(1)

    listener_thread = threading.Thread(target=accept_connections, daemon=True)
    listener_thread.start()

    print(f"Socket at port {tcp_port} is now listening")
    #possibly return the port and ip (getsockname)
    return tcp_port

def accept_connections():

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