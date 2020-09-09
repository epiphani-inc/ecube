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
import ecube.gql as cf
import ecube.gql_operations.Subscriptions as S
import ecube.gql_operations.Localops as L
from future.utils import iteritems
import glob
import yaml 
import os
import signal
import json
from ecube import ecube_hooks as eh
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import traceback
from jinja2 import Environment, FileSystemLoader
import subprocess
import inspect
import copy 
import six

# Set your users information in the list below
USERS = [
]

# Leave this as an empty list, it is used to automatically
# populate all the usernames from the list above.
USER_LIST = []
USERNAME_DICT = {}
BLACKLISTED_TOKENS = {}
# Leave this as an empty dict, it is used to automatically
# populate all the userid to user objects.
USER_DICT = {}
SLEEP_TIME = 5
# AppSync Endpoint - Subscription Managers Map
APPSYNC_SUB_MGRS_MAP = {}

USE_THREADS = True

# Global know if sandbox connectors should be updated
# or deleted and inserted. Now, default is to update
# if the connectors exist.
UPDATE_CONNECTORS = True

PUBLISH_ONLY = False

# Cutoff size to gzip commands
CUTOFF_SIZE = 10 * 1024
def runCLICMD(cmd, logger):
    logger.log(cf.Logger.DEBUG, "Got command execution request: %r" % (cmd))
    print("Got command execution request: %r" % (cmd))
    out = subprocess.Popen(cmd, shell=True,
               stdout=subprocess.PIPE, 
               stderr=subprocess.STDOUT)
    stdout,stderr = out.communicate()
    logger.log(cf.Logger.DEBUG, "STDOUT: %r" % (stdout))

    if stderr:
        logger.log(cf.Logger.ERROR, "STDERR: %r" % (stderr))

    return str.lstrip(stdout if six.PY2 else stdout.decode('utf-8'))

def exec_full(filepath, logger):
    ret_val = True
    import os
    global_namespace = {
      "__file__": filepath,
      "__name__": "__main__",
    }

    with open(filepath, 'rb') as file:
        try:
            exec(compile(file.read(), filepath, 'exec'), global_namespace)
        except SystemExit as e:
            logger(cf.Logger.ERROR, "caught exit: code: %r" % (e))
            if str(e) == '-1':
                # TODO: ret_val should be set to False, but if we do that
                # then the meta playbook does not get 'task<ID>_result'
                # for e.g. YaqlEvaluationException: Unable to resolve key ''task2_result'' in expression ''<% ctx().task2_result %>'' from context.
                # So for now, we set it to True will we fix the meta playbook
                ret_val = True
    return ret_val

