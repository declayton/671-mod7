"""
    This program listens for work messages contiously.
    It also alerts user if smoker temperature decreases by 15 degrees or more in 2.5 minutes.
 

    Author: Deanna Clayton
    Date: February 20, 2023

"""
 
import pika
import sys
import csv
from collections import deque
import smtplib
from email.message import EmailMessage
import tomllib #requires Python 3.11

# create deque
# limit to 5 items (the 5 most recent readings)
smoker_deque = deque(maxlen=5)

# open a file to write some data
# create a csv writer for our comma delimited data
output_file = open("smoker.csv", "w+")
writer = csv.writer(output_file, delimiter = ",")

# define an alert function to tell us when the smoker decreases 15 degrees or more in 2.5 min
def smoker_alert(d, message):
    # declare alert messages
    subject_str = ("Smoker Alert from Smoker App")
    content_str = ("Smoker Alert!")
    text_message = ("Smoker Alert!")
    
    d.append(message)
    if len(d) == 5:
        if d[0] - d[-1] >= 15:
            print("Smoker Alert!")
            createAndSendEmailTextAlert(subject_str,content_str, text_message)

# define a float number function to see if a string can be converted to a float
def float_num (element):
    if element is None: 
        return element
    try:
        float(element)
        return float(element)
    except ValueError:
        return element
    
def createAndSendEmailTextAlert(email_subject: str, email_body: str, text_message: str):

    """Read outgoing email info from a TOML config file"""

    with open(".env.toml", "rb") as file_object:
        secret_dict = tomllib.load(file_object)

    # basic information

    host = secret_dict["outgoing_email_host"]
    port = secret_dict["outgoing_email_port"]
    outemail = secret_dict["outgoing_email_address"]
    outpwd = secret_dict["outgoing_email_password"]

    # Create an instance of an EmailMessage

    msg = EmailMessage()
    tmsg = EmailMessage()
    msg["From"] = secret_dict["outgoing_email_address"]
    msg["To"] = secret_dict["outgoing_email_address"]
    tmsg["To"] = secret_dict["sms_address_for_texts"]
    msg["Reply-to"] = secret_dict["outgoing_email_address"]
    msg["Subject"] = email_subject
    msg.set_content(email_body)
    tmsg.set_content(text_message)
    
    print("========================================")
    print(f"Prepared Email Message: ")
    print("========================================")
    print()
    print(f"{str(msg)}")
    print(f"{str(tmsg)}")
    print("========================================")
    print()

    # Create an instance of an email server, enable debug messages

    server = smtplib.SMTP(host, port, timeout=120)
    #debug level 2 results in a timestamp
    server.set_debuglevel(2)

    print("========================================")
    print(f"SMTP server created: {str(server)}")
    print("========================================")
    print()

    try:
        print()
        server.connect(host, port)
        print("========================================")
        print(f"Connected: {host, port}")
        print("So far so good - will attempt to start TLS")
        print("========================================")
        print()

        server.starttls()
        print("========================================")
        print(f"TLS started. Will attempt to login.")
        print("========================================")
        print()

        try:
            server.login(outemail, outpwd)
            print("========================================")
            print(f"Successfully logged in as {outemail}.")
            print("========================================")
            print()

        except smtplib.SMTPHeloError:
            print("The server did not reply properly to the HELO greeting.")
            exit()
        except smtplib.SMTPAuthenticationError:
            print("The server did not accept the username/password combination.")
            exit()
        except smtplib.SMTPNotSupportedError:
            print("The AUTH command is not supported by the server.")
            exit()
        except smtplib.SMTPException:
            print("No suitable authentication method was found.")
            exit()
        except Exception as e:
            print(f"Login error. {str(e)}")
            exit()

        try:
            server.send_message(msg)
            server.send_message(tmsg)
            print("========================================")
            print(f"Message sent.")
            print("========================================")
            print()
        except Exception as e:
            print()
            print(f"ERROR: {str(e)}")
        finally:
            server.quit()
            print("========================================")
            print(f"Session terminated.")
            print("========================================")
            print()

    # Except if we get an Exception (we call e)

    except ConnectionRefusedError as e:
        print(f"Error connecting. {str(e)}")
        print()

    except smtplib.SMTPConnectError as e:
        print(f"SMTP connect error. {str(e)}")
        print()

# define a callback function to be called when a message is received
def smoker_callback(ch, method, properties, body):
    """ Define behavior on getting a message."""
    # decode the binary message body to a string and single out temperature recording.
    message = body.decode()
    message2 = str(message)[1:-1]
    message3 = message2.split(',')
    message4 = float_num(message3[1])

    # tell user message has been received
    print(f" [x] Received {message}")
    
    # call alert function
    if isinstance(message4, float):
        smoker_alert(smoker_deque, message4)

    # write the strings to the output file
    writer.writerow(message3)
    
    # when done with task, tell the user
    print(" [x] Done.")
    # acknowledge the message was received and processed 
    # (now it can be deleted from the queue)
    ch.basic_ack(delivery_tag=method.delivery_tag)


# define a main function to run the program
def main(hn: str = "localhost", qn: str = "temp1"):
    """ Continuously listen for task messages on a named queue."""

    # when a statement can go wrong, use a try-except block
    try:
        # try this code, if it works, keep going
        # create a blocking connection to the RabbitMQ server
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=hn))

    # except, if there's an error, do this
    except Exception as e:
        print()
        print("ERROR: connection to RabbitMQ server failed.")
        print(f"Verify the server is running on host={hn}.")
        print(f"The error says: {e}")
        print()
        sys.exit(1)

    try:
        # use the connection to create a communication channel
        channel = connection.channel()

        # use the channel to declare a durable queue
        # a durable queue will survive a RabbitMQ server restart
        # and help ensure messages are processed in order
        # messages will not be deleted until the consumer acknowledges
        channel.queue_declare(queue=qn, durable=True)

        # The QoS level controls the # of messages
        # that can be in-flight (unacknowledged by the consumer)
        # at any given time.
        # Set the prefetch count to one to limit the number of messages
        # being consumed and processed concurrently.
        # This helps prevent a worker from becoming overwhelmed
        # and improve the overall system performance. 
        # prefetch_count = Per consumer limit of unaknowledged messages      
        channel.basic_qos(prefetch_count=1) 

        # configure the channel to listen on a specific queue,  
        # use the callback function named callback,
        # and do not auto-acknowledge the message (let the callback handle it)
        channel.basic_consume( queue=qn, on_message_callback=smoker_callback)

        # print a message to the console for the user
        print(" [*] Ready for work. To exit press CTRL+C")

        # start consuming messages via the communication channel
        channel.start_consuming()

    # except, in the event of an error OR user stops the process, do this
    except Exception as e:
        print()
        print("ERROR: something went wrong.")
        print(f"The error says: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        print(" User interrupted continuous listening process.")
        sys.exit(0)
    finally:
        print("\nClosing connection. Goodbye.\n")
        connection.close()


# Standard Python idiom to indicate main program entry point
# This allows us to import this module and use its functions
# without executing the code below.
# If this is the program being run, then execute the code below
if __name__ == "__main__":
    # call the main function with the information needed
    main("localhost", "temp1")
