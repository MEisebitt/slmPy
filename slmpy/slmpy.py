# -*- coding: utf-8 -*-
"""
Created on Sun Dec 06 20:14:02 2015

@author: Sebastien M. Popoff

"""

try:
    import wx
except ImportError:
    raise ImportError("The wxPython module is required to run this program.")
import threading
import numpy as np
import time
import socket
import struct
import bz2
import zlib
import gzip
import itertools
from funcy import chunks
from math import ceil

from .comm import tcp_server, tcp_client
from .comm import udp_server, udp_client

        

EVT_NEW_IMAGE = wx.PyEventBinder(wx.NewEventType(), 0)
PACKET_SIZE = 4096

        

class ImageEvent(wx.PyCommandEvent):
    def __init__(self, eventType=EVT_NEW_IMAGE.evtType[0], id=0):
        wx.PyCommandEvent.__init__(self, eventType, id)
        self.img = None
        self.color = False
        self.oldImageLock = None
        self.eventLock = None


class SLMframe(wx.Frame):
    
    def __init__(self, 
                 monitor, 
                 isImageLock,
                 alwaysTop):
        
        style = wx.DEFAULT_FRAME_STYLE
        if alwaysTop:
            style = style | wx.STAY_ON_TOP
        self.isImageLock = isImageLock
        self.SetMonitor(monitor)
        super().__init__(None,
                         -1,
                         'SLM window',
                         pos = (self._x0, self._y0), 
                         size = (self._resX, self._resY),
                         style = style
                        ) 
        
        self.Window = SLMwindow(self, 
                                isImageLock = isImageLock,
                                res = (self._resX, self._resY)
                               )
        self.Show()
        
        self.Bind(EVT_NEW_IMAGE, self.OnNewImage)
        self.ShowFullScreen(not self.IsFullScreen(), wx.FULLSCREEN_ALL)
        self.SetFocus()
        
    def SetMonitor(self, monitor: int):
        if (monitor < 0 or monitor > wx.Display.GetCount()-1):
            raise ValueError('Invalid monitor (monitor %d).' % monitor)
        self._x0, self._y0, self._resX, self._resY = wx.Display(monitor).GetGeometry()
        
    def OnNewImage(self, event):
        self.Window.UpdateImage(event)
        
    
    def Quit(self):
        wx.CallAfter(self.Destroy)
        
        
class SLMwindow(wx.Window):
    
    def __init__(self,  *args, **kwargs):
        self.isImageLock = kwargs.pop('isImageLock')
        self.res = kwargs.pop('res')
        kwargs['style'] = kwargs.setdefault('style', wx.NO_FULL_REPAINT_ON_RESIZE) | wx.NO_FULL_REPAINT_ON_RESIZE
        super().__init__(*args, **kwargs)
        
        # hide cursor
        cursor = wx.StockCursor(wx.CURSOR_BLANK)
        self.SetCursor(cursor) 
        
        self.img = wx.Image(*self.res)
        self._Buffer = wx.Bitmap(*self.res)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(EVT_NEW_IMAGE, self.UpdateImage)
        self.Bind(wx.EVT_PAINT,self.OnPaint)
        
        self.OnSize(None)
        
    def OnPaint(self, event):
        self._Buffer = self.img.ConvertToBitmap()
        dc = wx.BufferedPaintDC(self, self._Buffer)
#         dc = wx.PaintDC(self)
#         dc.DrawBitmap(self._Buffer,0,0)
 
    def OnSize(self, event):
        # The Buffer init is done here, to make sure the buffer is always
        # the same size as the Window
        Size = self.GetClientSize()

        # Make new offscreen bitmap: this bitmap will always have the
        # current drawing in it, so it can be used to save the image to
        # a file, or whatever.
        self._Buffer = wx.Bitmap(*self.res)
        
    def UpdateImage(self, event):
        self.eventLock = event.eventLock
        self.img = event.img
        self.Refresh()
        
        self.ReleaseEventLock()
        
    def ReleaseEventLock(self):
        if self.eventLock:
            if self.eventLock.locked():
                self.eventLock.release()


        
        
