import sys
sys.path.insert(0, "../epi-scripts/chatqlv2/cognito")
sys.path.insert(0, "../epi-scripts/chatqlv2/cognito/appsync-subscription-manager")

import CommonFunctions as cf
import Subscriptions as S
import glob
import yaml 
import os
import json
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

class Run():
    def __init__(self, args=None):
        self.logger = cf.Logger(log_to_file=True if args.log_file else False,
                              log_file=args.log_file)
        self.logger.set_log_level(cf.Logger.DEBUG)
        self.logger.log(cf.Logger.DEBUG, "initialized with %s" % args)
        self.args = args 

    def findAllConnectors(self, d):
        try:
            obj = cf.execute_function_with_retry(cf.get_model_objects,
                (d['endpoint'], d['id_token'], "Connectors", None),
                {}, d['current_env'], cf.ARTIBOT_USERNAME, 1, 0,
                USER_LIST, USER_DICT, USERNAME_DICT, self.logger)
            for val in obj:
                if (val['name']==self.connector['name']):
                    print("DELETE CONNECTOR:", val)
                    cf.remove_obj(d['endpoint'], d['id_token'],"Connectors", val)
            cf.create_connector(d['endpoint'], d['id_token'], self.connector)
        except Exception as e:
            self.logger.log(cf.Logger.ERROR, "findAllConnectors: %r" % (e))

        #this should be read from requests 
    def Execute(self):
        self.logger.log(cf.Logger.DEBUG, "running command with %s" % self.args)

        ## load the connector from the path
        self.loadConnector()
        
        CURRENT_ENV = self.args.login
        cf.gql_main_loop(CURRENT_ENV, self.logger, USERS, BLACKLISTED_TOKENS,
        USER_LIST, USER_DICT, USERNAME_DICT, SLEEP_TIME,
        [
         (S.SUBSCRIPTIONS['onupdateallworkflows'], updateWorkflow),
        ], APPSYNC_SUB_MGRS_MAP,
        on_error, on_sub_error, on_connection_error, on_close, self.on_subscription_success)

    def loadConnector(self):
        dir_name = self.args.directory
        print ("Reading from: ", dir_name)
        files = get_integration_files(dir_name)
        for tmp_file in files:
            f = parse_file(tmp_file, dir_name)
            self.logger.log(cf.Logger.INFO, "read connector %s " %  f)
            self.connector = f 
    def on_subscription_success(self, cb_data, sub):
        self.logger.log(cf.Logger.INFO, "Got subscription success...")
        self.findAllConnectors(cb_data)


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
def parse_file(file_name, dir_name):
    print("Reading ", file_name, dir_name)
    with open(file_name, 'r') as stream:
        try:
            print "Parsing: %s" % (file_name)
            f = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print str(exc)
        
    c = get_connector_dict(f, file_name, dir_name)
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

def get_script_file_name(file_name, file_type, write):
    tmp_f = file_name

    if os.path.basename(file_name).startswith("integration-"):
        tmp_f = file_name.replace("integration-", "")

    extension = get_script_type_extension(file_type)

    if not extension:
        print "ERROR: Could not find extension for file NAME: %s TYPE: %s" % (file_name, file_type)
        return None

    tmp_f = tmp_f[:-4] + extension

    if write:
        tmp_f = tmp_f.replace("-", "")

    return tmp_f

# Create a dictionary formatted for the storing in DynamoDB for the parsed file
def get_connector_dict(parsed_file_dict, file_name, dir_name):
    tmp_dict = {}

    try:
        tmp_dict['name'] = parsed_file_dict['name']
        tmp_dict['category'] = parsed_file_dict['category']
        tmp_dict['description'] = parsed_file_dict['description']
        tmp_dict['source'] = INTEGRATION_SOURCE
        tmp_dict['md5'] = cf.get_file_md5sum(file_name)
    except Exception as e:
        print "ERROR: Missing required param: %s" % (str(e))
        return None


    tmp_dict['iconPath'] = "/assets/images/logos/epi.png"
    if 'script' in parsed_file_dict:
        if 'type' in parsed_file_dict['script']:
            tmp_dict['scriptType'] = parsed_file_dict['script']['type']

        if 'script' in parsed_file_dict['script']:
            tmp_dict['script'] = parsed_file_dict['script']['script']
            tmp_var = tmp_dict['script'].strip()

            if ((tmp_var == "") or
                (tmp_var == "-")):
                # Script is empty. Try to find and load the script
                script_file_name = get_script_file_name(file_name, tmp_dict['scriptType'], False)

                if script_file_name:
                    tmp_dict['script'] = cf.read_file(script_file_name, False)
                else:
                    print "ERROR: Could not parse script file name for: %s" % (file_name)
                    sys.exit(-1)

            tmp_dict['scriptPath'] = "something else.py"

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

def updateWorkflow(message, cb_data):
    cf.update_cb_data(cb_data, self.logger)
    val = message['data']['onUpdateAllWorkflows']
    print(val)
def on_error(error, cb_data):
    print("GOT ERROR: %r" % (error))

def on_sub_error(error, cb_data):
    print("GOT SUBSCRIPTION ERROR: %r" % (error))

def cleanup_sub_mgr(cb_data):
    if cb_data['endpoint'] not in BLACKLISTED_TOKENS:
        BLACKLISTED_TOKENS[cb_data['endpoint']] = {}

    BLACKLISTED_TOKENS[cb_data['endpoint']][cb_data['username']] = cb_data['id_token']
    MY_LOGGER.log(cf.Logger.INFO, "Blacklisted token: EP: %s U: %s" % (cb_data['endpoint'], cb_data['username']))
    tmp_cb_data = APPSYNC_SUB_MGRS_MAP.pop(cb_data['endpoint'], None)
    tmp_cb_data['manager'].close()

def on_connection_error(error, cb_data):
    print("GOT CONNECTION ERROR: %r" % (error))
    cleanup_sub_mgr(cb_data)

def on_close(cb_data):
    print("AutoTasks: GOT SOCKET CLOSE")
    #cleanup_sub_mgr(cb_data)

