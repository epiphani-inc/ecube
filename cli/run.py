import sys
sys.path.insert(0, "../epi-scripts/chatqlv2/cognito")
sys.path.insert(0, "../epi-scripts/chatqlv2/cognito/appsync-subscription-manager")

import CommonFunctions as cf
import Subscriptions as S
from future.utils import iteritems
import glob
import yaml 
import os
import json
from cli import ecube_hooks as eh
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import traceback
# Set your users information in the list below
USERS = [
]

# Leave this as an empty list, it is user to automatically
# populate all the usernames from the list above.
USER_LIST = []
USERNAME_DICT = {}
BLACKLISTED_TOKENS = {}
# Leave this as an empty dict, it is user to automatically
# populate all the userid to user objects.
USER_DICT = {}
SLEEP_TIME = 5
# AppSync Endpoint - Subscription Managers Map
APPSYNC_SUB_MGRS_MAP = {}

# Cutoff size to gzip commands
CUTOFF_SIZE = 10 * 1024

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
        self.logger = cf.Logger(log_to_file=True if args.log_file else False,
                              log_file=args.log_file)
        self.logger.set_log_level(cf.Logger.DEBUG)
        self.logger.log(cf.Logger.DEBUG, "initialized with %s" % args)
        self.args = args 
        self.connector = {}

    def findAllConnectors(self, d):
        print ("CONNECTOR", d['id_token'], d['endpoint'], d['current_env'])
        try:
            obj = cf.execute_function_with_retry(cf.get_model_objects,
                (d['endpoint'], d['id_token'], "Connectors", None),
                {}, d['current_env'], cf.ARTIBOT_USERNAME, 1, 0,
                USER_LIST, USER_DICT, USERNAME_DICT, self.logger)
            for val in obj:
                if (val['name'] in self.connector) and (val['category'] == self.connector[val['name']]['category']):
                    print("DELETE CONNECTOR:", val)
                    cf.remove_obj(d['endpoint'], d['id_token'],"Connectors", val)
            for _, v in iteritems(self.connector):
                cf.create_connector(d['endpoint'], d['id_token'], v)
        except Exception as e:
            self.logger.log(cf.Logger.ERROR, "findAllConnectors: %r" % (e))

        #this should be read from requests 
    def Execute(self):
        self.logger.log(cf.Logger.DEBUG, "running command with %s" % self.args)

        ## load the connector from the path
        self.loadConnector()
        
        CURRENT_ENV = self.args.login
        USERS.append({'username': self.args.username, 'password': self.args.password})
        cf.gql_main_loop(CURRENT_ENV, self.logger, USERS, BLACKLISTED_TOKENS,
        USER_LIST, USER_DICT, USERNAME_DICT, SLEEP_TIME,
        [
         (S.SUBSCRIPTIONS['oncreateecubesandboxexecution'], self.handle_new_sandbox_execution),
        ], APPSYNC_SUB_MGRS_MAP,
        self.on_error, self.on_sub_error, self.on_connection_error, self.on_close, self.on_subscription_success)

    def loadConnector(self):
        dir_name = self.args.directory
        self.logger.log(cf.Logger.DEBUG, "Reading from: " + dir_name)
        files = get_integration_files(dir_name)
        for tmp_file in files:
            f = parse_file(tmp_file, dir_name, self.logger)
            self.logger.log(cf.Logger.INFO, "read connector %s " %  f)
            self.connector[f['name']] = f
    def on_subscription_success(self, cb_data, sub):
        self.logger.log(cf.Logger.INFO, "Got subscription success...")
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
        print("Run: GOT SOCKET CLOSE")
        #cleanup_sub_mgr(cb_data)

    def handle_new_sandbox_execution(self, message, cb_data):
        upd_status = "DONE"
        try:
            cf.update_cb_data(cb_data, self.logger)
            val = message['data']['onCreateEcubeSandboxExecution']
            self.logger.log(cf.Logger.DEBUG, "Got a new execution msg: %r" % (val))
            data = json.loads(val['E3One'])
            eh.setExecData(data)
            os.environ['ECUBE_HOOKS_PATH'] = os.getcwd() + "/cli"
            exec_full(data['args']['script_path'], self.logger)
            o = eh.getExecOutput()
        except Exception:
            tb_output = StringIO()
            traceback.print_exc(file=tb_output)
            tmp_output = tb_output.getvalue()
            self.logger.log(cf.Logger.ERROR, tmp_output)
            o = tb_output.getvalue()
            upd_status = "ERROR"

        try:
            update_dict = {
                'id': val['id'],
                'output': json.dumps(o, separators=(',', ':')), 
                'status': upd_status
            }

            _ = cf.execute_function_with_retry(cf.update_obj,
                (cb_data['endpoint'], cb_data['id_token'], "EcubeSandboxExecution", update_dict),
                {}, cb_data['current_env'], cf.ARTIBOT_USERNAME, 1, 0,
                USER_LIST, USER_DICT, USERNAME_DICT, self.logger)
        except Exception:
            tb_output = StringIO()
            traceback.print_exc(file=tb_output)
            tmp_output = tb_output.getvalue()
            self.logger.log(cf.Logger.ERROR, tmp_output)

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

