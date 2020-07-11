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
