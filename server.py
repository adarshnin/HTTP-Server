#!/usr/bin/python3
import socket
import threading
import sys
import os.path
import time
from time import mktime
import platform
from datetime import datetime
import pytz
from tzlocal import get_localzone
#Encoding modules
import gzip
import zlib
import brotli
#For Content-MD5
import hashlib
#For parsing POST data
from urllib.parse import urlparse, parse_qs
#To write in csv files
import csv
#To generate random hex number
import uuid
#For encoding
import codecs
#generating cryptographically strong random numbers for cookie
from secrets import token_urlsafe
#For log file
import logging 
#To parse the config file
import configparser

DocumentRoot = ""
ServerRoot = ''
clientList = []

#For handling max simulateneous connections
MaxConn = 0
PORT = 0
lock = threading.Lock()

#Bold
BOLD = '\033[1m'
#Reset Color
RESET = "\033[0;0m"

logger = ""
ER_LOG_FILE = ""

allow_methods = []
server_files = []

sys.tracebacklimit = 0

# File extensions and their content types
file_extn = {'.html':'text/html', '.txt':'text/plain', '.md': 'text/markdown', '.csv': 'text/csv','.css': 'text/css', '': 'text/plain', '.jpeg':'image/webp', '.jpg':'image/jpg', '.png':'image/png', '.gif': 'image/gif', '.ico': 'image/x-icon', '.mp3' : 'audio/mpeg', '.php':'application/x-www-form-urlencoded', '.pdf': 'application/pdf', '.js': 'application/javascript', '.mp4' :'video/mp4'}
#Month and their place in year
month_val = { 'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12 }
days =["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] 

class serverThread(threading.Thread):
    def __init__(self, addr, connectionSocket):
        threading.Thread.__init__(self)
        self.socket = connectionSocket
        global clientList
        self.client_info = addr
    def run(self):
        empty_line_cnt = 0
        request_msg = []
        bin_body = bytearray(b'')
        put_body = ""
        put_method = False
        bin_file = False
        byte_content = False
        content_length = 0

        bin_post_method = False
        req_len = 0
        
        while True:
            sentence = self.socket.recv(8192)
            try:
                sentence = sentence.decode()
                if (byte_content):
                    bin_body.extend(sentence.encode())

            except UnicodeDecodeError:
                put_method = True
                bin_file = True
                res = sentence.split(b'\r\n\r\n')
                empty_cnt = 0
                empty_line = bytearray(b'\r\n\r\n')
                for i in res:
                    if (not(byte_content) and decode_stream(i)):
                        req_len += len(i)
                        i = i.decode()
                        find_method_cnt = 0
                        for line in i.split('\r\n'):
                            if (line != ""):
                                request_msg.append(line)
                                if (find_method_cnt == 0):
                                    if (line.split()[0] == "POST"):
                                        bin_post_method = True
                                        find_method_cnt = 1
                                if ("Content-Length:" in line):
                                    content_length = int(line.split()[1])
                    else:
                        if (empty_cnt >= 2):
                            bin_body.extend(empty_line)
                        i = bytearray(i)
                        bin_body.extend(i)
                        byte_content = True
                    empty_cnt+=1
            try:
                if (sentence.split()[0] == "PUT"):
                    put_method = True
            except:
                pass
            if (not(put_method)):
                if (sentence is not None):
                    for i in sentence.split('\r\n'):
                        if (i != ""):
                            request_msg.append(i)
                    
                    if (sentence == "\r\n" or "\r\n\r\n" in sentence):
                        break
            else:
                content_len = 0
                if (not(bin_file)):
                    for line in sentence.split('\r\n'):
                        if (empty_line_cnt == 0):
                            if(line != ''):
                                request_msg.append(line)
                            content_len_header = line.split()
                            try:
                                if (content_len_header[0] == "Content-Length:"):
                                    content_len = int(content_len_header[1])
                            except IndexError:
                                pass
                        else:
                            put_body += line
                        if (content_len != 0 and len(put_body) == content_len):
                            empty_line_cnt = -1
                            break                        

                        if (line == ''):
                            empty_line_cnt=1
                    if (empty_line_cnt == -1):
                        #To Indicate end of Put message body
                        break
                        
                else:
                    if (bin_post_method):
                        if (req_len + len(bin_body) >= content_length):
                            break
                    #For PUT
                    elif (len(bin_body) >= content_length):
                        break
                
        method = request_msg[0].split()[0]
        if (method == "GET" or method == "HEAD"):
            get_handle(self.socket,request_msg, method, self.client_info)
        elif(method == "POST"):
            post_handle(self.socket, request_msg, self.client_info, bin_body)
        elif(method == "PUT"):
            if (bin_file):
                put_handle(self.socket, request_msg, bin_body, bin_file, self.client_info)
            else:
                put_handle(self.socket, request_msg, put_body, bin_file, self.client_info)
            put_body = ""
            bin_body = bytearray(b'')
        elif(method == "DELETE"):
            delete_handle(self.socket, request_msg, self.client_info)
        else:
            #Method not allowed
            status_handler(self.socket, 405, self.client_info, request_msg)
        
        #After closing connection, remove from list
        global clientList
        clientList.remove(self.client_info)

def parse_config():
    config = configparser.ConfigParser()
    config.read('server.conf')

    global DocumentRoot
    global MaxConn
    global server_files
    global logger
    global ER_LOG_FILE
    global PORT
    global ServerRoot
    global allow_methods
    global COOKIE_FILE

    DocumentRoot = config['default']['DocumentRoot']
    MaxConn = int(config['default']['MaxConn'])
    ServerRoot = config['default']['ServerRoot']
    server_files = config['default']['Server_files']
    allow_methods = config['default']['AllowMethods']
    PORT = int(config['default']['ServerPort'])

    LOG_FILE = config['Log']['access_log']
    ER_LOG_FILE = config['Log']['error_log']

    COOKIE_FILE = ServerRoot + config['cookie']['cookie_file']
    FORMAT = '%(message)s'
    logging.basicConfig(filename=LOG_FILE, format=FORMAT)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    #To clear cookies
    open(COOKIE_FILE, 'w').close()

def decode_stream(content):
    try:
        content.decode()
        return True
    except UnicodeDecodeError:
        return False
#For encoding files
def encode_file(value, encoded_file, response, file_path):
    if ("gzip" in value):
        encoded_file = ServerRoot + 'encoded/file.gz'
        f_in = open(file_path, "rb")
        f_out = gzip.open(encoded_file, 'wb')
        f_out.writelines(f_in)
        f_out.close()
        f_in.close()
        response.append("Content-Encoding: gzip")
        file_size = os.path.getsize(encoded_file)
    elif("deflate" in value):
        encoded_file = ServerRoot + 'encoded/deflate_out.zz'
        original_data = open(file_path, 'rb').read()
        compressed_data = zlib.compress(original_data, zlib.Z_BEST_COMPRESSION)
        f = open(encoded_file, 'wb')
        f.write(compressed_data)
        f.close()
        response.append("Content-Encoding: deflate")
        file_size = os.path.getsize(encoded_file)
    elif("br" in value):
        encoded_file = ServerRoot + 'encoded/br_out.br'
        original_data = open(file_path, 'rb').read()
        compressed_data = brotli.compress(original_data)
        f = open(encoded_file, 'wb')
        f.write(compressed_data)
        f.close()
        response.append("Content-Encoding: br")
        file_size = os.path.getsize(encoded_file)
    return encoded_file, file_size
#For Conditional GET
def check_if_modified(time_value, file_path):
    try:
        time_diff = mktime(time.localtime()) - mktime(time.gmtime())
        time_value.replace(",", "")
        time_value = time_value.split()
        mday_time = time_value[4].split(":")
        mtime = datetime(int(time_value[3]), month_val[time_value[2]], int(time_value[1]), int(mday_time[0]), int(mday_time[1]), int(mday_time[2]))

        #Converting to GMT/UTC time and comparing
        dt = os.path.getmtime(file_path)
        naive = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(dt))
        naive = datetime.strptime (naive, "%Y-%m-%d %H:%M:%S")
        #Get local timezone
        local = get_localzone()
        local_dt = local.localize(naive, is_dst=None)
        utc_dt = local_dt.astimezone(pytz.utc)
        #If If-Modified-Since time <= Last Modified time
        if (mtime.timestamp() + time_diff < utc_dt.timestamp()):
            #200 OK Response
            return True
        else:
            return False
    except:
        return True

def last_modified(file_path):
    #Get Last Modified time in GMT
    dt = os.path.getmtime(file_path)
    naive = time.strftime('%A:%Y:%m:%d:%H:%M:%S', time.localtime(dt))
    naive = datetime.strptime (naive, "%A:%Y:%m:%d:%H:%M:%S")
    local = get_localzone()
    local_dt = local.localize(naive, is_dst=None)
    utc_dt = local_dt.astimezone(pytz.utc)
    day = days[utc_dt.weekday()]
    utc_dt = str(utc_dt).split("+")[0]
    d_date = utc_dt.split()[0].split("-")
    d_time = utc_dt.split()[1]
    dTime = str(day[:3])+ ", " + d_date[2] + " " + str(list(month_val.keys())[list(month_val.values()).index(int(d_date[1]))] + " ") + d_date[0] + " " + d_time + " GMT"
    return dTime

def post_create_file(filename, content, bin_file):
    post_dir = ServerRoot + "post/"
    if (bin_file):
        f = open(post_dir+filename, "wb")
    else:
        f = open(post_dir+filename, "w")
    f.write(content)
    f.close()

def store_cookie(cookie_value):
    f = open(COOKIE_FILE, "a")
    f.write(cookie_value+"\n")
    f.close()
def get_cookies():
    f = open(COOKIE_FILE, "r")
    content = f.read()
    return content.split("\n")

def status_handle_304(connectionSocket, file_path):
    response = []
    response.append("HTTP/1.1 304 Not Modified")
    response.append(str("Date: ")+time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.gmtime()))
    response.append(str("Server: Scorpion/0.1 ")+str("(")+platform.system()+str(")"))
    response.append(str("Connection: close"))
    response.append(str("Content-Length: ")+str(os.path.getsize(file_path)))
    response.append(str("Last-Modified: ")+last_modified(file_path))
    response.append("\r\n")         
    response = "\r\n".join(response).encode()
    connectionSocket.send(response)
    connectionSocket.close()

