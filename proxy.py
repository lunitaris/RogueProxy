#!/bin/env python2
#-*- coding:utf-8 -*-

from socket import socket, SOL_SOCKET, SO_REUSEADDR, error as sock_err
from threading import Thread
from Queue import Queue
from time import time, sleep
from threadlib import loger, worker, cltthread
from argparse import ArgumentParser


def __init_serv__():
    """ This func inits everything. Defines the queue, starts the pool of http workers,
        starts the logger thread, bind our script to 0.0.0.0:8080, and finally starts new
        thread for each client that connects
    """
    # Read args
    parser = ArgumentParser()
    parser.add_argument("-i", "--inject-js", help="Inject JS in pages", action="store_true")
    parser.add_argument("-d", "--dump-password", type=int, choices=[1, 2, 3], help="Dump password to {[1] - stdout |  [2] - file | [3] - both file and stdout} when found")
    args = parser.parse_args()
    # Defines a FIFO queue for requests threads
    queue = Queue()
    # Defines another FIFO queue for LOG thread
    logqueue = Queue()

    # We start a pool of N workers
    # They are used to serve each requests independently from the source client
    for num in range(64):
        thread = Thread(target=worker, args=(queue, logqueue, num, args.inject_js, args.dump_password))
        # We set each worker to Daemon
        # This is important because we can safely ^C now
        thread.setDaemon(True)
        thread.start()

    # We start the thread that will log every thing into http.log
    logthread = Thread(target=loger, args=(logqueue,))
    # Once again, we are setting this thread to daemonic mode
    # for ^C sakes
    logthread.setDaemon(True)
    logthread.start()

    sock = socket()
    # We bind ourselves to port 8080 (usual port for proxy though)
    while True:
        try:
            sock.bind(('0.0.0.0', 8080))
        except sock_err:
            print(
                '%s - [INFO] Exception SOCKET_ERROR: Can\'t bind.Please try again later.' %
                (time()))
            sleep(1)
        else:
            print '%s - [INFO] Server listening to 0.0.0.0:8080' % (time())
            break
    # We use SO_REUSEADDR argument to be able to restart the proxy script right after we kill it
    # Doesn't work every time sadly
    # There is probably a lot of timeout errors
    sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    try:
        # Here we just wait until we received a new connection (from a client)
        # We then start a thread to handle this specific client / request
        while True:
            sock.listen(0)
            # max connection is set to 0, but i guess we could set it to the number of
            # started workers. Possibly using threading.activeCount()
            cltsock, cltaddr = sock.accept()
            thread = Thread(
                target=cltthread, args=(
                    cltsock, cltaddr, queue, logqueue))
            # We set each worker to Daemon
            # This is important because we can safely ^C now
            thread.setDaemon(True)
            thread.start()
    except KeyboardInterrupt:
        sock.close()
        exit(0)

if __name__ == '__main__':
    __init_serv__()
