import sys
import time 
import json 
import base64, zlib
from tabulate import tabulate
sys.path.insert(0, "../epi-scripts/chatqlv2/cognito")
sys.path.insert(0, "../epi-scripts/chatqlv2/cognito/appsync-subscription-manager")

import CommonFunctions as cf

class Playbook(object):
    def __init__(self, args):

        self.logger = cf.Logger(log_to_file=True if args.log_file else False,
                              log_file=args.log_file)
        self.logger.set_log_level(cf.Logger.DEBUG)
        self.logger.log(cf.Logger.DEBUG, "initialized with %s" % args)
        self.env = cf.initEnv(args.login, self.logger)
        self.args = args 

    def show(self):
        d = self.env
        try:
            obj = cf.get_model_objects(d['endpoint'], d['id_token'],"AllRunbooks", None)
            extract = {'name', 'id', 'author', 'updatedAt', 'rbVars'}
            arr = []
            for val in obj:
                lst = { key:value for key,value in val.items() if key in extract}
                arr.append(lst)

            print (tabulate(arr, headers="keys"))
        except Exception as e:
            print ("error ", e)
            self.logger.log(cf.Logger.ERROR, "findAddWorkflow: %r" % (e))

    def run(self):
        self.dummy = self.findDummyInv()
        self.findRunPlaybook()

    def findDummyInv(self):
        d = self.env

        try:
            obj = cf.get_model_objects(d['endpoint'], d['id_token'], "Investigation", {'title': {'eq': 'dummy'}})
            for val in obj:
                if (val['title'] == 'dummy'):
                    INV = val['id']
                    return INV 
            return None 
        except Exception as e:
            self.logger.log(cf.Logger.ERROR, "findAddWorkflow: %r" % (e))

    def findRunPlaybook(self):
        d = self.env
        try:
            obj = cf.get_model_objects(d['endpoint'], d['id_token'], "AllRunbooks", {'name': {'eq': self.args.PBName}})
            for val in obj:
                if (val['name'] == self.args.PBName):
                    return self.runPB(val, d)
            self.logger.log(cf.Logger.ERROR, "PB NOT FOUND %s" % self.args.PBName)

        except Exception as e:
            self.logger.log(cf.Logger.ERROR, "findRunPlaybook: %r" % (e))
    def printOutput(self, out):
        oo = json.loads(out)
        for o in oo:
            for k,v in o.items():
                print k, v

    def runPB(self, val, d):
        rb = self.ExecutedRunbooksCreate(self.dummy, val['id'], val['name'], d)
        #rb = {'id': "cdadbc86-bb6c-45aa-a328-8064e47944fb"}
        count = 0
        print("Running Playbook %s ID %s for INV %s" % (val['name'], rb['id'], self.dummy))
        while(True):
            pb = self.findPB(rb['id'], d)
            if (pb == None):
                return None
            print pb['state']
            state = pb['state']
            if (state != "new" and state != "processing"):
                op = pb['output']
                if (pb['outputType'] == "gzip/b64encoded"):
                    op = zlib.decompress(base64.b64decode(op))
                self.printOutput(op)
                return state
            count += 1
            if (count > 20):
                print "Timeout"
                return None
            time.sleep(5)
            
    def ExecutedRunbooksCreate(self, investId, runbookId, title, d):
        author = d['username']
        cmd = {
            'investigationId': investId, 'author': author,
            'runbookID': runbookId,
            'title': title, 'state': "new"
        }
        try:
            link = cf.insert_obj(d['endpoint'], d['id_token'], "ExecutedRunbooks", cmd)
            return link
        except Exception as e:
            self.logger.log(cf.Logger.ERROR, "Executed RB CREATE : %r" % (e))
            return None

    def findPB(self, pbid, d):
        cmd = {'id': pbid}
        try:
            old = cf.execute_function_with_retry(cf.get_obj,
                                                (d['endpoint'], d['id_token'],
                                                "ExecutedRunbooks", cmd),
                                                {}, d['current_env'], cf.ARTIBOT_USERNAME, 1, 0,
                                                [], {}, {}, self.logger)
            if (old):
                return old
        except Exception as e:
            self.logger.log(cf.Logger.ERROR, "Cannot Find: %r" % (e))
            return None

