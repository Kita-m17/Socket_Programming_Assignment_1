from socket import *

port = 12000

socketUDP=socket(AF_INET, SOCK_DGRAM)
socketUDP.bind(('196.42.84.95', port))
print("running")
print(gethostbyname(gethostname()))
data, addr= socketUDP.recvfrom(4096)
print(data)
