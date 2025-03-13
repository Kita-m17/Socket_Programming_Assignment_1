from enum import Enum

#message types = Command, Data transfer, Control
class MessageType(Enum):
    COMMAND = 1
    DATA_TRANSFER = 2
    CONTROL = 3

class Command(Enum):
    REGISTER = 0x10
    REQUEST_FILE = 0x11
    DISCONNECT = 0x12

class DataTransfer(Enum):
    SEND_CHUNK = 0x20
    RECEIVE_CHUNK = 0x21

class Control(Enum):
    MSSG_ACKNOWLEDGEMENT = 0x30
    RETRANSMISSION_REQUEST = 0x31


