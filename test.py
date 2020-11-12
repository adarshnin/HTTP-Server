#!/usr/bin/python3
import pandas as pd
import concurrent.futures
import requests
import time

SERVER_PORT = 50000
CONNECTIONS = 100
TIMEOUT = 10
req_len = 0

def test_get():
    tlds = open('urls/urls_get.txt').read().splitlines()
    urls = ['http://localhost:{}{}'.format(SERVER_PORT,x) for x in tlds]
    urls = urls[0:1]
    out = []
    thread(load_get_url, urls, out)

def test_2_get():
    tlds = open('urls/urls_get.txt').read().splitlines()
    urls = ['http://localhost:{}{}'.format(SERVER_PORT,x) for x in tlds]
    urls = urls[0:2]
    out = []
    thread(load_get_url, urls, out)

def test_cond_get():
    tlds = open('urls/urls_get.txt').read().splitlines()
    urls = ['http://localhost:{}{}'.format(SERVER_PORT,x) for x in tlds]
    urls = urls[0:1]
    out = []
    thread(load_cond_get_url, urls, out)

def load_get_url(url, timeout):
    ans = requests.get(url, timeout=timeout)
    assert ans.status_code == 200 or ans.status_code == 404
    return ans.status_code

def load_cond_get_url(url, timeout):
    ans = requests.get(url, headers = {"If-Modified-Since" : "Wed, 12 Nov 2020 23:28:00 GMT"}, timeout=timeout)
    assert  ans.status_code == 304 or ans.status_code == 200
    return ans.status_code

def test_head():
    tlds = open('urls/urls_get.txt').read().splitlines()
    urls = ['http://localhost:{}{}'.format(SERVER_PORT,x) for x in tlds]
    urls = urls[0:1]
    out = []
    thread(load_head_url, urls, out)

def load_head_url(url, timeout):
    ans = requests.head(url, timeout=timeout)
    assert ans.status_code == 200 or ans.status_code == 404
    return ans.status_code

def test_post():
    tlds = open('urls/urls_post.txt').read().splitlines()
    urls = ['http://localhost:{}{}'.format(SERVER_PORT,x) for x in tlds]
    urls = urls[0:1]
    out = []
    thread(load_post_url, urls, out)

def test_2_post():
    tlds = open('urls/urls_post.txt').read().splitlines()
    urls = ['http://localhost:{}{}'.format(SERVER_PORT,x) for x in tlds]
    urls = urls[0:1] * 2
    out = []
    thread(load_post_url, urls, out)
        
def load_post_url(url, timeout):
    files = {'upload_file': open('files/sample.pdf','rb')}
    post_data = {'first_name': 'Tony', 'last_name': 'Stark', 'company': 'Avengers', 'email': 'tony.stark@gmail.com', 'phone': '+919876916592', 'subject': 'Math', 'exist': 'on'}
    ans = requests.post(url, data = post_data, files = files, timeout=timeout, stream=True)
    assert ans.status_code == 200 or ans.status_code == 201
    return ans.status_code    

def test_put():
    tlds = open('urls/urls_put.txt').read().splitlines()
    urls = ['http://localhost:{}{}'.format(SERVER_PORT,x) for x in tlds]
    urls = urls[0:1]
    out = []
    thread(load_put_url, urls, out)

def test_2_put():
    tlds = open('urls/urls_put.txt').read().splitlines()
    urls = ['http://localhost:{}{}'.format(SERVER_PORT,x) for x in tlds]
    urls = urls[0:1] * 2
    out = []
    stress_thread(load_put_url, urls, out, 1)


def load_put_url(url, timeout):
    path = url.split(str(SERVER_PORT)+"/")[1]
    ans = requests.put(url, data=open(path, 'rb'), stream = True)
    assert ans.status_code == 201 or ans.status_code == 204 or ans.status_code == 403
    return ans.status_code

def test_del():
    tlds = open('urls/urls_del.txt').read().splitlines()
    urls = ['http://localhost:{}{}'.format(SERVER_PORT,x) for x in tlds]
    urls = urls[0:1]
    out = []
    thread(load_del_url, urls, out)

def test_2_del():
    tlds = open('urls/urls_del.txt').read().splitlines()
    urls = ['http://localhost:{}{}'.format(SERVER_PORT,x) for x in tlds]
    urls = urls[0:2]
    out = []
    thread(load_del_url, urls, out)

