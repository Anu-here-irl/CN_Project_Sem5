"""Interactive client for testing the local POP3 server."""
import socket

HOST, PORT = "127.0.0.1", 1110


def read_response(stream, multiline=False):
    first = stream.readline().decode("utf-8", errors="replace").rstrip("\r\n")
    print(first)
    if multiline and first.startswith("+OK"):
        while True:
            line = stream.readline().decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                break
            if line == ".":
                break
            print(line[1:] if line.startswith("..") else line)


def main():
    with socket.create_connection((HOST, PORT)) as sock:
        stream = sock.makefile("rwb")
        read_response(stream)
        while True:
            command = input("POP3> ").strip()
            if not command:
                continue
            stream.write((command + "\r\n").encode())
            stream.flush()
            upper = command.upper()
            read_response(stream, multiline=(upper == "LIST" or upper.startswith("RETR ")))
            if upper == "QUIT":
                break


if __name__ == "__main__":
    main()
