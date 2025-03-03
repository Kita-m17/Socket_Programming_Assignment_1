from socket import *
import os
import os.path

#tracker informartion
trackerIP = "137.158.160.170";
trackerPort = 5000
peerPort = 6000
chunkSize = 1024 #1KB per chunk

# #register files and their file chunks with the tracker
# for file in files:
#     file_size = os.path.getsize(file)
#     num_chunks = file_size // chunkSize + (1 if file_size % chunkSize != 0 else 0)
#     file_chunks[file] = num_chunks


#     peerSocket.sendto(f"REGISTER {peerPort} {file}:{'-'.join(map(str, range(num_chunks)))}".encode(), (trackerIP, trackerPort))

def get_file():
    currentPath = "./"
    path = os.listdir(currentPath)
    files = ', '.join(path)
    return files

def register_peer(peerSocket):
    files = get_file()
    peerSocket.sendto(f"REGISTER {files}".encode(), (trackerIP, trackerPort))

    #receive acknowledgement from tracker
    data, _ = peerSocket.recvfrom(1024)
    print(f"Tracker: {data.decode()}")

def request_files(peerSocket, file_request):
    # Request file from tracker
    
    peerSocket.sendto(f"REQUEST {file_request}".encode(), (trackerIP, trackerPort))

    # Receive list of peers with the file
    data, _ = peerSocket.recvfrom(1024)

    if(data.decode() == 'No peers with file'):
        print('No peers with file')

    else:
        peer_list = data.decode().split(",")

        # Assume the peer now requests and downloads the chunks from other peers
        # Code for chunk downloading and assembly would go here...
        print(f"Available peers for {file_request}: {peer_list}")

def main():
    #register with the socket
    peerSocket = socket(AF_INET, SOCK_DGRAM)
    print("Peer script started!")

    file_chunks = {}

    #register peer in the system
    register_peer(peerSocket)

    #seeder requests for a file
    file_request = input("Enter the file/file chunk you're looking for: ")
    request_files(peerSocket, file_request)
    peerSocket.close()

if __name__ == '__main__':
    main()