class Run():
    def __init__(self, args=None):
        global PUBLISH_ONLY
        try:
            tmp_lf = args.log_file
        except:
            tmp_lf = None
        self.logger = cf.Logger(log_to_file=True if tmp_lf else False,
                                log_file=tmp_lf)
        self.logger.set_log_level(cf.Logger.INFO)
        self.args = args 
        self.connector = {}
        self.local_install = False

        if 'local_install' in self.args and self.args.local_install:
            self.local_install = True
        
        if 'local_install_host' in self.args and self.args.local_install_host:
            self.local_install = True
            cf.set_local_gql_host(self.args.local_install_host)
        
        if 'local_install_port' in self.args and self.args.local_install_port:
            self.local_install = True
            cf.set_local_gql_port(self.args.local_install_port)

        if self.local_install:
            self.env = cf.init_local_env(args.username)

        try:
            if self.args.publish_playbooks:
                PUBLISH_ONLY = True
        except:
            pass

        if USE_THREADS:
            self.worker_pool = cf.WorkerPool()
        else:
            self.worker_pool = None

    def findAllConnectors(self, d):
        try:
            obj = cf.execute_function_with_retry(cf.get_model_objects,
                (d['endpoint'], d['id_token'], "Connectors", None),
                {}, d['current_env'], d['username'], 1, 0,
                USER_LIST, USER_DICT, USERNAME_DICT, self.logger,
                use_local_instance=self.local_install)
            for val in obj:
                if ((val['name'] in self.connector) and
                    (val['category'] == self.connector[val['name']]['category']) and
                    (val['source'] == self.connector[val['name']]['source'])):
                    if not UPDATE_CONNECTORS:
                        cf.remove_obj(d['endpoint'], d['id_token'],"Connectors", val,
                            use_local_instance=self.local_install)
                    else:
                        self.connector[val['name']]['id'] = val['id']
                        cf.update_obj(d['endpoint'], d['id_token'], "Connectors", self.connector[val['name']],
                            use_local_instance=self.local_install)
            for k, v in iteritems(self.connector):
                if not 'id' in v:
                    new_conn = cf.insert_obj(d['endpoint'], d['id_token'], 'Connectors', v,
                        use_local_instance=self.local_install)
                    v['id'] = new_conn['id']
        except Exception as e:
            tb_output = StringIO()
            traceback.print_exc(file=tb_output)
            o = tb_output.getvalue()
            self.logger.log(cf.Logger.ERROR, o)
            self.logger.log(cf.Logger.ERROR, "findAllConnectors: %r" % (e))

        if PUBLISH_ONLY:
            print("Done Publishing playbooks, exiting...")
            os.kill(os.getpid(), signal.SIGKILL)

        #this should be read from requests 
    def Execute(self):
        ## load the connector from the path
        self.loadConnector()
        
        if self.local_install:
            # Only subscribe to created events.
            tmp_f = {
                'where': {
                    'mutation_in': ['CREATED']
                }
            }
            query_list = [(L.LOCALOPS['onecubesandboxexecution'], self.handle_new_sandbox_execution, tmp_f)]
        else:
            query_list = [(S.SUBSCRIPTIONS['oncreateecubesandboxexecution'], self.handle_new_sandbox_execution)]

        CURRENT_ENV = self.args.login
        USERS.append({'username': self.args.username, 'passwd': self.args.password})
        cf.gql_main_loop(CURRENT_ENV, self.logger, USERS, BLACKLISTED_TOKENS,
        USER_LIST, USER_DICT, USERNAME_DICT, SLEEP_TIME,
        query_list, APPSYNC_SUB_MGRS_MAP,
        self.on_error, self.on_sub_error, self.on_connection_error, self.on_close, self.on_subscription_success,
        use_local_instance=self.local_install)

        #this should be read from requests 
    def loadTemplate(self, args):
        template_dir = "%s/files" % (os.path.dirname(inspect.getfile(cf)))
        file_loader = FileSystemLoader(template_dir)
        env = Environment(loader=file_loader)
        template = env.get_template('template.yml')
        cmd = os.path.basename(self.args.name)
        output = template.render(cliName=cmd)
        try:
            f = yaml.safe_load(output)
        except yaml.YAMLError:
            tb_output = StringIO()
            traceback.print_exc(file=tb_output)
            tmp_output = tb_output.getvalue()
            self.logger.log(cf.Logger.ERROR, tmp_output)
        c = get_connector_dict(f, template_dir + "/template.yml", "", self.logger)
        self.connector[c['name']] = c

        return c 

    def isthisforme(self, val):
        for key in self.connector.keys():
            if self.connector[key]["id"] == val["E3Two"]:                
                return True
        return False 

    def handle_cli(self, message, cb_data):
        upd_status = "DONE"
        try:
            if self.local_install:
                if message['data']['ecubeSandboxExecution']['mutation'] != 'CREATED':
                    self.logger.log(cf.Logger.DEBUG, "Ignoring non-creation subscription message")
                    return
                val = message['data']['ecubeSandboxExecution']['node']
            else:
                val = message['data']['onCreateEcubeSandboxExecution']

            if (not self.isthisforme(val)):
                return 
            data = json.loads(val['E3One'])
            data2 = data['args']['command']
            self.logger.log(cf.Logger.DEBUG, "Got a new execution msg: %r" % (val))
            o = runCLICMD(data2, self.logger)

        except Exception:
            tb_output = StringIO()
            traceback.print_exc(file=tb_output)
            o = tb_output.getvalue()
            self.logger.log(cf.Logger.ERROR, o)
            upd_status = "ERROR"

        try:

            update_dict = {
                'id': val['id'],
                'output': o,
                'status': upd_status
            }
            _ = cf.execute_function_with_retry(cf.update_obj,
                (cb_data['endpoint'], cb_data['id_token'], "EcubeSandboxExecution", update_dict),
                {}, cb_data['current_env'], cb_data['username'], 1, 0,
                USER_LIST, USER_DICT, USERNAME_DICT, self.logger,
                use_local_instance=self.local_install)
        except Exception:
            tb_output = StringIO()
            traceback.print_exc(file=tb_output)
            tmp_output = tb_output.getvalue()
            self.logger.log(cf.Logger.ERROR, tmp_output)


    def ExecuteCLI(self):
        self.logger.log(cf.Logger.DEBUG, "running command with %s" % self.args)
        ## load the connector from the path
        self.loadTemplate(self.args)
        CURRENT_ENV = self.args.login
        USERS.append({'username': self.args.username, 'passwd': self.args.password})
        self.logger.log(cf.Logger.DEBUG, "Waiting for commands...")
        print("Waiting for commands...")

        if self.local_install:
            # Only subscribe to created events.
            tmp_f = {
                'where': {
                    'mutation_in': ['CREATED']
                }
            }
            query_list = [(L.LOCALOPS['onecubesandboxexecution'], self.handle_cli, tmp_f)]
        else:
            query_list = [(S.SUBSCRIPTIONS['oncreateecubesandboxexecution'], self.handle_cli)]

        cf.gql_main_loop(CURRENT_ENV, self.logger, USERS, BLACKLISTED_TOKENS,
        USER_LIST, USER_DICT, USERNAME_DICT, SLEEP_TIME,
        query_list, APPSYNC_SUB_MGRS_MAP,
        self.on_error, self.on_sub_error, self.on_connection_error, self.on_close, self.on_subscription_success,
        use_local_instance=self.local_install)


    def loadConnector(self):
        dir_name = self.args.directory
        self.logger.log(cf.Logger.DEBUG, "Reading from: " + dir_name)
        files = get_integration_files(dir_name)
        for tmp_file in files:
            f = parse_file(tmp_file, dir_name, self.logger)
            self.logger.log(cf.Logger.INFO, "read connector %s " %  f)
            self.connector[f['name']] = f
    def on_subscription_success(self, cb_data, sub):
        self.findAllConnectors(cb_data)

    def on_error(self, error, cb_data):
        self.logger.log(cf.Logger.ERROR, "GOT ERROR: %r" % (error))

    def on_sub_error(self, error, cb_data):
        self.logger.log(cf.Logger.ERROR, "GOT SUBSCRIPTION ERROR: %r" % (error))

    def cleanup_sub_mgr(self, cb_data):
        if cb_data['endpoint'] not in BLACKLISTED_TOKENS:
            BLACKLISTED_TOKENS[cb_data['endpoint']] = {}

        BLACKLISTED_TOKENS[cb_data['endpoint']][cb_data['username']] = cb_data['id_token']
        self.logger.log(cf.Logger.INFO, "Blacklisted token: EP: %s U: %s" % (cb_data['endpoint'], cb_data['username']))
        tmp_cb_data = APPSYNC_SUB_MGRS_MAP.pop(cb_data['endpoint'], None)
        tmp_cb_data['manager'].close()

    def on_connection_error(self, error, cb_data):
        self.logger.log(cf.Logger.ERROR, "GOT CONNECTION ERROR: %r" % (error))
        self.cleanup_sub_mgr(cb_data)

    def on_close(self, cb_data):
        self.logger.log(cf.Logger.ERROR, "Run: GOT SOCKET CLOSE")
        #cleanup_sub_mgr(cb_data)

    def handle_new_sandbox_execution(self, message, cb_data):
        if self.worker_pool:
            self.worker_pool.apply_async(self.handle_single_execution,
                (message, cb_data))
        else:
            self.handle_single_execution(message, cb_data)

    def handle_single_execution(self, message, cb_data):
        upd_status = "DONE"
        try:
            if self.local_install:
                if message['data']['ecubeSandboxExecution']['mutation'] != 'CREATED':
                    self.logger.log(cf.Logger.DEBUG, "Ignoring non-creation subscription message")
                    return
                val = message['data']['ecubeSandboxExecution']['node']
            else:
                val = message['data']['onCreateEcubeSandboxExecution']
            if (not self.isthisforme(val)):
                return 
            self.logger.log(cf.Logger.DEBUG, "Got a new execution msg: %r" % (val))
            data = json.loads(val['E3One'])
            eh.setExecData(data)
            os.environ['ECUBE_HOOKS_PATH'] = os.getcwd() + "/cli"
            exec_full(data['args']['script_path'], self.logger)
            o, rc = eh.getExecOutput()

            if rc != 0:
                upd_status = "ERROR"
        except Exception:
            tb_output = StringIO()
            traceback.print_exc(file=tb_output)
            o = tb_output.getvalue()
            self.logger.log(cf.Logger.ERROR, o)
            upd_status = "ERROR"

        try:
            update_dict = {
                'id': val['id'],
                'output': json.dumps(o, separators=(',', ':')), 
                'status': upd_status
            }

            _ = cf.execute_function_with_retry(cf.update_obj,
                (cb_data['endpoint'], cb_data['id_token'], "EcubeSandboxExecution", update_dict),
                {}, cb_data['current_env'], cb_data['username'], 1, 0,
                USER_LIST, USER_DICT, USERNAME_DICT, self.logger,
                use_local_instance=self.local_install)
        except Exception:
            tb_output = StringIO()
            traceback.print_exc(file=tb_output)
            tmp_output = tb_output.getvalue()
            self.logger.log(cf.Logger.ERROR, tmp_output)

        if self.worker_pool:
            eh.removeThreadData()

