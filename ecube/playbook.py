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
import sys
import time
import json
import base64
import zlib
from tabulate import tabulate
import yaml
import os

import ecube.gql as cf
import ecube.playbook_create as pc

DEFAULT_KUBE_CONFIG = '~/.kube/config'
DEFAULT_AWS_CREDS = '~/.aws/credentials'

class Playbook(object):
    def __init__(self, args):

        try:
            tmp_lf = args.log_file
        except:
            tmp_lf = None
        self.logger = cf.Logger(log_to_file=True if tmp_lf else False,
                                log_file=tmp_lf)
        self.logger.set_log_level(cf.Logger.INFO)
        self.args = args
        self.local_install = False

        if 'local_install' in self.args and self.args.local_install == 'true':
            self.local_install = True

        if 'local_install_host' in self.args and self.args.local_install_host:
            self.local_install = True
            cf.set_local_gql_host(self.args.local_install_host)
        
        if 'local_install_port' in self.args and self.args.local_install_port:
            self.local_install = True
            cf.set_local_gql_port(self.args.local_install_port)

        if not self.local_install:
            self.env = cf.initEnv(args.login, self.logger)
        else:
            self.env = cf.init_local_env(args.username)

    def create(self):
        ff = pc.readDirectory(self)

        rtName = ff['pbFile']['name']
        rtDesc = ff['pbFile']['description']
        rbVars = None
        if (self.args.PBName):
            rtName = self.args.PBName
        print("Creating Playbook",rtName)

        if ('arguments' in ff['pbFile']):
            rbVars = ff['pbFile']['arguments']

        ff.pop('pbFile', None)
        d = self.env

        cmd = {
            'name': rtName,
            'description': rtDesc,
            'author': self.args.username,
            'type': 'longRunBook',
            'longSave': json.dumps(ff),
            'commands': None, 
            'RunBookConnectors': None, 
        }
        if rbVars != None:
            cmd['rbVars'] = json.dumps(rbVars)

        try:
            link = cf.insert_obj(
                d['endpoint'], d['id_token'], "AllRunbooks", cmd,
                use_local_instance=self.local_install)
            return link
        except Exception as e:
            self.logger.log(cf.Logger.ERROR, "Error creating playbook: %r" % (e))
            return

    def show(self):
        d = self.env
        try:
            obj = cf.get_model_objects(
                d['endpoint'], d['id_token'], "AllRunbooks", None,
                use_local_instance=self.local_install)
            extract = {'name', 'id', 'author', 'updatedAt', 'rbVars'}
            arr = []
            for val in obj:
                lst = {key: value for key,
                       value in val.items() if key in extract}
                arr.append(lst)

            print(tabulate(arr, headers="keys"))
        except Exception as e:
            print("error ", e)
            self.logger.log(cf.Logger.ERROR, "show playbooks: %r" % (e))

    def run(self):
        self.dummy = self.findDummyInv()
        self.findRunPlaybook()

    def add_stash(self, key, value, author, scope):
        d = self.env

        #Check if already exists, if so update
        try:
            obj = cf.get_model_objects(
                    d['endpoint'], d['id_token'],
                    "Stash", {'Key': {'eq': key}},
                    use_local_instance=self.local_install)

            if len(obj) >= 1:
                print("Found Existing stash for: %s, updating", key)
                #Stash entry already exists, update
                upd_obj = {
                    'id': obj[0]['id'], 
                    'Key': key,
                    'Value': value,
                    'author': author,
                    'scope': scope,}

                try:
                    cf.update_obj(
                        d['endpoint'], d['id_token'], "Stash", upd_obj,
                        use_local_instance=self.local_install)
                    print("Successfully updated stash, key: %s" % key)
                    return
                except Exception as e:
                    self.logger.log(cf.Logger.ERROR, "Error updating kube config in stash: %r" %(e))
            else:
                print("Key not found in stash, adding: %s", key)
        
        except Exception as e:
            self.logger.log(cf.Logger.ERROR, "Error in check to see if  kube config exists in stash: %r" %(e))
            return
        
        cmd = {
            'Key': key,
            'Value': value,
            'author': author,
            'scope': scope,
        }
        try:
            cf.insert_obj(
                d['endpoint'], d['id_token'], "Stash", cmd,
                use_local_instance=self.local_install)
            print("Successfully added stash, key: %s" % key)
        except Exception as e:
            self.logger.log(cf.Logger.ERROR, "Error loading kube config: %r" %(e))
    
    def kube_creds_add(self, kconf):

        # Create a dictionary and store the dictionary in stash

        kDict = {}
        
        #Store kube config
        try:
            kCfgStr = yaml.safe_dump(kconf, allow_unicode=True, default_flow_style=False)
        except yaml.YAMLError as exc:
            print(exc)
            return kDict

        kDict['kube_config'] = kCfgStr
        cName, uName = self.get_cluster_user(kconf)
        if not cName or not uName:
            return kDict

        # Grab creds only if client-cert and client-key exists.        
        users = kconf['users']
        for user in users:
            if user['name'] == uName:
                ccert = user['user'].get('client-certificate', None)
                ck = user['user'].get('client-key', None)
                if not ccert or not ck:
                    return kDict
                break
        
        clusters = kconf['clusters']
        for cluster in clusters:
            if cluster['name'] == cName:
                ca = cluster['cluster']['certificate-authority']
        
        #Add the entries to stash
        with open(ca, 'r') as stream:
            caStr = stream.read()

        with open(ccert, 'r') as stream:
            ccertStr = stream.read()

        with open(ck, 'r') as stream:
            ckStr = stream.read()
        
        # Add to kDict and push it to stash
        kDict['cluster-name'] = cName
        kDict['user-name'] = uName
        kDict['ca'] = caStr
        kDict['client-cert'] = ccertStr
        kDict['client-key'] = ckStr

        return kDict

    def aws_creds_add(self, awsf, kd):
        try:
            with open(awsf, 'r') as af:
                lines = af.readlines()
                for line in lines:
                    if 'aws_access_key_id' in line:
                        # write stash entry
                        awsAccessKey = line.split("=")[1].strip()
                        kd['aws-access-key'] = awsAccessKey
                    if 'aws_secret_access_key' in line:
                        awsSecret = line.split("=")[1].strip()
                        kd['aws-secret-key'] = awsSecret
            return kd
        except Exception as e:
            print("Error accessing aws credentials: %r" % e)
            print("Try specifying aws credentials file path using --aws-credentials option")
            return kd

    def get_cluster_user(self, kconf):
        cc = kconf.get('current-context', None)

        if not cc:
            return None, None
        
        ctxs = kconf['contexts']
        
        for ctx in ctxs:
            if ctx['name'] == cc:
                cName = ctx['context']['cluster']
                uName = ctx['context']['user']
                return cName, uName
        return None, None

    def check_eks(self, kconf):
        cName, uName = self.get_cluster_user(kconf)
        if not cName or not uName:
            return False
        
        users = kconf['users']
        for user in users:
            if user['name'] == uName:
                if 'exec' in user['user']:
                    exec = user['user']['exec']
                    if exec['command'] == 'aws':
                        return True
        return False

    def stash(self):
        d = self.env

        stashKeyName =  self.args.KName
        # Read K8s config
        if self.args.Kcfg:
            kcfgfile = self.args.Kcfg
        else:
            kcfgfile = DEFAULT_KUBE_CONFIG

        cfgfile = os.path.expanduser(kcfgfile)
        print("loading config: %s"%(cfgfile))
    
        #First parse yaml
        try:
            with open(cfgfile, 'r') as kf:
                try:
                    kCfg = yaml.safe_load(kf)
                except yaml.YAMLError as exc:
                    print(exc)
        except Exception as e:
            print("Error accessing kube config %r" % e)

        #Add creds to stash
        kd = self.kube_creds_add(kCfg)

        #Check if EKS cluster, if so add AWS creds
        if (self.check_eks(kCfg)):
            if self.args.AwsCreds:
                awsCredsFile = self.args.AwsCreds
            else:
                awsCredsFile = DEFAULT_AWS_CREDS
            
            awsFile = os.path.expanduser(awsCredsFile)
            kd = self.aws_creds_add(awsFile, kd)
            
        #finally add to stash
        kd = json.dumps(kd)
        self.add_stash(stashKeyName, kd, d['username'], 'PRIVATE')

    def findDummyInv(self):
        d = self.env

        try:
            obj = cf.get_model_objects(d['endpoint'], d['id_token'], "Investigation", {
                                       'title': {'eq': 'dummy'}, 'from': {'eq': self.args.username}},
                                       use_local_instance=self.local_install)
            for val in obj:
                if (val['title'] == 'dummy'):
                    INV = val['id']
                    return INV
            return None
        except Exception as e:
            self.logger.log(cf.Logger.ERROR, "findDummyInv: %r" % (e))

    def results(self):
        d = self.env
        # try:
        filter = None
        if (self.args.PBName):
            filter = {'title': {'eq': self.args.PBName}}

        obj = cf.get_model_objects(d['endpoint'], d['id_token'], "ExecutedRunbooks", 
                                    filter,
                                    use_local_instance=self.local_install)
        for pb in obj:
            print(pb['state'], ":", pb['updatedAt'])
            state = pb['state']
            if (state != "new" and state != "processing"):
                op = pb['output']
                if (pb['outputType'] == "gzip/b64encoded"):
                    op = zlib.decompress(base64.b64decode(op))
                self.printOutput(op)

    def connectors(self):
        d = self.env
        # try:
        filter = None
        if (self.args.CName):
            filter = {'name': {'eq': self.args.CName}}

        obj = cf.get_model_objects(d['endpoint'], d['id_token'], "Connectors", 
                                    filter,
                                    use_local_instance=self.local_install)
        for val in obj:
            if (val['commandsType'] == 'gzip/b64encoded'):
                tb = cf.b64decode(val['commands'])
                val['commands'] = json.loads(cf.gunzip_bytes(tb))
            else:
                val['commands'] = json.loads(val['commands'])
            if (self.args.CName):
                print(yaml.safe_dump(val))
            else:
                print("%s: " % val['name'])
                for c in val['commands']: 
                    print ("  %s: %s" % (c['name'], c['description']))
    

    def findRunPlaybook(self):
        d = self.env
        try:
            obj = cf.get_model_objects(d['endpoint'], d['id_token'], "AllRunbooks", {
                                       'name': {'eq': self.args.PBName}},
                                       use_local_instance=self.local_install)
            for val in obj:
                if (val['name'] == self.args.PBName):
                    return self.runPB(val, d)
            self.logger.log(cf.Logger.ERROR, "PB NOT FOUND %s" %
                            self.args.PBName)

        except Exception as e:
            self.logger.log(cf.Logger.ERROR, "findRunPlaybook: %r" % (e))

    def printOutput(self, out):
        if (self.args.json):
            print(out)
            return
        oo = json.loads(out)
        for o in oo:
            for k, v in o.items():
                print(k, v)

    def runPB(self, val, d):
        rb = self.ExecutedRunbooksCreate(self.dummy, val['id'], val['name'], d)
        #rb = {'id': "cdadbc86-bb6c-45aa-a328-8064e47944fb"}
        count = 0
        if (self.args.json == False):
            self.logger.log(cf.Logger.DEBUG, "Running Playbook %s ID %s for INV %s" % (
                val['name'], rb['id'], self.dummy))
        while(True):
            pb = self.findPB(rb['id'], d)
            if (pb == None):
                return None
            if (self.args.json == False):
                print(pb['state'])
            state = pb['state']
            if (state != "new" and state != "processing"):
                op = pb['output']
                if (pb['outputType'] == "gzip/b64encoded"):
                    op = zlib.decompress(base64.b64decode(op))
                self.printOutput(op)
                return state
            count += 1
            if (count > 20):
                print("Timeout")
                return None
            time.sleep(5)

    def ExecutedRunbooksCreate(self, investId, runbookId, title, d):
        author = d['username']
        rbVars = None
        if (self.args.PBVars):
            rbVars = self.args.PBVars
        cmd = {
            'investigationId': investId, 'author': author,
            'runbookID': runbookId,
            'title': title, 'state': "new",
            'rbVars': rbVars
        }
        try:
            link = cf.insert_obj(
                d['endpoint'], d['id_token'], "ExecutedRunbooks", cmd,
                use_local_instance=self.local_install)
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
                                                 [], {}, {}, self.logger,
                                                 use_local_instance=self.local_install)
            if (old):
                return old
        except Exception as e:
            self.logger.log(cf.Logger.ERROR, "Cannot Find: %r" % (e))
            return None