def status_handler(connectionSocket, status_code, client_info, request_msg, file_path = None):
    response = []
    error_file = ServerRoot + "status_handler/"+str(status_code)+"/index.html"
    referer = "-"
    user_agent = "-"

    if (status_code == 400):
        response.append("HTTP/1.1 400 Bad Request")
    elif(status_code == 403):
        response.append("HTTP/1.1 403 Forbidden")
    elif(status_code == 404):
        response.append("HTTP/1.1 404 Not Found")
    elif(status_code == 405):
        response.append("HTTP/1.1 405 Method Not Allowed")
        response.append("Allow: " + allow_methods)
    elif(status_code == 415):
        response.append("HTTP/1.1 415 Unsupported Media Type")
    response.append(str("Date: ")+time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.gmtime()))
    response.append(str("Server: Scorpion/0.1 ")+str("(")+platform.system()+str(")"))
    response.append(str("Connection: close"))
    try:
        response.append(str("Content-Length: ")+str(os.path.getsize(file_path)))
        response.append(str("Last-Modified: ")+last_modified(file_path))
    except:
        #If file does not exist
        pass
    try:
        #For useragent
        for header in request_msg:
            key = header.split(":")
            if (key[0] == "User-Agent"):
                user_agent = key[1]
                break
    except:
        pass

    response.append("\r\n")         
    response = "\r\n".join(response).encode()
    connectionSocket.send(response)
    f = open(error_file, "rb")
    connectionSocket.sendfile(f)
    file_size = os.path.getsize(error_file)
    f.close()
    connectionSocket.close()

    current_time = time.strftime("%d/%b/%Y %H:%M:%S +05:30", time.gmtime())
    logger.error('{} - - [{}] "{}" {} {} {} {}'.format(client_info,current_time,request_msg[0],status_code,file_size,referer,user_agent))
    error_logger = open(ER_LOG_FILE, "a+")
    error_logger.writelines('{} - - [{}] "{}" {} {} {} {}\n'.format(client_info,current_time,request_msg[0],status_code,file_size,referer,user_agent))
    error_logger.close()

