# A dictionary of execution data
execData = None

# python list/dict object
execOutput = None

# Return code of execution
execRetCode = 0

# The action to perform
execAction = None

def setExecAction(action):
    global execAction
    execAction = action

def getExecAction():
    return execAction

def setExecData(data):
    global execData
    print("setting Exec Data: %r" % (data))
    execData = data

def getExecData():
    print("getting Exec Data: %r" % (execData))
    return execData

def setExecOutput(output, ret_code=0):
    global execOutput
    global execRetCode
    print("setting Exec Output: %r" % (output))
    execOutput = output
    execRetCode = ret_code

def getExecOutput():
    print("getting Exec Output: %r" % (execOutput))
    return execOutput, execRetCode