import socket

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 2525


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:

    client_socket.connect((SERVER_HOST, SERVER_PORT))

    with client_socket.makefile("r", encoding="utf-8") as server_reader:

        print("====================================")
        print("    INVALID SMTP COMMAND TEST")
        print("====================================")
        print()

        # Read server greeting
        response = server_reader.readline().strip()
        print("Server:", response)

        # Send HELO
        client_socket.sendall(
            b"HELO localhost\r\n"
        )

        response = server_reader.readline().strip()
        print("Server:", response)

        # Send an invalid command
        client_socket.sendall(
            b"FOOBAR\r\n"
        )

        response = server_reader.readline().strip()
        print("Server:", response)

        # Quit
        client_socket.sendall(
            b"QUIT\r\n"
        )

        response = server_reader.readline().strip()
        print("Server:", response)


print()
print("Invalid command test completed.")