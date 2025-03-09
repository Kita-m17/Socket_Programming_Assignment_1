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
trackerPort = 65135

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

    #get the file sizes
    file_sizes = chunkSave.get_files()

    for file in os.listdir(shared_folder):
        file_path = os.path.join(shared_folder, file)

        if not os.path.exists(file_path):
            print(f"Error: File {file_path} not found.")
            return
        
        if os.path.isdir(file_path):
            print(f"Skipping directory: {file_path}")
            continue
        
        print(f"Processing file: {file} (Size: {file_sizes[file]} bytes)")

        # Generate file chunks
        chunkSave.split_chunks(file,  file_sizes)

    file_chunks = chunkSave.get_peer_file_chunks("./chunks")
    
    # Peer info message
    peer_info = {
        "type": "REGISTER",
        "peer_address": peerSocket.getsockname(),
        "files": file_chunks # Stores file names and their chunks
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
    data, _ = peerSocket.recvfrom(1024)

    if(data.decode() == 'No peers with file'):
        print('No peers with file')

    else:
        peer_list = data.decode().split(", ")

        # Assume the peer now requests and downloads the chunks from other peers
        # Code for chunk downloading and assembly would go here...
        print(f"Available peers for {file}: {peer_list}")

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
    peerSocket.bind((host,0))
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
            send_heartbeat(peerSocket, trackerIP, trackerPort)
            time.sleep(1)

    except:
        print("Peer shutting down gracefully...")
        
    #time.sleep(300) #exit if offline for 5 min or more
    peerSocket.close()
    

if __name__ == '__main__':
    main()