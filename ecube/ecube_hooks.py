'''
Copyright (c) 2020 epiphani, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''
from __future__ import print_function
import threading

# A dictionary of execution data
execData = None

# python list/dict object
execOutput = None

# Return code of execution
execRetCode = 0

# The action to perform
execAction = None

THREAD_DATA_DICT = {}
DATA_LOCK = threading.Lock()

def getThreadData():
    thread_id = threading.current_thread().ident

    DATA_LOCK.acquire()

    if not thread_id in THREAD_DATA_DICT:
        THREAD_DATA_DICT[thread_id] = {}

    DATA_LOCK.release()

    print("getThreadData: THREAD_DATA_DICT: %s: %r" % (thread_id, THREAD_DATA_DICT))
    return THREAD_DATA_DICT[thread_id]

def removeThreadData():
    thread_id = threading.current_thread().ident

    DATA_LOCK.acquire()
    THREAD_DATA_DICT.pop(thread_id, None)
    DATA_LOCK.release()

    print("removeThreadData: THREAD_DATA_DICT: %s: %r" % (thread_id, THREAD_DATA_DICT))

def setExecAction(action):
    t = getThreadData()
    t['execAction'] = action

def getExecAction():
    return getThreadData()['execAction']

def setExecData(data):
    print("setting Exec Data: %r" % (data))
    t = getThreadData()
    t['execData'] = data

def getExecData():
    t = getThreadData()
    print("getting Exec Data: %r" % (t['execData']))
    return t['execData']

def setExecOutput(output, ret_code=0):
    print("setting Exec Output: %r" % (output))
    t = getThreadData()
    t['execOutput'] = output
    t['execRetCode'] = ret_code

def getExecOutput():
    t = getThreadData()
    print("getting Exec Output: %r" % (t['execOutput']))
    return t['execOutput'], t['execRetCode']
