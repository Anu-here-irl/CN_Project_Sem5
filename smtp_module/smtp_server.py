# smtp_server.py
# Local SMTP server with SQLite mailbox storage
# Supports multiple client connections

import socket

from users import user_exists
from database import store_email


# ====================================
# SERVER SETTINGS
# ====================================

HOST = "127.0.0.1"
PORT = 2525

DATABASE_NAME = "mailbox.db"


# ====================================
# DATABASE FUNCTION
# ====================================




# ====================================
# CREATE SERVER SOCKET
# ====================================

server_socket = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM
)

# Allow address reuse after restarting
server_socket.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_REUSEADDR,
    1
)

# Bind server
server_socket.bind((HOST, PORT))

# Start listening
server_socket.listen(5)


print("====================================")
print("       LOCAL SMTP SERVER")
print("====================================")
print("Server started successfully!")
print("IP Address :", HOST)
print("Port       :", PORT)
print("Waiting for clients...")
print()


try:

    # ====================================
    # ACCEPT MULTIPLE CLIENTS
    # ====================================

    while True:

        # Wait for a client
        client_socket, client_address = server_socket.accept()

        print()
        print("====================================")
        print("Client connected!")
        print("Client address:", client_address)
        print("====================================")
        print()


        with client_socket:

            with client_socket.makefile(
                "r",
                encoding="utf-8"
            ) as client_reader:


                # ====================================
                # SMTP ENVELOPE VARIABLES
                # ====================================

                smtp_sender = ""
                smtp_recipient = ""


                # ====================================
                # SMTP GREETING
                # ====================================

                # Has the client sent HELO?
                helo_received = False

                # Has MAIL FROM been accepted?
                sender_accepted = False

                # Has RCPT TO been accepted?
                recipient_accepted = False

                client_socket.sendall(
                    b"220 Local SMTP Server Ready\r\n"
                )


                # ====================================
                # PROCESS SMTP COMMANDS
                # ====================================

                while True:

                    line = client_reader.readline()

                    if not line:
                        break

                    # Remove CRLF
                    message = line.rstrip("\r\n")

                    print("Client:", message)

                    command = message.upper()


                    # ====================================
                    # HELO
                    # ====================================

                    if command.startswith("HELO"):

                        # Mark that HELO has been received
                        helo_received = True

                        # Reset SMTP transaction state
                        sender_accepted = False
                        recipient_accepted = False

                        client_socket.sendall(
                            b"250 Hello\r\n"
                        )


                    # ====================================
                    # MAIL FROM
                    # ====================================

                    elif command.startswith("MAIL FROM"):

                        # HELO must come before MAIL FROM
                        if not helo_received:
                            client_socket.sendall(
                                b"503 Bad sequence of commands\r\n"
                            )
                            continue

                        # Extract sender
                        smtp_sender = message[10:].strip()

                        # Remove < and >
                        smtp_sender = smtp_sender.strip("<>")

                        print(
                            "SMTP Sender:",
                            smtp_sender
                        )


                        # Check sender
                        if user_exists(smtp_sender):

                            sender_accepted = True

                            client_socket.sendall(
                                b"250 Sender accepted\r\n"
                            )

                        else:

                            client_socket.sendall(
                                b"550 Sender not found\r\n"
                            )


                    # ====================================
                    # RCPT TO
                    # ====================================

                    elif command.startswith("RCPT TO"):

                        # MAIL FROM must come before RCPT TO
                        if not sender_accepted:
                            client_socket.sendall(
                                b"503 Bad sequence of commands\r\n"
                            )
                            continue

                        # Extract recipient
                        smtp_recipient = message[8:].strip()

                        # Remove < and >
                        smtp_recipient = smtp_recipient.strip("<>")

                        print(
                            "SMTP Recipient:",
                            smtp_recipient
                        )


                        # Check recipient
                        if user_exists(smtp_recipient):

                            recipient_accepted = True

                            client_socket.sendall(
                                b"250 Recipient accepted\r\n"
                            )

                        else:

                            client_socket.sendall(
                                b"550 Recipient not found\r\n"
                            )


                    # ====================================
                    # DATA
                    # ====================================

                    elif command == "DATA":

                        # MAIL FROM and RCPT TO must both be accepted
                        if not sender_accepted or not recipient_accepted:
                            client_socket.sendall(
                                b"503 Bad sequence of commands\r\n"
                            )
                            continue

                        client_socket.sendall(
                            b"354 Start mail input; end with <CRLF>.<CRLF>\r\n"
                        )


                        print()
                        print("----- EMAIL DATA START -----")


                        # ====================================
                        # EMAIL INFORMATION
                        # ====================================

                        # SMTP envelope is authoritative
                        sender = smtp_sender
                        recipient = smtp_recipient

                        # Email header information
                        header_sender = ""
                        header_recipient = ""

                        subject = ""
                        body_lines = []


                        # ====================================
                        # READ EMAIL DATA
                        # ====================================

                        while True:

                            data_line = client_reader.readline()

                            if not data_line:
                                break

                            data_line = data_line.rstrip(
                                "\r\n"
                            )


                            # End of email
                            if data_line == ".":
                                break


                            print(data_line)


                            # From header
                            if data_line.startswith("From:"):

                                header_sender = (
                                    data_line[5:].strip()
                                )


                            # To header
                            elif data_line.startswith("To:"):

                                header_recipient = (
                                    data_line[3:].strip()
                                )


                            # Subject header
                            elif data_line.startswith("Subject:"):

                                subject = (
                                    data_line[8:].strip()
                                )


                            # Blank line
                            elif data_line == "":

                                continue


                            # Body
                            else:

                                body_lines.append(data_line)


                        # Join body lines
                        body = "\n".join(body_lines)


                        print("----- EMAIL DATA END -----")
                        print()


                        # ====================================
                        # DISPLAY EMAIL INFORMATION
                        # ====================================

                        print("EMAIL INFORMATION")
                        print("-------------------------")

                        print(
                            "SMTP Sender    :",
                            sender
                        )

                        print(
                            "SMTP Recipient :",
                            recipient
                        )

                        print(
                            "Header From    :",
                            header_sender
                        )

                        print(
                            "Header To      :",
                            header_recipient
                        )

                        print(
                            "Subject        :",
                            subject
                        )

                        print(
                            "Body           :",
                            body
                        )

                        print("-------------------------")
                        print()


                        # ====================================
                        # STORE EMAIL
                        # ====================================

                        store_email(
                            sender,
                            recipient,
                            subject,
                            body
                        )


                        # Tell client message was accepted
                        client_socket.sendall(
                            b"250 Message accepted\r\n"
                        )

                        # ====================================
                        # RESET SMTP TRANSACTION
                        # ====================================

                        smtp_sender = ""
                        smtp_recipient = ""
                        sender_accepted = False


                    # ====================================
                    # QUIT
                    # ====================================

                    elif command == "QUIT":

                        client_socket.sendall(
                            b"221 Bye\r\n"
                        )

                        break


                    # ====================================
                    # UNKNOWN COMMAND
                    # ====================================

                    else:

                        client_socket.sendall(
                            b"502 Command not implemented\r\n"
                        )


        # ====================================
        # CLIENT DISCONNECTED
        # ====================================

        print()
        print("Client disconnected.")
        print("Waiting for another client...")
        print()


except KeyboardInterrupt:

    print()
    print("Server stopped by user.")


finally:

    server_socket.close()

    print()
    print("SMTP server closed.")