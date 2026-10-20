import socket

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 2525


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:

    client_socket.connect((SERVER_HOST, SERVER_PORT))

    with client_socket.makefile("r", encoding="utf-8") as server_reader:

        print("====================================")
        print(" TEST: DATA WITHOUT RCPT TO")
        print("====================================")
        print()

        # Server greeting
        response = server_reader.readline().strip()
        print("Server:", response)

        # HELO
        client_socket.sendall(
            b"HELO localhost\r\n"
        )

        response = server_reader.readline().strip()
        print("Server:", response)

        # Valid MAIL FROM
        client_socket.sendall(
            b"MAIL FROM:<alice@localmail.com>\r\n"
        )

        response = server_reader.readline().strip()
        print("Server:", response)

        # Skip RCPT TO
        # Directly send DATA
        client_socket.sendall(
            b"DATA\r\n"
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
print("Test completed.")