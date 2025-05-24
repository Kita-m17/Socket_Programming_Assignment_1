P2P File Sharing System - README

1. Setup Instructions
Prerequisites
Ensure you have Python 3 installed on your machine. You can check this by running:
python --version
Have a folder called "chunks" in the working directory

If Python is not installed, download and install it

2. Running the Components
Tracker (UDP Server)
The tracker maintains active peers and responds to file requests.
Start the tracker using:
python Tracker.py

By default, the tracker should automatically bind to your machine’s IP. However, if it fails to start, update the host variable inside the start_tracker method in Tracker.py:
trackerSocket.bind(('YOUR_LOCAL_IP', port))

Replace 'YOUR_LOCAL_IP' with your machine's IP address (run ipconfig on Windows or ifconfig on Linux/Mac to find it).

------------------
Peer (Seeder/Leecher)
* Updating Hardcoded IP Addresses
Before running Peer.py, you must change the hardcoded IP addresses inside the main() method:

udpSocket = socket(AF_INET, SOCK_DGRAM)
udpSocket.bind(('YOUR_LOCAL_IP', 12004))

tcpSocket = socket(AF_INET, SOCK_STREAM)
tcpSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)  # Allow reuse of the address
tcpSocket.bind(('YOUR_LOCAL_IP', 12002))
tcpSocket.listen(5)

Replace 'YOUR_LOCAL_IP' with your machine’s IP address.

Additionally, update the tracker’s IP address inside Peer.py:
trackerIP = 'TRACKER_IP'

Replace 'TRACKER_IP' with the machine's IP address where the tracker is running.
___________________________________________________________
Note: This system may not work on UCT lab machines due to network firewalls blocking TCP/UDP connections. It runs successfully on local machines and Nightmare.
___________________________________________________________

Running a Peer:
Start a peer (Seeder/Leecher) using:
python Peer.py

Follow the prompts to request files, share files, or exit the network.

3. How It Works
- Peers register with the tracker over UDP.
- Leechers request a file from the tracker.
- The tracker responds with available seeders.
- Leechers connect to seeders via TCP and request file chunks.
- File chunks are transferred over TCP until the full file is assembled.
- Leechers become seeders after downloading and notify the tracker.
- Peers send periodic heartbeats to stay active in the network. 
- Inactive peers are removed by the tracker after a timeout.

4. Troubleshooting
Tracker Not Responding
Ensure the tracker is running before starting peers.
Check your firewall settings and allow UDP & TCP traffic.

Run:
netstat -an

This checks if the required ports are already in use.

Peer Not Connecting to Tracker
Ensure the tracker's IP is correctly set inside Peer.py.
Double-check the hardcoded IP changes (explained above).
Restart both the tracker and the peer.

File Transfer Issues
Ensure the file exists in the seeder’s shared folder.
Check if the requested chunks are available in the network.
If a transfer is interrupted, try re-requesting the file

5. Features Implemented
Peer Discovery via UDP, Parallel Downloads, Chunk-Based File Transfer, Reseeding after Download,  Heartbeat Mechanism, Error Handling & Retransmissions

6. Summary
This P2P file-sharing system efficiently distributes files using UDP for tracker communication and TCP for file transfers. The protocol ensures reliability, and the heartbeat mechanism prevents stale peers from cluttering the network.
Ensure IP addresses are updated correctly before running the peer for smooth operation. 🚀
