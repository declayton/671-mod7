"""
    This program sends messages to three queues on the RabbitMQ server.


    Author: Deanna Clayton
    Date: February 20, 2023

"""

import pika
import sys
import csv
import time

# read from a file to get some data
input_file = open("smoker-temps.csv", "r")

# create a csv reader for our comma delimited data
reader = csv.reader(input_file, delimiter=",")

def delete_queue(host: str, queue_name: str):
    """
    Delete queues each time program is run
    """
    conn = pika.BlockingConnection(pika.ConnectionParameters(host))
    ch = conn.channel()
    ch.queue_delete(queue=queue_name)

def send_message(host: str, queue_name: str, message: str):
    """
    Creates and sends a message to the queue each execution.
    This process runs and finishes.

    Parameters:
        host (str): the host name or IP address of the RabbitMQ server
        queue_name (str): the name of the queue
        message (str): the message to be sent to the queue
    """

    try:
        # create a blocking connection to the RabbitMQ server
        conn = pika.BlockingConnection(pika.ConnectionParameters(host))
        # use the connection to create a communication channel
        ch = conn.channel()
        # use the channel to declare a durable queue
        # a durable queue will survive a RabbitMQ server restart
        # and help ensure messages are processed in order
        # messages will not be deleted until the consumer acknowledges
        ch.queue_declare(queue=queue_name, durable=True)
        # use the channel to publish a message to the queue
        # every message passes through an exchange
        ch.basic_publish(exchange="", routing_key=queue_name, body=message)
        # print a message to the console for the user
        print(f" [x] Sent {message}")
    except pika.exceptions.AMQPConnectionError as e:
        print(f"Error: Connection to RabbitMQ server failed: {e}")
        sys.exit(1)
    finally:
        # close the connection to the server
        conn.close()


# Standard Python idiom to indicate main program entry point
# This allows us to import this module and use its functions
# without executing the code below.
# If this is the program being run, then execute the code below
if __name__ == "__main__":  

    # Delete the queues to clear out any data previously sent
    delete_queue("localhost", "temp1")
    delete_queue("localhost", "temp2")
    delete_queue("localhost", "temp3")

    # Skip the header row
    # next(reader)

    for row in reader:
        # read a row from the file
        Time, Smoker, FoodA, FoodB = row

        # get the message from the command line
        # if no arguments are provided, use the default message
        # use the join method to convert the list of arguments into a string
        # join by the space character inside the quotes
        message1 = " ".join(sys.argv[1:]) or f"[{Time}, {Smoker}]"
        message2 = " ".join(sys.argv[1:]) or f"[{Time}, {FoodA}]"
        message3 = " ".join(sys.argv[1:]) or f"[{Time}, {FoodB}]"
        # send the messages to queues
        send_message("localhost","temp1",message1)
        send_message("localhost","temp2",message2)
        send_message("localhost","temp3",message3)

        # sleep for 30 seconds
        time.sleep(1)