class Client():
    """Client class to interact with slmPy running on a distant server."""
    def __init__(self):
        pass

    def start(self, 
              server_address: str, 
              port: int = 9999, 
              protocol: str = 'TCP',
              compression: str = 'zlib',
              compression_level: int = -1,
              wait_for_reply: bool = True
             ):
        """
        Parameters
        ----------
        server_address : str
            Address or network name of the server to connect to.
            Example: '192.168.0.100' / 'localhost'
        port : int, default 9999
            Port number of the listening socket on the server.
        protocol : str, default 'TCP'
            Protocol, 'TCP' or 'UDP'
        compression : str, default 'zlib'
            Compression algorithm to use before sending the data to the client.
            Can be 'zlib', 'gzip', 'bz2' or None for no compression.
            If the compression is not recognized, performs no compression.
        compression_level: int, default -1
            Level of compression. Depends on the compression algorithm.
        wait_for_reply: bool, default True
            If True, wait for the server confirmation before returning when sendArray is called.
            The server should use the argument `comfirm` in `listen_port()` with the same value.
            Be careful, some images can be missed!
        """
        
        if protocol == 'TCP':
            self.client = tcp_client(server_address = server_address, port = port)
#             self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#             self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
#             def send_all(message_size, data):
#                 self.client_socket.sendall(message_size + data)
                
        elif protocol == 'UDP':
            self.client = udp_client(server_address = server_address, port = port)
#             self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
#             def send_all(message_size, data):
#                 self.client_socket.sendto(message_size, (server_address, port))
#                 for chunk in chunks(PACKET_SIZE, data):
#                     self.client_socket.sendto(chunk, (server_address, port))
                
        else:
            raise()
        
#         self.send_all = send_all
        self.compression = compression
        if compression_level == -1 and compression == 'bz2':
            compression_level = 9
        self.compression_level = compression_level
        self.wait_for_reply = wait_for_reply
#         try:
#             self.client.connect((server_address, port))
#             print(f'Connected to {server_address} on {port}')
#         except socket.error as e:
#             print(f'Connection to {server_address} on port {port} failed: {e}')
#             return

    def compress(self, np_array):
        data = np_array.tobytes()
        
        if self.compression == 'bz2':
             data = bz2.compress(data, 
                                 compresslevel = self.compression_level)
        elif self.compression == 'zlib':
             data = zlib.compress(data, 
                                  level = self.compression_level)
        elif self.compression == 'gzip':
             data = gzip.compress(data, 
                                  compresslevel = self.compression_level)
                
        return data
        

    def _send_numpy_array(self, np_array):
        """
        Send a numpy array to the connected socket.
        
        Parameters
        ----------
        np_array : array_like
            Numpy array to send to the listening socket.
        """
        
        # compress data according to compression parameters set at initialization
        data = self.compress(np_array)

        # then send data
        self.client.send_data(data)
        #self.client_socket.sendall(message_size + data)
        print('sent!')
        
    def sendArray(self, 
                  arr: np.ndarray, 
                  timeout: float = 10,
                  retries: int = 2):
        """
        Send a numpy array to the connected socket.
        
        Parameters
        ----------
        arr : array_like
            Numpy array to send to the server.
        timeout : float, default 10
            Timeout in seconds.
        retries : int, default 2
            Number of times to try sending data if an error occurs.
        """
        if not isinstance(arr, np.ndarray):
            print('Not a valid numpy image')
            return
        if not arr.dtype == np.uint8:
            print('Numpy array should be of uint8 type')


        for retry in range(retries):
            self._send_numpy_array(arr)
            t0 = time.time()
            if retry:
                print(f'Retrying: retry #{retry+1}')
            if self.wait_for_reply:
                while True:
                    buffer = self.client.receive(128)
                    if buffer:
                        print(f'Buffer = {buffer.decode()}')
                    if buffer and buffer.decode() == 'done':
                        print('Data transmitted')
                        return 1
                    elif buffer and buffer.decode() == 'err':
                        print('Error. Data not transmitted')
                        print('Wrong image size?')
                        break
                    elif time.time()-t0 > timeout:
                        print('Timeout reached.')
                        break
            else:
                return 1
        else:
            return -1
        
    def close(self):
        self.client_socket.shutdown(1)
        self.client_socket.close()
        