def load_del_url(url, timeout):
    ans = requests.delete(url)
    assert ans.status_code == 200 or ans.status_code == 403 or ans.status_code == 404
    return ans.status_code

def test_all(rep = 1):
    tlds = open('urls/urls_comm.txt').read().splitlines()
    urls = ['http://localhost:{}{}'.format(SERVER_PORT,x) for x in tlds]
    urls = urls * rep
    out = []
    thread(load_all_methods,urls, out)

def load_all_methods(url, timeout):
    global req_len
    if (req_len % 4 == 0):
        req_len += 1
        ans = requests.get(url, timeout=timeout)
        assert ans.status_code == 200 or ans.status_code == 404
        return ans.status_code
    elif (req_len % 4 == 1):
        req_len += 1
        ans = requests.head(url, timeout=timeout)
        assert ans.status_code == 200 or ans.status_code == 404
        return ans.status_code   
    elif (req_len % 4 == 2):
        req_len += 1
        post_data = {'first_name': 'Tony', 'last_name': 'Stark', 'company': 'Avengers', 'email': 'tony.stark@gmail.com', 'phone': '+919876916592', 'subject': 'Math', 'exist': 'on'}
        ans = requests.post(url, data = post_data, timeout=timeout, stream=True)
        assert ans.status_code == 200 or ans.status_code == 201
        return ans.status_code   
    elif (req_len % 4 == 3):
        req_len += 1
        ans = requests.delete(url)
        assert ans.status_code == 200 or ans.status_code == 403 or ans.status_code == 404
        return ans.status_code
        
def thread(method, urls, out):
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONNECTIONS) as executor:
        future_to_url = (executor.submit(method, url, TIMEOUT) for url in urls)
        time1 = time.time()
        for future in concurrent.futures.as_completed(future_to_url):
            try:
                data = future.result()
            except Exception as exc:
                data = str(type(exc))
            finally:
                out.append(data)

                print(str(len(out)),end="\r")

        time2 = time.time()

    print(f'Took {time2-time1:.2f} s')
    print("Response-Code\t ")
    s = pd.Series(out).value_counts()
    print((s.to_string()))
    print("-------------")

def stress_thread(method, urls, out, conn):
    with concurrent.futures.ThreadPoolExecutor(max_workers=conn) as executor:
        future_to_url = (executor.submit(method, url, TIMEOUT) for url in urls)
        time1 = time.time()
        for future in concurrent.futures.as_completed(future_to_url):
            try:
                data = future.result()
            except Exception as exc:
                data = str(type(exc))
            finally:
                out.append(data)

                print(str(len(out)),end="\r")

        time2 = time.time()

    print(f'Took {time2-time1:.2f} s')
    print("Response-Code\t ")
    s = pd.Series(out).value_counts()
    print((s.to_string()))
    print("-------------")

def test_stress_get(rep):
    tlds = open('urls/urls_get.txt').read().splitlines()
    urls = ['http://localhost:{}{}'.format(SERVER_PORT,x) for x in tlds]
    urls = urls[0:2] * rep
    out = []
    stress_thread(load_get_url, urls, out, 112)

def test_stress_post(rep):
    tlds = open('urls/urls_post.txt').read().splitlines()
    urls = ['http://localhost:{}{}'.format(SERVER_PORT,x) for x in tlds]
    urls = urls[0:1] * rep
    out = []
    stress_thread(load_post_url, urls, out, 102)

def test_stress_put(rep):
    tlds = open('urls/urls_put.txt').read().splitlines()
    urls = ['http://localhost:{}{}'.format(SERVER_PORT,x) for x in tlds]
    urls = urls[0:1] * rep
    out = []
    stress_thread(load_put_url, urls, out, 1)

def test_stress_del(rep):
    tlds = open('urls/urls_del.txt').read().splitlines()
    urls = ['http://localhost:{}{}'.format(SERVER_PORT,x) for x in tlds]
    urls = urls[0:2] * rep
    out = []
    stress_thread(load_del_url, urls, out, 92)

if __name__ == "__main__":
    test_get()
    # test_post()
    # test_head()
    # test_2_get()
    # test_2_post()
    # test_put()
    # test_2_put()
    # test_del()
    # test_2_del()

    # Testing Conditional Get
    # test_cond_get()

    # Can give argument for number of repetitions of methods
    # test_all(100)

    # Change TIMEOUT for Stress Test
    # Stress Test
    # test_stress_get(230)
    # test_stress_post(240)
    # test_stress_put(106)
    # test_stress_del(120)