def delete_handle(connectionSocket, request_msg, client_info):
    response = []
    cookie_exist = False
    cookie_values = get_cookies()

    #For Log file
    st_code = "-"
    file_size = "-"
    user_agent = "-"
    referer = "-"

    file_path = request_msg[0].split()[1]

    if (file_path[0] == "/"):
        file_path = file_path[1:]

    file_path = DocumentRoot + file_path

    if (file_path in server_files):
        status_handler(connectionSocket, 403, client_info, request_msg)
        return

    if os.path.exists(file_path):
        if os.path.isdir(file_path):  
            os.rmdir(file_path)  
        elif os.path.isfile(file_path):  
            os.remove(file_path)
        response.append("HTTP/1.1 200 OK")
    else:
        status_handler(connectionSocket, 404, client_info, request_msg)
        return

    for header in request_msg:

        if (":" in header):
            header = header.split(": ")
        else:
            header = header.split(" ")

        try:
            key = header[0]
            value = header[1]
        except:
            #Bad request
            status_handler(connectionSocket, 400, client_info, request_msg, file_path)
            return
        
        if (key == "Host"):
             #Date header
            response.append(str("Date: ")+time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.gmtime()))
            response.append(str("Server: Scorpion/0.1 ")+str("(")+platform.system()+str(")"))
            
        elif(key == "Cookie"):
            value = value.split(";")
            value = value[0].split("=")[1]
            if (value in cookie_values):
                #Already existing cookie
                cookie_exist = True
            else:
               #Invalidate the cookie by expires if it does not exist in server storage
                response.append("Set-Cookie: cookieID="+value+"; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly")
        elif(key == "User-Agent"):
            user_agent = value
        elif(key == "Referer"):
            referer = value
        elif(key == "Connection"):
            response.append("Connection: close")
    if (not(cookie_exist)):
        #creating cookie
        #To generate cookie value
        c_value = token_urlsafe(16) 
        cookie_values.append(c_value)
        #Set Expiry time of 2 days(172800 sec) from now
        response.append("Set-Cookie: cookieID="+c_value+"; Expires="+time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.gmtime(time.time() + 172800)) +"; HttpOnly")
        store_cookie(c_value)

    response.append("\r\n")         
    #Adding newline between every item in list using join()
    response = "\r\n".join(response).encode()
    connectionSocket.send(response)
    f = open(ServerRoot + "delete/del.html", "rb")
    connectionSocket.sendfile(f)
    f.close()
    connectionSocket.close()

    current_time = time.strftime("%d/%b/%Y %H:%M:%S +05:30", time.gmtime())
    logger.info('{} - - [{}] "{}" {} {} {} {}'.format(client_info,current_time,request_msg[0],st_code,file_size,referer,user_agent))
    logger.debug(request_msg)
    logger.debug(response)

