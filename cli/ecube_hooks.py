# A dictionary of execution data
execData = None

# String in JSON format
execOutput = None

def setExecData(data):
    global execData
    print("setting Exec Data: %r" % (data))
    execData = data

def getExecData():
    print("getting Exec Data: %r" % (execData))
    return execData

def setExecOutput(output):
    global execOutput
    print("setting Exec Output: %r" % (output))
    execOutput = output

def getExecOutput():
    print("getting Exec Output: %r" % (execOutput))
    return execOutput