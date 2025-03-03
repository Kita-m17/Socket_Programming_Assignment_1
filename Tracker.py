from socket import *
import time

#tracker informartion
trackerPort = 5000
timeout = 300 #timeout for inactive peers (seconds)

peer_database = {}  # Store peers and their files: {file_name: [(ip, port)]}

def start_tracker():
    """Starts the UDP tracker"""
    trackerSocket = socket(AF_INET, SOCK_DGRAM) #UDP socket
    trackerSocket.bind(('', trackerPort )) #listening on port 5000
    print(f"Tracker {trackerSocket.getsockname()} is running")

    while True:
        print("...")
        data, addr = trackerSocket.recvfrom(1024) # Receive data from peers
        message = data.decode().split(" ")

        if message[0] == "REGISTER":
            #peer_ip = message[1]  # peers ip address
            #peer_port = int(message[2]) # Peer should send their listening port

            #for peers entering the system, retrieve their identifiers and file names
            # files_and_chunks = message[3].split(", ")

            #register the chunks of each file 


            # for file_and_chunks in files_and_chunks:

            #     file_name, chunks = file_and_chunks.split(":")

            #     #split the chunks string into a list of string parts
            #     chunk_strings = chunks.split("-")
            #     # Convert each string part into an integer  
            #     chunks = [int(chunk) for chunk in chunk_strings] # List of chunks available for this file

            #     if file_name not in peer_database:
            #         peer_database[file_name] = []
            #     peer_database[file_name].append( (peer_ip, peer_port, chunks) )
                
            print(f"Received from {addr}: {data.decode()}")
            trackerSocket.sendto(b"Registered successfully!", addr)
        
        elif message[0] == "REQUEST":
            file_requested = message[1]
            peers_with_chunks = []
            
            # Get the list of peers that have the requested file
            peers_with_file = peer_database.get(file_requested, [])
            
            # Create an empty list to hold the formatted peer strings  
            formatted_peers = []
            
            # Loop through each peer in the list  
            for peer in peers_with_file:  
                ip, port, chunks = peer  #get peer ip, port, and chunks 

                #create string of the identifier(portNo and ip address) and their chunks
                formatted_peer = f"{ip}:{port}[{', '.join(map(str, chunks))}]"  # Format the peer as "ip:port"  
                formatted_peers.append(formatted_peer)  # Add the formatted peer to the list  

            # If no peers have the file, notify the requesting peer
            if not peers_with_chunks:
                peers_with_chunks.append("No peers with file")

            # Join the list of formatted peers into a single string, separated by commas  
            peers_with_file = ", ".join(peers_with_chunks)  
            
            trackerSocket.sendto(peers_with_file.encode(), addr)

start_tracker()