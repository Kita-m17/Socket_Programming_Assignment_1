from socket import *

def main():
    serverPort = 12000
    serverSocket = socket(AF_INET, SOCK_STREAM)
    serverSocket.bind(('196.42.84.95', serverPort))
    serverSocket.listen(1)
    print('it works')
    print('The server is ready to recieve')

    while True:
        connectionSocket, addr = serverSocket.accept()
        sentence = connectionSocket.recv(1024).decode()
        capitalSentence = sentence.upper()
        connectionSocket.send(capitalSentence.encode())
        connectionSocket.close()

if __name__ =="__main__":
    main()