def put_handle(connectionSocket,request_msg, put_body, bin_file, client_info):
    response = []
    file_path = ""

    #For Log file
    st_code = "-"
    file_size = "-"
    user_agent = "-"
    referer = "-"

    cookie_exist = False
    cookie_values = get_cookies()

    try:
        file_path = request_msg[0].split()[1]
    except:
        status_handler(connectionSocket, 400, client_info, request_msg, file_path)
        return

    if (file_path[0] == "/"):
        file_path = file_path[1:]

    file_path = DocumentRoot + file_path
    
    if (file_path in server_files):
        status_handler(connectionSocket, 403, client_info, request_msg)
        return

    if (os.path.isfile(file_path) and not(bin_file)):
        #Overwrite the file 
        f = open(file_path, "r")
        file_content = f.read()
        f.close()
        response.append("HTTP/1.1 204 No Content")
        st_code = 204

        if (file_content == put_body):
            #send validator fields if resource data equal to data in PUT request
            response.append(str("Last-Modified: ")+last_modified(file_path))
            response.append('ETag: "'+str(uuid.uuid4().hex)+'"')
        else:
            f = open(file_path, "w")
            f.write(put_body)
            f.close()    
    else:
        #Create the file
        if (bin_file):
            f = open(file_path, "wb")
            f.write(put_body)
            f.close()
        else:
            f = open(file_path, "w")
            f.write(put_body)
            f.close()   
        response.append("HTTP/1.1 201 Created")
        st_code = 201
    
    for header in request_msg:
        if (":" in header):
            header = header.split(": ")
        else:
            header = header.split(" ")

        try:
            key = header[0]
            value = header[1]
        except:
            #Bad request
            status_handler(connectionSocket, 400, client_info, request_msg, file_path)
            return
        
        if (key == "Host"):
             #Date header
            response.append(str("Date: ")+time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.gmtime()))
        elif(key == "Content-Type"):
            response.append('ETag: "'+str(uuid.uuid4().hex)+'"')
            response.append(str("Server: Scorpion/0.1 ")+str("(")+platform.system()+str(")"))
        elif(key == "Cookie"):
            value = value.split(";")
            value = value[0].split("=")[1]
            if (value in cookie_values):
                #Already existing cookie
                cookie_exist = True
            else:
               #Invalidate the cookie by expires if it does not exist in server storage
                response.append("Set-Cookie: cookieID="+value+"; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly")
        elif(key == "User-Agent"):
            user_agent = value
        elif(key == "Referer"):
            referer = value
        elif(key == "Connection"):
            response.append("Connection: close")
    if (not(cookie_exist)):
        #creating cookie
        #To generate cookie value
        c_value = token_urlsafe(16) 
        cookie_values.append(c_value)
        #Set Expiry time of 2 days(172800 sec) from now
        response.append("Set-Cookie: cookieID="+c_value+"; Expires="+time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.gmtime(time.time() + 172800)) +"; HttpOnly")
        store_cookie(c_value)

    response.append("Content-Location: "+"/"+file_path)
    response.append("\r\n")         
    #Adding newline between every item in list using join()
    response = "\r\n".join(response).encode()
    connectionSocket.send(response)
    connectionSocket.close()
    current_time = time.strftime("%d/%b/%Y %H:%M:%S +05:30", time.gmtime())
    logger.info('{} - - [{}] "{}" {} {} {} {}'.format(client_info,current_time,request_msg[0],st_code,file_size,referer,user_agent))
    logger.debug(request_msg)
    logger.debug(response)

