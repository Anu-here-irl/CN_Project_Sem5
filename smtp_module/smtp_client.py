# smtp_client.py
# Basic SMTP client for our Computer Networks project

import socket


# Server settings
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 2525


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:

    client_socket.connect((SERVER_HOST, SERVER_PORT))

    with client_socket.makefile(
        "r",
        encoding="utf-8"
    ) as server_reader:

        print("====================================")
        print("        LOCAL SMTP CLIENT")
        print("====================================")
        print("Connected to SMTP server!")
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
        # MAIL FROM
        # ====================================

        client_socket.sendall(
            b"MAIL FROM:<alice@localmail.com>\r\n"
        )

        sender_response = read_response()

        # Stop if sender was rejected
        if not sender_response.startswith("250"):

            print()
            print("Email sending failed: sender rejected.")
            exit()


        # ====================================
        # RCPT TO
        # ====================================

        client_socket.sendall(
            b"RCPT TO:<bob@localmail.com>\r\n"
        )

        recipient_response = read_response()

        # Stop if recipient was rejected
        if not recipient_response.startswith("250"):

            print()
            print("Email sending failed: recipient rejected.")
            exit()


        # ====================================
        # DATA
        # ====================================

        client_socket.sendall(
            b"DATA\r\n"
        )

        data_response = read_response()


        # Make sure server accepted DATA command
        if not data_response.startswith("354"):

            print()
            print("Email sending failed: DATA command rejected.")
            exit()


        # ====================================
        # EMAIL CONTENT
        # ====================================

        email_content = (
            "From: alice@localmail.com\r\n"
            "To: bob@localmail.com\r\n"
            "Subject: CN Project Test\r\n"
            "\r\n"
            "Hello Bob!\r\n"
            "This is our first SMTP test.\r\n"
            "Our local email system is working!"
            "\r\n.\r\n"
        )


        client_socket.sendall(
            email_content.encode("utf-8")
        )


        message_response = read_response()


        # ====================================
        # QUIT
        # ====================================

        client_socket.sendall(
            b"QUIT\r\n"
        )

        read_response()


print()
print("Email transmission completed.")