class SLMdisplay:
    """Interface for sending images to the display frame."""
    def __init__(self,
                 monitor = 1, 
                 isImageLock = False,
                 alwaysTop = False):       
        self.isImageLock = isImageLock    
        self.alwaysTop = alwaysTop
        self.monitor = monitor
        # Create the thread in which the window app will run
        # It needs its thread to continuously refresh the window
        self.vt =  videoThread(self)      
        self.eventLock = threading.Lock()
        if (self.isImageLock):
            self.eventLock = threading.Lock()
            
    def listen_port(self, 
                    port: int = 9999, 
                    protocol: str = 'TCP',
                    check_image_size: bool = False,
                    compression: str = 'zlib',
                    timeout: float = 10.,
                    buffer_size: int = 65536,
                    comfirm: bool = True):
        """
        Listen to a port for data transmission.
        Update the SLM with the array transmitted.
        Use a `Client` abject to send arrays from a client. 
        
        Parameters
        ----------
        port : int, default 9999
            The port to listen to and receive the data from.
        protocol : str, default 'TCP'
            Protocol, 'TCP' or 'UDP'.
        check_image_size : bool, default False
            If `check_image_size` is True, an image that does not fit
            the resolution of the SLM will not be displayed and an 
            error will be returned to the client.
        compression : string, default 'zlib'
            Compression protocol of the data.
            Should be None, 'zlib', 'bz2' or 'gzip'
        timeout :  float, default 10.
            Timeout in seconds.
        buffer_size : int, default 65536
            Size of the buffer to receive data.
            Should be large enough to reduce latency for high resolutions.
        comfirm: bool, default True
            If True send a confirmation signal to the client.
        """
        if protocol == 'TCP':
#             server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#             server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
#             server_socket.bind(('',port))
#             server_socket.listen(1)
#             print(f'waiting for a connection on port {port}')
#             client_connection,client_address=server_socket.accept()
#             print(f'connected to {client_address[0]}')     
            self.server = tcp_server(port = port, buffer_size = buffer_size)
            self.server.run()
        
#             receive = lambda x: client_connection.recv(x)
#             send = lambda x: client_connection.sendall(x)
            
            
#             print(f'payload_size = {payload_size}')
            while True:
#                 data=b''
                
#                 while len(data) < payload_size:
#                     data += self.server.receive(PACKET_SIZE)
# #                     print(f'data length = {len(data)}')

#                 t0 = time.time()
#                 packed_msg_size = data[:payload_size]
#                 data = data[payload_size:]
#                 msg_size = struct.unpack("i", packed_msg_size)[0]
#                 # Retrieve all data based on message size
#                 print(f'Waiting for data of size {msg_size}')
#                 while len(data) < msg_size:      
#                     data += self.server.receive(buffer_size)
#                     if time.time()-t0 > timeout:
#                         print('Timeout!')
#                         print(f'{time.time()-t0:.3f}')
#                         self.server.send(b'err')
#                         continue

