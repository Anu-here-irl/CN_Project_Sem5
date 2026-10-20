import socket

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 2525


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:

    client_socket.connect((SERVER_HOST, SERVER_PORT))

    with client_socket.makefile("r", encoding="utf-8") as server_reader:

        print("====================================")
        print("   TWO EMAILS - ONE CONNECTION")
        print("====================================")
        print()

        # ====================================
        # FUNCTION TO READ SERVER RESPONSE
        # ====================================

        def read_response():

            response = server_reader.readline()

            if not response:
                raise ConnectionError(
                    "SMTP server closed the connection"
                )

            response = response.strip()

            print("Server:", response)

            return response


        # ====================================
        # SERVER GREETING
        # ====================================

        read_response()


        # ====================================
        # HELO
        # ====================================

        client_socket.sendall(
            b"HELO localhost\r\n"
        )

        read_response()


        # ====================================
        # EMAIL 1
        # ====================================

        print()
        print("----- SENDING EMAIL 1 -----")

        client_socket.sendall(
            b"MAIL FROM:<alice@localmail.com>\r\n"
        )

        read_response()


        client_socket.sendall(
            b"RCPT TO:<bob@localmail.com>\r\n"
        )

        read_response()


        client_socket.sendall(
            b"DATA\r\n"
        )

        read_response()


        email_1 = (
            "From: alice@localmail.com\r\n"
            "To: bob@localmail.com\r\n"
            "Subject: First Email\r\n"
            "\r\n"
            "This is the first email.\r\n"
            "It is being sent on this connection."
            "\r\n.\r\n"
        )

        client_socket.sendall(
            email_1.encode("utf-8")
        )

        read_response()


        # ====================================
        # EMAIL 2
        # ====================================

        print()
        print("----- SENDING EMAIL 2 -----")

        client_socket.sendall(
            b"MAIL FROM:<alice@localmail.com>\r\n"
        )

        read_response()


        client_socket.sendall(
            b"RCPT TO:<bob@localmail.com>\r\n"
        )

        read_response()


        client_socket.sendall(
            b"DATA\r\n"
        )

        read_response()


        email_2 = (
            "From: alice@localmail.com\r\n"
            "To: bob@localmail.com\r\n"
            "Subject: Second Email\r\n"
            "\r\n"
            "This is the second email.\r\n"
            "It is using the same TCP connection."
            "\r\n.\r\n"
        )

        client_socket.sendall(
            email_2.encode("utf-8")
        )

        read_response()


        # ====================================
        # QUIT
        # ====================================

        print()
        print("----- CLOSING CONNECTION -----")

        client_socket.sendall(
            b"QUIT\r\n"
        )

        read_response()


print()
print("Two-email test completed.")