def get_files(file_pattern):
    return glob.glob(file_pattern)
# Given a directory, return a list of YML files
# that do not have a corresponding MD file, b/c
# the files that have a MD file are Unreleased
# and are work in progress.
def get_integration_files(dir_name):
    f = get_files(dir_name + "/*.yml")
    return f 
# Parse a given YAML file and store its dictionary in the
# PARSED_CONNECTORS_DICT object
def parse_file(file_name, dir_name, logger):
    logger.log(cf.Logger.log, "Reading FILE: %s DIR: %s" % (file_name, dir_name))
    with open(file_name, 'r') as stream:
        try:
            logger.log(cf.Logger.DEBUG, "Parsing: %s" % (file_name))
            f = yaml.safe_load(stream)
        except yaml.YAMLError:
            tb_output = StringIO()
            traceback.print_exc(file=tb_output)
            tmp_output = tb_output.getvalue()
            logger.log(cf.Logger.ERROR, tmp_output)
        
    c = get_connector_dict(f, file_name, dir_name, logger)
    return c 

INTEGRATION_SOURCE="developer"
INTEGRATION_EPIPHANI_SOURCE="epiphani-multicloud"
INTEGRATION_DIR=""

def get_script_type_extension(file_type):
    if file_type == "python":
        return ".py"
    elif file_type == "javascript":
        return ".js"
    else:
        return None