def post_handle(connectionSocket,request_msg, client_info, file_body):
    response = []

    #For Log file
    st_code = "-"
    file_size = "-"
    user_agent = "-"
    referer = "-"
    post_data = request_msg[-1]
    post_data = parse_qs(post_data)
    file_path = ServerRoot + "post/success.html"
    encoded_file = False
    f = None
    cookie_exist = False
    #For handling multi-part form data (including files)
    multi_part = False

    if ("Content-Disposition" in "".join(request_msg)):
        multi_part = True

    cookie_values = get_cookies()
    #Post data stored here
    data_file = ServerRoot + "post/data.csv"
    #Handle fields    
    fields = [] 
    for key in post_data:
        post_data[key] = post_data[key][0]
        fields.append(post_data[key])

    row = list(post_data.values())
    #Check if file already exists
    if (os.path.isfile(data_file)):
        with open(data_file, 'a') as csvfile:
            # creating a csv writer object  
            csvwriter = csv.writer(csvfile)   
            # writing the data row  
            csvwriter.writerow(row) 
        response.append("HTTP/1.1 200 OK")
        st_code = 200
    else:
        with open(data_file, 'w') as csvfile:  
            # creating a csv writer object  
            csvwriter = csv.writer(csvfile)  
            # writing the fields  
            csvwriter.writerow(fields)  
            # writing the data row  
            csvwriter.writerow(row)
        response.append("HTTP/1.1 201 Created")
        st_code = 201
    response.append('Location: ' + data_file)

    mul_cnt = 0
    form_data = ""
    mul_filename = ""
    contlen_header = False
    contdisp_header = False
    for header in request_msg:
        if (mul_cnt == 1):
            form_data += header + " "
            mul_cnt = 0
            continue
        if (mul_cnt == 2 and not(multi_part)):
            post_create_file(mul_filename, header, False)
        if (":" in header):
            header = header.split(": ")
        else:
            header = header.split(" ")
        try:
            key = header[0]
            value = header[1]
        except:
            pass

        if(key == "Host"):
            #Date header
            response.append(str("Date: ")+time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.gmtime()))
        elif(key == "Connection"):
            #For non-persistant connections
            response.append(str("Connection: close"))
        elif(key == "Accept-Language"):
            #Files only availaible in en
            response.append(str("Content-Language: en"))
        elif(key == "User-Agent"):
            user_agent = value
            response.append(str("Last-Modified: ")+last_modified(file_path))
            #Specifying Server name and OS
            response.append(str("Server: Scorpion/0.1 ")+str("(")+platform.system()+str(")"))
        elif(key == "Accept-Encoding"):
            if ("gzip" in value or "deflate" in value or "br" in value):
                encoded_file, file_size = encode_file(value, encoded_file, response, file_path)
            else:
                file_size = os.path.getsize(file_path)
            response.append(str("Content-Length: ")+str(file_size))
            #32 hexadecimal digits For Etag
            response.append('ETag: "'+str(uuid.uuid4().hex)+'"')
        elif(key == "Cookie"):
            value = value.split(";")
            value = value[0].split("=")[1]
            if (value in cookie_values):
                #Already existing cookie
                cookie_exist = True
            else:
               #Invalidate the cookie by expires if it does not exist in server storage
                response.append("Set-Cookie: cookieID="+value+"; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly")
        elif(key == "Referer"):
            referer = value
        elif(key == "Content-Disposition"):
            contdisp_header = True
            multi_part = True
            #For getting form-data(multi-part)
            mul_cnt = 1
            if ("filename" in value):
                mul_filename = value.split("; ")[2].split('"')[1]
                mul_cnt = 0
                form_data += mul_filename
                post_data = form_data
                if (contlen_header):
                    if (bool(file_body)):
                        post_create_file(mul_filename, file_body, True)
        elif(key == "Content-Type" and multi_part == True):
            #For creating file
            contlen_header = True
            mul_cnt = 2
            if (contdisp_header):
                if (bool(file_body)):
                    post_create_file(mul_filename, file_body, True)

    if (not(cookie_exist)):
        #creating cookie
        #To generate cookie value
        c_value = token_urlsafe(16) 
        cookie_values.append(c_value)
        #Set Expiry time of 2 days(172800 sec) from now
        response.append("Set-Cookie: cookieID="+c_value+"; Expires="+time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.gmtime(time.time() + 172800)) +"; HttpOnly")
        store_cookie(c_value)
        
    if (not(encoded_file)):
        f = open(file_path, "rb")

    else:
        f = open(encoded_file, 'rb')

    response.append("\r\n")         
    response = "\r\n".join(response).encode()
    connectionSocket.send(response)
    connectionSocket.sendfile(f)
    f.close()
    connectionSocket.close()

    current_time = time.strftime("%d/%b/%Y %H:%M:%S +05:30", time.gmtime())
    logger.info('{} - - [{}] "{}" {} {} {} {} {}'.format(client_info,current_time,request_msg[0],st_code,file_size,referer,user_agent, post_data))
    logger.debug(request_msg)
    logger.debug(response)

