from socket import *
import json
import time

STATE_TIMEOUT = 300 #timeout for inactive peers (seconds)
away_threshold = 120
peers = []
peer_states = {} #stores peer states: {peer_address: {'state': 'registered', 'last_active' = time_stamp}}
peer_database = {}  # Store peers and their files: {file_name: {chunk:[ip, port]}}
file_metadata = {} #stores the metadata of each file that the peers have

def handle_peer_requests(data, addr, server):
    request = json.loads(data.decode()) #convert json string to dict
    # print(data.decode())
    if request["type"] == "REGISTER":
        register_peer(request, addr, server)
        
    elif request["type"] == "REQUEST":
        peer_file_request(request, addr, server)

    elif request["type"] == "RESEED":
        update_peer_chunks(request, addr, server)

    elif request["type"] == "EXIT":
        remove_peer(request, addr, server)

    elif request["type"] == "HEARTBEAT":
        update_peer_activity(addr, server)


def save_file_metadata(metadata):
    for file_info in metadata:
        file_name = file_info.get("filename")
        if(file_name not in file_metadata):
            file_metadata[file_name] = {
                "size": file_info.get("size"),
                "num_chunks": file_info.get("num_chunks")
            }

def remove_peer(request, addr, server, send_response=True):
    """Removes a peer and its shared chunks from the tracker database."""
    peer_address = tuple(request.get("peer_address"))
    print(f"Removing peer {peer_address} from database.")

    if peer_database in peers:
        peers.remove(peer_address)
    peer_states.pop(peer_address, None)

    files_to_remove = []
    #Iterate over all files in peer_database
    for file_name, file_chunks in list(peer_database.items()):
        chunks_to_remove = []

        for file_chunk, peer_list in list(peer_database.items()):
            if peer_address in peer_list:
                peer_list.remove(peer_address)
            if not peer_list:
                chunks_to_remove.append(chunk)
            
        #remove empty chunks
        for chunk in chunks_to_remove:
            del file_chunks[chunk]
        
         # If no chunks remain, mark the file for removal
        if not file_chunks:
            files_to_remove.append(file_name)
            
    # Delete empty files
    for file_name in files_to_remove:
            del peer_database[file_name]

    if peer_address in peer_states:
        del peer_states[peer_address]

    if send_response:
        # Confirm removal to peer
        server.sendto(b"Peer successfully removed", addr)

def update_peer_chunks(request, addr, server):
    """ Update the tracker database when a peer receives new chunks. """
    peer_address = tuple(request.get("peer_address"))
    filename = request.get("filename")
    chunk = request.get("chunk")

    if filename not in peer_database:
        peer_database[filename] = {}

    if chunk not in peer_database[filename]:
        peer_database[filename][chunk] = []

    if peer_address in peer_database[filename][chunk]:
        print(f"Peer {peer_address} already has chunk {chunk} of {filename}. No update needed.")
        server.sendto(b"Chunk already registered", addr)
    else:
        peer_database[filename][chunk].append(peer_address)
        print(f"Updated: Peer {peer_address} now has chunk {chunk} of {filename}.")
        server.sendto(b"Chunk update received", addr)

def peer_file_request(request, addr, server):
    filename = request.get("file_request", "")
    requesting_peer_address = request["peer_address"]

    if not filename or filename not in peer_database:
        server.sendto(json.dumps({"error": "No peers with file"}).encode(), addr)
        return

    # Get the chunk list if the file exists in the database
    file_data = peer_database.get(filename, {})

    # Initialize the response with the new structure
    response = {
        "filename": filename,
        "peers": {},
        "total_chunks": len(file_data)
    }

    # Filter out the requesting peer and organize by IP:port
    for chunk_num, peers in file_data.items():
        # Only include peers that aren't the requesting peer
        filtered_peers = [peer for peer in peers if peer != requesting_peer_address]
        
        for peer in filtered_peers:
            peer_key = f"{peer[0]}:{peer[1]}"  # Create a key using IP:port
            
            if peer_key not in response["peers"]:
                response["peers"][peer_key] = {
                    "ip": peer[0],
                    "port": peer[1],
                    "chunks": []
                }
            
            response["peers"][peer_key]["chunks"].append(chunk_num)
    
    # Check if there are any peers left after filtering
    if not response["peers"]:
        server.sendto(json.dumps({"error": "No other peers with file"}).encode(), addr)
        return
    
    # Send the JSON response
    server.sendto(json.dumps(response).encode(), addr)