def get_script_file_name(file_name, file_type, write, logger):
    tmp_f = file_name

    if os.path.basename(file_name).startswith("integration-"):
        tmp_f = file_name.replace("integration-", "")

    extension = get_script_type_extension(file_type)

    if not extension:
        logger.log(cf.Logger.ERROR, "Could not find extension for file NAME: %s TYPE: %s" % (file_name, file_type))
        return None

    tmp_f = tmp_f[:-4] + extension

    if write:
        tmp_f = tmp_f.replace("-", "")

    return tmp_f

# Create a dictionary formatted for the storing in DynamoDB for the parsed file
def get_connector_dict(parsed_file_dict, file_name, dir_name, logger):
    tmp_dict = {}

    try:
        tmp_dict['name'] = parsed_file_dict['name']
        tmp_dict['category'] = parsed_file_dict['category']
        tmp_dict['description'] = parsed_file_dict['description']

        if PUBLISH_ONLY:
            tmp_dict['source'] = INTEGRATION_EPIPHANI_SOURCE
        else:
            tmp_dict['source'] = INTEGRATION_SOURCE

        tmp_dict['md5'] = cf.get_file_md5sum(file_name)
    except Exception as e:
        logger.log(cf.Logger.ERROR, "Missing required param: %r" % (e))
        return None

    if not parsed_file_dict.get('iconPath'):
        tmp_dict['iconPath'] = "/assets/images/logos/epi_connector_icon.png"
    else:
        tmp_dict['iconPath'] = parsed_file_dict.get('iconPath')

    if 'script' in parsed_file_dict:
        if 'type' in parsed_file_dict['script']:
            tmp_dict['scriptType'] = parsed_file_dict['script']['type']

        if 'script' in parsed_file_dict['script']:
            tmp_dict['script'] = parsed_file_dict['script']['script']

            # Script is empty. Try to find and load the script
            script_file_name = get_script_file_name(file_name, tmp_dict['scriptType'], False, logger)

            if not script_file_name:
                logger.log(cf.Logger.ERROR, "Could not parse script file name for: %s" % (file_name))
                sys.exit(-1)

            tmp_dict['scriptPath'] = script_file_name

            # Don't need to put script in DynamoDB
            tmp_dict.pop('script', None)

        if 'commands' in parsed_file_dict['script']:
            tmp_dict['commands'] = json.dumps(parsed_file_dict['script']['commands'], separators=(',', ':'))

            if len(tmp_dict['commands']) > CUTOFF_SIZE:
                tmp_bytes = cf.gzip_string(tmp_dict['commands'])
                tmp_dict['commands'] = cf.b64encode(tmp_bytes)
                tmp_dict['commandsType'] = 'gzip/b64encoded'
            else:
                tmp_dict['commandsType'] = 'plain/text'

    if (('detaileddescription' in parsed_file_dict) and
        (parsed_file_dict['detaileddescription'])):
        tmp_dict['detaileddescription'] = parsed_file_dict['detaileddescription']

    if 'configuration' in parsed_file_dict:
        tmp_dict['configuration'] = json.dumps(parsed_file_dict['configuration'], separators=(',', ':'))

    return tmp_dict