def get_handle(connectionSocket,request_msg, method, client_info):
    response = []
    file_path = ""
    encoded_file = False
    f = None
    #For Log file
    st_code = "-"
    file_size = "-"
    user_agent = "-"
    referer = "-"
    cookie_exist = False
    cookie_values = get_cookies()
    for header in request_msg:

        if (":" in header):
            header = header.split(": ")
        else:
            header = header.split(" ")

        try:
            key = header[0]
            value = header[1]
        except:
            #Bad request
            status_handler(connectionSocket, 400, client_info, request_msg, file_path)
            return

        if (key == method):
            file_path = value
            #remove / from the start of the path
            if (file_path[0] == '/'):
                file_path = file_path[1:]
            #Root of server
            if (file_path == ""):
                #Redirect
                response.append("HTTP/1.1 301 Moved Permanently")
                response.append(str("Date: ")+time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.gmtime()))
                response.append("Location: /index.html")
                response.append("\r\n")         
                response = "\r\n".join(response).encode()
                connectionSocket.send(response)
                connectionSocket.close()
                return

            file_path = DocumentRoot + file_path

            #version check - must be HTTP/1.1
            try:
                version = header[2].split("/")[1]
                if (version != "1.1"):
                    status_handler(connectionSocket, 505, client_info, request_msg, file_path)
                    return
            except:
                #Bad request
                status_handler(connectionSocket, 400, client_info, request_msg, file_path)
                return
            if (os.path.isfile(file_path)):
                response.append("HTTP/1.1 200 OK")
                st_code = 200
            else:
                status_handler(connectionSocket, 404, client_info, request_msg)
                return        
        elif(key == "Host"):
            #Date header
            response.append(str("Date: ")+time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.gmtime()))
        elif(key == "Connection"):
            #For non-persistant connections
            response.append(str("Connection: close"))
        elif(key == "Accept"):
            try:
                ext = os.path.splitext(file_path)
                ext = ext[1]
                type = file_extn[ext]
                response.append(str("Content-Type: ")+type)
            except:
                #For Unsupported Media types
                status_handler(connectionSocket, 415, client_info, request_msg, file_path)
                return
        elif(key == "Accept-Encoding"):
            if ("gzip" in value or "deflate" in value or "br" in value):
                lock.acquire()
                encoded_file, file_size = encode_file(value, encoded_file, response, file_path)
                lock.release()
            else:
                file_size = os.path.getsize(file_path)
            response.append(str("Content-Length: ")+str(file_size))
            
            #32 hexadecimal digits For Etag
            response.append('ETag: "'+str(uuid.uuid4().hex)+'"')
        elif(key == "Accept-Language"):
            #Files only availaible in en
            response.append(str("Content-Language: en"))
        elif(key == "User-Agent"):
            user_agent = value
            response.append(str("Last-Modified: ")+last_modified(file_path))
            #Time after which response considered stale - 5 days
            response.append("Expires: "+time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.gmtime(time.time() + 432000)))

            #Specifying Server name and OS
            response.append(str("Server: Scorpion/0.1 ")+str("(")+platform.system()+str(")"))
        elif(key == "Cookie"):
            value = value.split(";")
            value = value[0].split("=")[1]
            if (value in cookie_values):
                #Already existing cookie
                cookie_exist = True
            else:
               #Invalidate the cookie by expires if it does not exist in server storage
                response.append("Set-Cookie: cookieID="+value+"; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly")

        elif(key == "Referer"):
            referer = value

        elif(key == "If-Modified-Since"):
            if(check_if_modified(value,file_path)):
                #Normal Response with Body
                pass
            else:
                response = []
                st_code = 304
                status_handle_304(connectionSocket, file_path)
                current_time = time.strftime("%d/%b/%Y %H:%M:%S +05:30", time.gmtime())
                logger.info('{} - - [{}] "{}" {} {} {} {}'.format(client_info,current_time,request_msg[0],st_code,file_size,referer,user_agent))
                return
    if (not(cookie_exist)):
        #creating cookie
        #To generate cookie value
        c_value = token_urlsafe(16) 
        cookie_values.append(c_value)
        #Set Expiry time of 2 days(172800 sec) from now
        response.append("Set-Cookie: cookieID="+c_value+"; Expires="+time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.gmtime(time.time() + 172800)) +"; HttpOnly")
        store_cookie(c_value)
    
    if (not(encoded_file)):
        f = open(file_path, "rb")

    else:
        f = open(encoded_file, 'rb')

    digest = hashlib.md5(f.read()).hexdigest()
    response.append(("Content-MD5: ")+digest)
    response.append('\r\n')         
    #Adding newline between every item in list using join()
    encoded  = '\r\n'.join(response).encode()
    connectionSocket.send(encoded)
    if (method != "HEAD"):
        connectionSocket.sendfile(f)
    f.close()
    connectionSocket.close()
    current_time = time.strftime("%d/%b/%Y %H:%M:%S +05:30", time.gmtime())
    logger.info('{} - - [{}] "{}" {} {} {} {}'.format(client_info,current_time,request_msg[0],st_code,file_size,referer,user_agent))
    logger.debug(request_msg)
    logger.debug(response)

if __name__ == "__main__":
    parse_config()
    serverPort = PORT
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        serverSocket.bind(('localhost', serverPort))
    except PermissionError:
        print("You do not have permission. Retry with the 'sudo' command.")
        sys.exit(1)
    except OSError:
        port_str = "Port Number " + str(serverPort) + " is busy. Retry with another Port Number."
        print(port_str)
        sys.exit(1)
    
    print(BOLD, '------- Scorpion/0.1 HTTP Server Running on http://localhost:{} -------'.format(serverPort), RESET)

    serverSocket.listen(100000)
    while True:
        try:
            connectionSocket, addr = serverSocket.accept()
            if (len(clientList) < MaxConn):
                clientList.append(connectionSocket.getpeername())
                thread = serverThread(addr, connectionSocket)
                #Die when main thread dies
                thread.daemon = True
                thread.start()
        except KeyboardInterrupt:
            print("\nServer shutting down......")
            sys.exit(0)
    serverSocket.close()