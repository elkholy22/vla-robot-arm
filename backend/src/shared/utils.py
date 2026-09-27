import socket
import struct
import pickle
import numpy as np

def send_packet(sock: socket.socket, data: object):
    serialized_data = pickle.dumps(data)
    
    message_length = len(serialized_data)
    header = struct.pack('!I', message_length)
    
    sock.sendall(header + serialized_data)

def receive_packet(sock: socket.socket) -> object:
    header = _recv_all(sock, 4)
    if not header:
        return None
        
    message_length = struct.unpack('!I', header)[0]
    
    body = _recv_all(sock, message_length)
    if not body:
        return None
    
    return pickle.loads(body)

def _recv_all(sock: socket.socket, n: int) -> bytes:
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return b''
        data.extend(packet)
    return bytes(data)

def ndarray_to_list(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif hasattr(obj, "__dict__"):
        for key, value in obj.__dict__.items():
            setattr(obj, key, ndarray_to_list(value))
        return obj
    elif isinstance(obj, list):
        return [ndarray_to_list(x) for x in obj]
    elif isinstance(obj, dict):
        return {k: ndarray_to_list(v) for k, v in obj.items()}
    return obj