import socket
import select
import threading
import sys

def handle_client(client_sock):
    try:
        req = b""
        while b"\r\n\r\n" not in req:
            chunk = client_sock.recv(4096)
            if not chunk:
                break
            req += chunk

        lines = req.split(b"\r\n")
        first_line = lines[0].decode("latin1")
        parts = first_line.split()
        if len(parts) < 2:
            client_sock.close()
            return

        method, target = parts[0], parts[1]

        if method.upper() == "CONNECT":
            host, port = target.split(":")
            port = int(port)

            remote_sock = socket.create_connection((host, port), timeout=10)
            client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")

            sockets = [client_sock, remote_sock]
            while True:
                r, _, _ = select.select(sockets, [], [], 30)
                if not r:
                    break
                if client_sock in r:
                    data = client_sock.recv(65536)
                    if not data:
                        break
                    remote_sock.sendall(data)
                if remote_sock in r:
                    data = remote_sock.recv(65536)
                    if not data:
                        break
                    client_sock.sendall(data)
            remote_sock.close()
        else:
            from urllib.parse import urlparse
            p = urlparse(target)
            host = p.hostname
            port = p.port or 80
            remote_sock = socket.create_connection((host, port), timeout=10)
            remote_sock.sendall(req)
            sockets = [client_sock, remote_sock]
            while True:
                r, _, _ = select.select(sockets, [], [], 30)
                if not r:
                    break
                if client_sock in r:
                    data = client_sock.recv(65536)
                    if not data:
                        break
                    remote_sock.sendall(data)
                if remote_sock in r:
                    data = remote_sock.recv(65536)
                    if not data:
                        break
                    client_sock.sendall(data)
            remote_sock.close()
    except Exception:
        pass
    finally:
        try:
            client_sock.close()
        except Exception:
            pass

def main(port=8888):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(128)
    print(f"Proxy server running on 0.0.0.0:{port}", flush=True)
    while True:
        client, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(client,), daemon=True)
        t.start()

if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    main(p)