#                 frame_data = data[:msg_size]
#                 data = data[msg_size:]
                
                frame_data, data = self.server.get_data(
                                            buffer_size = buffer_size, 
                                            timeout = timeout
                )
    
                if compression == 'bz2':
                    frame_data = bz2.decompress(frame_data)
                elif compression == 'zlib':
                    frame_data = zlib.decompress(frame_data)
                elif compression == 'gzip':
                    frame_data = gzip.decompress(frame_data)

                # Extract frame
                print('Received image')
                #image = pickle.loads(frame_data, encoding='latin1')
                image = np.frombuffer(frame_data, dtype = np.uint8)

                resX, resY = self.vt.frame._resX, self.vt.frame._resY
                if check_image_size and not len(image) == resY*resX:
                    print('Buffer size does not match image size')
                    print(f'Expected {resX*resY}, received: {len(image)}')
                    self.server.send(b'err')
                    continue
                
                image = image.reshape([resY,resX])
                print('Updating SLM')
                self.updateArray(image, sleep = 0.)
                print('Done')
                self.server.send(b'done')
            
        elif protocol == 'UDP':
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            server_socket.bind(("", port))
            receive = lambda x: server_socket.recvfrom(x)[0]
            
            while True:
                
                t0 = time.time()
                packed_msg_size, address = server_socket.recvfrom(PACKET_SIZE)
                msg_size = struct.unpack("i", packed_msg_size)[0]
                
                n_chunks = ceil(msg_size/PACKET_SIZE)
                print(packed_msg_size, "OO")
                
                data=b''
                for _ in range(n_chunks):
                    data += receive(PACKET_SIZE)
                    if time.time()-t0 > timeout:
                        print('Timeout!')
                        server_socket.sendto(b'err', address)
                        continue

                    print(data, ' >>'*10)
                
                
                frame_data = data[:msg_size]
                
                print(len(frame_data))
                print(msg_size)
                print('=='*20)
                
                if compression == 'bz2':
                    frame_data = bz2.decompress(frame_data)
                elif compression == 'zlib':
                    frame_data = zlib.decompress(frame_data)
                elif compression == 'gzip':
                    frame_data = gzip.decompress(frame_data)

                # Extract frame
                print('Received image')
                #image = pickle.loads(frame_data, encoding='latin1')
                image = np.frombuffer(frame_data, dtype = np.uint8)

                resX, resY = self.vt.frame._resX, self.vt.frame._resY
                if check_image_size and not len(image) == resY*resX:
                    print('Buffer size does not match image size')
                    print(f'Expected {resX*resY}, received: {len(image)}')
                    server_socket.sendto(b'err', address)
                    continue



                image = image.reshape([resY,resX])
                print('Updating SLM')
                self.updateArray(image, sleep = 0.)
                server_socket.sendto(b'done', address)

        else:
            raise()
#         server_socket=socket.socket() 
#         server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
        
        
            
            


        client_connection.close()
        server_socket.close()
        
    def getSize(self):
        return self.vt.frame._resX, self.vt.frame._resY

    def updateArray(self, array, sleep = 0.2):
        """
        Update the SLM monitor with the supplied array.
        Note that the array is not the same size as the SLM resolution,
        the image will be deformed to fit the screen.
        
        Parameters
        ----------
        array : array_like
            Numpy array to display, should be the same size as the resolution of the SLM.
        sleep : float
            Pause in seconds after displaying an image.
        """
        # create a wx.Image from the array
        h,w = array.shape[0], array.shape[1]

        if len(array.shape) == 2:
            bw_array = array.copy()
            bw_array.shape = h, w, 1
            color_array = np.concatenate((bw_array,bw_array,bw_array), axis=2)
            data = color_array.tostring()
        else :      
            data = array.tostring()   
        img = wx.ImageFromBuffer(width=w, height=h, dataBuffer=data)
        # Create the event
        event = ImageEvent()
        event.img = img
        event.eventLock = self.eventLock
        
        # Wait for the lock to be released (if isImageLock = True)
        # to be sure that the previous image has been displayed
        # before displaying the next one - it avoids skipping images
        if (self.isImageLock):
            event.eventLock.acquire()
        # Wait (can bug when closing/opening the SLM too quickly otherwise)
        time.sleep(sleep)
        # Trigger the event (update image)
        self.vt.frame.AddPendingEvent(event)
        
    def close(self):
         self.vt.frame.Quit()

class videoThread(threading.Thread):
    """Run the MainLoop as a thread. 
    WxPython is not designed for that, it will give a warning on exit, but it will work, 
    see: https://wiki.wxpython.org/MainLoopAsThread
    Access the frame with self.frame."""
    def __init__(self, parent,autoStart=True):
        threading.Thread.__init__(self)
        self.parent = parent
        # Set as deamon so that it does not prevent the main program from exiting
        self.setDaemon(1)
        self.start_orig = self.start
        self.start = self.start_local
        self.frame = None #to be defined in self.run
        self.lock = threading.Lock()
        self.lock.acquire() #lock until variables are set
        if autoStart:
            self.start() #automatically start thread on init
    def run(self):
        app = wx.App()
        frame = SLMframe(monitor = self.parent.monitor, 
                         isImageLock = self.parent.isImageLock,
                         alwaysTop = self.parent.alwaysTop)
        frame.Show(True)
        self.frame = frame
        self.lock.release()
        # Start GUI main loop
        app.MainLoop()

    def start_local(self):
        self.start_orig()
        # Use lock to wait for the functions to get defined
        self.lock.acquire()