def register_peer(request, addr, server):
    """Register peer and its chunks"""
    peer_address = tuple(request.get("peer_address"))
    print(f"Debug: peer_address = {peer_address}, type = {type(peer_address)}")
    file_chunks = request.get("files", {})
    if not peer_address:
        print("Error: Missing peer_address in request.")
        server.sendto(b"Error: Missing peer_address", addr)
        return
    
    if peer_address in peers:
        print(f"Peer {peer_address} re-registering. Removing old data.")
        remove_peer({"peer_address": peer_address}, addr, server, send_response=False)
    peers.append(peer_address)

    for filename, chunk_list in file_chunks.items():
        if filename not in peer_database:
            peer_database[filename] = {}

        for chunk in chunk_list:
            if chunk not in peer_database[filename]:
                peer_database[filename][chunk] = []
            if peer_address not in peer_database[filename][chunk]: #avoid duplicates
                peer_database[filename][chunk].append(peer_address)
    metadata = request.get("metadata")
    save_file_metadata(metadata)

    peer_states[peer_address] = {
        "state": "connected",
        "last_active": time.time()
    }

    print(f"Connected to peer: {peer_address} with files: {peer_database}")
    server.sendto(b"Registration successful", addr)
    
def check_peer_activity():
    """Periodically check if peers are still active"""
    while True:
        time.sleep(30)
        for peer_address, state_info in list(peer_states.items()):
            if time.time() - state_info['last_active'] > STATE_TIMEOUT:
                        peer_states[peer_address]['state'] = 'away'
                        print(f"Marked {peer_address} as away")

def update_peer_activity(addr, server):
    """Updates the last active timestamp of a peer."""
    #while True:
    #current_time = time.time()
    #peer_ip = addr[0]

    if addr in peer_states:
        peer_states[addr]["last_active"] = time.time()
        peer_states[addr]["state"] = "active"
        print(f"Received heartbeat from {addr}, marked as active")
    #     server.sendto(b"Heartbeat received", addr)
    # else:
    #     server.sendto(b"Peer not registered", addr)

def update_peer_states():
    """Checks the peer activity and their states based on timeout"""
    while True:
        current_time = time.time()
        peers_to_remove = [] 

        for peer, data in list(peer_states.items()):
            inactive_time = current_time - data["last_active"]

            if inactive_time > STATE_TIMEOUT:
                print(f"Peer {peer} removed due to inactivity.")
                peers_to_remove.append(peer)  # Mark for removal

                # del peer_database[peer]  # Remove fully inactive peers
                # peers.remove(peer) if peer in peers else None
            elif inactive_time > away_threshold and data["state"] == "active":
                print(f"Peer {peer} marked as 'away'.")
                peer_states[peer]["state"] = "away"

        # Remove inactive peers from state tracking and database
        for peer in peers_to_remove:
            peer_states.pop(peer, None)
           
            if peer in peers:
                peers.remove(peer)

            files_to_remove = []

            # Remove peer from peer_database
            for file_name, file_chunks in list(peer_database.items()):
                chunks_to_remove = []

                for chunk, peer_list in list(file_chunks.items()):
                    if peer in peer_list:
                        peer_list.remove(peer)
                    if not peer_list:  # If no peers left, remove chunk
                        chunks_to_remove = []
                        #del file_chunks[chunk]

                    for chunk in chunks_to_remove:
                        del file_chunks[chunk]
                    if not file_chunks:
                        files_to_remove.append(file_name)

                for file_name in files_to_remove:
                    del peer_database[file_name]

        time.sleep(60)  # Check every minute

def start_tracker(port = 65135):
    """Starts the UDP tracker"""
    host = gethostbyname(gethostname())
    trackerSocket = socket(AF_INET, SOCK_DGRAM) #UDP socket
    trackerSocket.bind((host, port)) #listening on port 65135
    print(f"Tracker {trackerSocket.getsockname()} is running")
    
    while True:
        data, addr = trackerSocket.recvfrom(4096)
        handle_peer_requests(data, addr, trackerSocket)

start_tracker()