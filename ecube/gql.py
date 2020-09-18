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
import appsync_subscription_manager as asm
import warrant
import os
from datetime import datetime
import threading
import pprint
import ecube.environments as environments
import time
import requests
import hashlib
import json
import traceback
import signal
import ecube.gql_operations.Mutations as Mutations
import ecube.gql_operations.Queries as Queries
import ecube.gql_operations.Localops as Localops
import base64
import codecs
import six
import re
from future.utils import iteritems
import copy

ENVIRONMENTS = environments.ENVIRONMENTS
ARTIBOT_USERNAME = "artibot"

# Read GQL URL
LOCAL_GQL_HOST = os.environ.get('LOCAL_GQL_HOST', "localhost")
LOCAL_GQL_PORT = os.environ.get('LOCAL_GQL_PORT', "31050")
LOCAL_GQL_FRAG = "%s:%s" % (LOCAL_GQL_HOST, LOCAL_GQL_PORT)
GQL_PSK = os.environ.get("GQL_PSK", 'SAANPD00D')

LOG_DIR = "/var/log/epiphani/"

# AppMgr dictionary access lock
APPMGR_LOCK = threading.Lock()

# Subscriptions retry logic
APPSYNC_SUB_RETRY_MAP = {}
MAX_BACKOFF_TIME = 10

class WorkerPool():
    def apply_async(self, t_func, t_args):
        threading.Thread(target=t_func, args=t_args).start()

class GetObjError(Exception):
     def __init__(self, *args, **kwargs):
         default_message = 'This is a default message!'

         # if no arguments are passed set the first positional argument
         # to be the default message. To do that, we have to replace the
         # 'args' tuple with another one, that will only contain the message.
         # (we cannot do an assignment since tuples are immutable)
         if not (args or kwargs): args = (default_message,)

         # Call super constructor
         super(GetObjError, self).__init__(*args, **kwargs)

class ListObjectsError(Exception):
     def __init__(self, *args, **kwargs):
         default_message = 'This is a default message!'

         # if no arguments are passed set the first positional argument
         # to be the default message. To do that, we have to replace the
         # 'args' tuple with another one, that will only contain the message.
         # (we cannot do an assignment since tuples are immutable)
         if not (args or kwargs): args = (default_message,)

         # Call super constructor
         super(ListObjectsError, self).__init__(*args, **kwargs)

class DeleteObjectError(Exception):
     def __init__(self, *args, **kwargs):
         default_message = 'This is a default message!'

         # if no arguments are passed set the first positional argument
         # to be the default message. To do that, we have to replace the
         # 'args' tuple with another one, that will only contain the message.
         # (we cannot do an assignment since tuples are immutable)
         if not (args or kwargs): args = (default_message,)

         # Call super constructor
         super(DeleteObjectError, self).__init__(*args, **kwargs)

class InsertObjectError(Exception):
     def __init__(self, *args, **kwargs):
         default_message = 'This is a default message!'

         # if no arguments are passed set the first positional argument
         # to be the default message. To do that, we have to replace the
         # 'args' tuple with another one, that will only contain the message.
         # (we cannot do an assignment since tuples are immutable)
         if not (args or kwargs): args = (default_message,)

         # Call super constructor
         super(InsertObjectError, self).__init__(*args, **kwargs)

class UpdateObjectError(Exception):
     def __init__(self, *args, **kwargs):
         default_message = 'This is a default message!'

         # if no arguments are passed set the first positional argument
         # to be the default message. To do that, we have to replace the
         # 'args' tuple with another one, that will only contain the message.
         # (we cannot do an assignment since tuples are immutable)
         if not (args or kwargs): args = (default_message,)

         # Call super constructor
         super(UpdateObjectError, self).__init__(*args, **kwargs)

class Logger():
    DEBUG = 1
    INFO = 2
    ERROR = 3
    OFF = 4

    def __init__(self, log_to_file=True, log_file=None):
        self.my_pid = os.getpid()
        self.log_to_file = log_to_file
        self.log_file = log_file
        if log_file == None:
            log_file = LOG_DIR + "ExecRunbook.%d.log" % (self.my_pid)
        #print("Initializing logger for PID: %d" % (self.my_pid))

        if self.log_to_file:
            if log_file == None:
                os.mkdir(LOG_DIR)
            self.log_file = open(log_file, "w")
            self.log_level = Logger.OFF
            self.write = self.log_file.write
            self.flush = self.log_file.flush
            self.stream = self.log_file
        else:
            self.write = sys.stdout.write
            self.flush = sys.stdout.flush
            self.stream = sys.stdout

    def is_valid_log_level(self, log_level):
        l = False
        try:
            if not ((log_level < Logger.DEBUG) or (log_level > Logger.OFF)):
                l = True
        except:
            pass

        return l

    def set_log_level(self, log_level):
        if not self.is_valid_log_level(log_level):
            print("ERROR: Trying to set Invalid log level: %r" % (log_level))
            sys.exit(-1)
        self.log_level = log_level

    def get_log_level(self):
        return self.log_level

    def get_log_level_str(self, log_level):
        if log_level == Logger.OFF:
            return "OFF"
        elif log_level == Logger.DEBUG:
            return "DEBUG"
        elif log_level == Logger.INFO:
            return "INFO"
        elif log_level == Logger.ERROR:
            return "ERROR"
        else:
            return "INVALID_LOG_LEVEL(%s)" % (str(log_level))

    def log(self, log_level, log_str):
        if self.is_valid_log_level(log_level):
            if log_level >= self.log_level:
                self.write("%s: %d: %s: %r\n" % (datetime.now().strftime("%m/%d/%Y, %H:%M:%S"), self.my_pid, self.get_log_level_str(log_level), log_str))
        else:
            self.write("%s: %d: %s: %r\n" % (datetime.now().strftime("%m/%d/%Y, %H:%M:%S"), self.my_pid, self.get_log_level_str(log_level), log_str))
        self.flush()

    def pprint(self, log_level, log_obj):
        if self.is_valid_log_level(log_level):
            if log_level >= self.log_level:
                pprint.pprint(log_obj, stream=self.stream)
                self.write("\n")
        else:
            self.write("%d: %r\n" % (self.my_pid, self.get_log_level_str(log_level)))
            pprint.pprint(log_obj, stream=self.stream)
            self.write("\n")
        self.flush()

def set_gql_psk(gql_psk):
    global GQL_PSK
    GQL_PSK = gql_psk
    asm.set_gql_psk(gql_psk)

def set_local_gql_host(lgh):
    global LOCAL_GQL_HOST
    global LOCAL_GQL_FRAG
    LOCAL_GQL_HOST = lgh
    LOCAL_GQL_FRAG = "%s:%s" % (LOCAL_GQL_HOST, LOCAL_GQL_PORT)
    asm.set_local_gql_frag(LOCAL_GQL_FRAG)

def set_local_gql_port(lgp):
    global LOCAL_GQL_PORT
    global LOCAL_GQL_FRAG
    LOCAL_GQL_PORT = lgp
    LOCAL_GQL_FRAG = "%s:%s" % (LOCAL_GQL_HOST, LOCAL_GQL_PORT)
    asm.set_local_gql_frag(LOCAL_GQL_FRAG)

def init_local_env(username):
    return {
        'endpoint': "http://%s:%s/graphql" % (LOCAL_GQL_HOST, LOCAL_GQL_PORT),
        'id_token': None,
        'username': username,
        'current_env': None,
    }

# calculate and return the md5sum of the contents of a given file
def get_file_md5sum(file_name):
    with open(file_name, "rb") as f:
        file_hash = hashlib.md5()
        t = f.read(8192)
        while t:
            file_hash.update(t)
            t = f.read(8192)

    return file_hash.hexdigest()

def initEnv(current_env, logger):
    users = get_env_var(current_env, 'USERS')
    gql_endpoint = get_env_var(current_env, "GRAPHQL_API_ENDPOINT")
    user_list = []
    user_dict = {}
    username_dict = {}

    # Initialize the environment
    init_environment(current_env, users, user_list, user_dict, username_dict, logger)
    myauth = users[0]['auth']

    ret = {
        'id_token': myauth.id_token,
        'username': myauth.username,
        'current_env': current_env,
        'endpoint': gql_endpoint
    }
    return ret

def setup_env_and_subscribe(sub_list=None, appsync_sub_mgrs_map=None, logger=None,
    on_connection_error=None, on_error=None, on_sub_error=None,
    on_close=None, current_env=None, on_subscription_success=None,
    use_local_instance=False):
    tmp_dict = {}
    user_list = []
    user_dict = {}
    username_dict = {}

    # Setup vars for the environment
    if not use_local_instance:
        users = get_env_var(current_env, 'USERS')
        gql_endpoint = get_env_var(current_env, "GRAPHQL_API_ENDPOINT")

        # Initialize the environment
        init_environment(current_env, users, user_list, user_dict, username_dict, logger)

        for tmp_user in users:
            tmp_dict[tmp_user['username']] = tmp_user['auth'].id_token

        username = users[0]['username']
        id_token = users[0]['auth'].id_token
    else:
        users = []
        gql_endpoint = "http://" + LOCAL_GQL_FRAG + "/graphql"
        username = "admin"
        id_token="NOT_ID_TOKEN_NEEDED"
        asm.set_local_gql_frag(LOCAL_GQL_FRAG)
        asm.set_gql_psk(GQL_PSK)

    check_and_subscribe(endpoint=gql_endpoint, endpoint_user_dict=tmp_dict,
        username=username, id_token=id_token, use_local_instance=use_local_instance,
        sub_list=sub_list, appsync_sub_mgrs_map=appsync_sub_mgrs_map, logger=logger,
        on_connection_error=on_connection_error, on_error=on_error, on_sub_error=on_sub_error,
        on_close=on_close, current_env=current_env, on_subscription_success=on_subscription_success)

def cf_on_close(cb_data):
    # Remove the current subscription manager and create
    # a new one
    ep = cb_data['endpoint']
    logger = cb_data['kwargs']['logger']
    kwargs = cb_data['kwargs']
    logger.log(Logger.ERROR, "CF: Got Socket close for EP: %s" % (ep))

    logger.log(Logger.INFO, "CF: Calling APP Socket 'on-close'")
    kwargs['on_close'](cb_data)
    logger.log(Logger.INFO, "CF: Cleaning up EP: %s" % (ep))
    first_retry = False

    APPMGR_LOCK.acquire()

    kwargs['appsync_sub_mgrs_map'].pop(ep, None)
    retry_map = APPSYNC_SUB_RETRY_MAP.get(ep)

    if not retry_map:
        first_retry = True
        retry_map = {'prev_ts': datetime.now(), 'backoff_time': 1}
        APPSYNC_SUB_RETRY_MAP[ep] = retry_map

    APPMGR_LOCK.release()

    if not first_retry and retry_map['backoff_time'] < MAX_BACKOFF_TIME:
        time_diff = int((datetime.now() - retry_map['prev_ts']).total_seconds())
        if time_diff < retry_map['backoff_time']:
            retry_map['backoff_time'] *= 2
        elif time_diff > (MAX_BACKOFF_TIME * 10):
            # If the last disconnect was more than 10 max backoff ago,
            # then reset the backoff to default 1 second.
            retry_map['backoff_time'] = 1
        if retry_map['backoff_time'] > MAX_BACKOFF_TIME:
            retry_map['backoff_time'] = MAX_BACKOFF_TIME
    logger.log(Logger.INFO, "CF: Sleeping for %d seconds before retrying" % (retry_map['backoff_time']))
    time.sleep(retry_map['backoff_time'])
    retry_map['prev_ts'] = datetime.now()

    logger.log(Logger.INFO, "CF: Re-Subscribing EP: %s" % (ep))
    setup_env_and_subscribe(sub_list=kwargs['sub_list'],
        appsync_sub_mgrs_map=kwargs['appsync_sub_mgrs_map'], logger=kwargs['logger'],
        on_connection_error=kwargs['on_connection_error'],
        on_error=kwargs['on_error'], on_sub_error=kwargs['on_sub_error'],
        on_close=kwargs['on_close'], current_env=kwargs['current_env'],
        on_subscription_success=kwargs['on_subscription_success'],
        use_local_instance=kwargs['use_local_instance'])

'''
Since we store the args that are passed to check & subscribe, we
want to make sure that all the arguments are KW args so that they
can be stored & later passed back to this function on a socket
close for reconnection.
ALL THE ARGS SHOULD BE KWARGS.
'''
def check_and_subscribe(endpoint=None, endpoint_user_dict=None, username=None,
    id_token=None, sub_list=None, appsync_sub_mgrs_map=None, logger=None,
    on_connection_error=None, on_error=None, on_sub_error=None, on_close=None,
    current_env=None, on_subscription_success=None, use_local_instance=False):
    # MUST BE THE VERY FIRST LINE IN THIS FUNCTION!
    cur_args = locals()

    if endpoint in appsync_sub_mgrs_map:
        logger.log(Logger.DEBUG, "Sub Mgr already exists for endpoint: %s user: %s" % (endpoint, username))
        return False

    tmp_cb_data = {
        'current_env': current_env,
        'endpoint': endpoint,
        'username': username,
        'id_token': id_token,
        'endpoint_user_dict': endpoint_user_dict,
        'kwargs': cur_args,
        'use_local_instance': use_local_instance,
        'gql_psk': GQL_PSK
    }

    my_mgr = asm.AppSyncSubscriptionManager(id_token = id_token,
        appsync_api_id = endpoint.split('/')[2].split('.')[0],
        on_connection_error = on_connection_error,
        on_error = on_error,
        on_close = cf_on_close,
        use_local_instance = use_local_instance,
        cb_data = tmp_cb_data)

    sub_dict = {}

    for tmp_set in sub_list:
        sub_query = tmp_set[0]
        on_message = tmp_set[1]
        if len(tmp_set) == 3:
            sub_filter = tmp_set[2]
        else:
            sub_filter = {}

        my_sub = my_mgr.subscribe(sub_query, on_message, on_sub_error,
            on_subscription_success, sub_filter=sub_filter)
        sub_dict[my_sub.get_id()] = my_sub

    tmp_cb_data['subscriptions'] = sub_dict
    tmp_cb_data['manager'] = my_mgr

    appsync_sub_mgrs_map[endpoint] = tmp_cb_data

    x = threading.Thread(target=my_mgr.run_forever, args=())
    x.start()
    return True

def gql_main_loop(current_env, logger, users, blacklisted_tokens,
    user_list, user_dict, username_dict, sleep_time, sub_list,
    appsync_sub_mgrs_map, on_error,
    on_sub_error, on_connection_error, on_close,
    on_subscription_success, use_local_instance=False):
    global ENVIRONMENTS
    init_done = False
    env_list = []

    set_env_var(current_env, 'USERS', users)

    try:
      while True:
        if (use_local_instance or current_env) and not init_done:
            if use_local_instance or (current_env in ENVIRONMENTS):
                setup_env_and_subscribe(sub_list=sub_list, appsync_sub_mgrs_map=appsync_sub_mgrs_map, logger=logger,
                    on_connection_error=on_connection_error, on_error=on_error, on_sub_error=on_sub_error,
                    on_close=on_close, current_env=current_env, on_subscription_success=on_subscription_success,
                    use_local_instance=use_local_instance)
            else:
                logger.log(Logger.ERROR, "Could not find CURRENT_ENV: %s" % (current_env))
            init_done = True
        elif not current_env and not init_done:
            # Remove PROD to be processed in dev
            if 'PROD' in env_list:
                logger.log(Logger.INFO, "Removing PROD from env list...")
                env_list.remove('PROD')

            for env in env_list:
                if env in ENVIRONMENTS:
                    setup_env_and_subscribe(sub_list=sub_list, appsync_sub_mgrs_map=appsync_sub_mgrs_map, logger=logger,
                        on_connection_error=on_connection_error, on_error=on_error, on_sub_error=on_sub_error,
                        on_close=on_close, current_env=env, on_subscription_success=on_subscription_success)
                else:
                    logger.log(Logger.ERROR, "Could not find ENV: %s" % (env))

            init_done = True

        # logger.log(Logger.DEBUG, "Sleeping for %d secs..." % sleep_time)
        time.sleep(sleep_time)
    except KeyboardInterrupt as e:
        os.kill(os.getpid(), signal.SIGTERM)

def get_env_var(env, var):
    return ENVIRONMENTS[env][var]

def set_env_var(env, var, val):
    ENVIRONMENTS[env][var] = val

def init_environment(env, users, user_list, user_dict, username_dict, logger):
    # First clean the user_list (in case its a re-init)
    del user_list[:]

    # Authenticate all the users...
    for user in users:
        user_list.append(user['username'])
        # create a cognito user object
        u = warrant.Cognito(get_env_var(env, 'COGNITO_USER_POOL_ID'),
            get_env_var(env, 'COGNITO_USER_POOL_CLIENT_ID'),
            username=user['username'])

        try:
            # Try to authenticate the user
            u.authenticate(password=user['passwd'])
        except Exception as e:
            # Authentication failed...
            logger.log(Logger.ERROR, "%r" % (e))
            sys.exit(2)

        # Save the authenticated cognito user object
        user['auth'] = u

        # get the user ID by decoding the id_token
        decoded = u.verify_token(u.id_token, 'id_token', 'id')
        user['id'] = decoded['sub']
        user['decoded_id_token'] = decoded

        # Save the warrant cognito user object in the USER ID MAP
        user_dict[decoded['sub']] = u
        username_dict[user['username']] = u

    set_env_var(env, 'USERNAME_DICT', username_dict)
    set_env_var(env, 'USER_DICT', user_dict)

def check_user_token(current_env, endpoint, username, username_dict):
    env_endpoint = get_env_var(current_env, "GRAPHQL_API_ENDPOINT")

    if env_endpoint == endpoint:
        a = username_dict.get(username, None)

        if a:
            return a.id_token

    return None

'''
This function takes a function pointer and executes it.
If the execution results in a 'token expired' error, it
will try to re-authenticate the 'username' with its
password from the current_env & if successful, will use
that new token and retry the function call.

ARGUMENTS:

func: Function that should be called and retried
args: Arguments for 'func' or () if no arguments
kwargs: Keyword arguments for 'func' or {} if no keyword arguments
current_env: Current environment string
username: Username that should be used for retrying if 'func'
          fails due to 'token expired' error
id_token_index: Index of the ID token in 'args' or -1
endpoint_index: Index of the endpoint URL in 'args' above or -1

The next 3 arguments should be passed from
when the environment was originally initialized
user_list: list of users in this environment
user_dict: dictionary of users keyed of user id
username_dict: dictionary of users keyed of username

logger: Instance of 'Logger' class to be used for logs
'''
def execute_function_with_retry(func, args, kwargs, current_env,
    username, id_token_index, endpoint_index,
    user_list, user_dict, username_dict, logger,
    use_local_instance=False):
    retried_already = False

    if use_local_instance:
        kwargs.update({'use_local_instance': use_local_instance})
        current_env = None

    while True:
        try:
            # Try to get an updated token before calling the function
            # But not if this is a local instance
            if (not use_local_instance) and current_env and endpoint_index >= 0:
                new_token = check_user_token(current_env, args[endpoint_index], username, username_dict)

                if new_token:
                    args = args[:id_token_index] + (new_token,) + args[(id_token_index + 1):]

            return func(*args, **kwargs)
        except Exception as e:
            err_str = str(e)

            if use_local_instance:
                logger.log(Logger.ERROR, "Using local instance, cannot retry")
                raise

            if not current_env:
                logger.log(Logger.ERROR, "No ENV set, cannot retry")
                raise

            # Trying to handle more cases of unauthorized access. Most of the times
            # we get reason as "token is expired" but sometimes we also get "unauthorized".
            if "code: 401 reason: unauthorized" in err_str.lower():
                if not retried_already:
                    retried_already = True
                    logger.log(Logger.ERROR, "%s failed, %s, retrying" % (func.__name__, str(e)))
                    try:
                        init_environment(current_env, get_env_var(current_env, 'USERS'),
                            user_list, user_dict, username_dict, logger)
                    except Exception as e:
                        logger.log(Logger.ERROR, "Retry failed: env initialization failed")
                        raise

                    # rebuild args with new id_token
                    if username in username_dict:
                        logger.log(Logger.DEBUG, "Updated token for user: " + username)
                        args = args[:id_token_index] + (username_dict[username].id_token,) + args[(id_token_index + 1):]
                    else:
                        logger.log(Logger.ERROR, "Could not find USER: %s" % (username))
                        raise
                else:
                    logger.log(Logger.ERROR, "Already tried once, giving up")
                    raise
            else:
                logger.log(Logger.ERROR, "Unhandled error, cannot retry")
                raise

def plural(m):
    if (m[-1] == 's' or m[-1] == 'h'):
        return (m+"es")
    else:
        return (m+"s")

def make_lower(val):
    return val[0].lower()  + val[1:]

def capitalize(val):
    if not isinstance(val, six.string_types):
        return ''
    s = val[0].upper()
    t = ""
    i = 1
    while i < len(val):
        if re.match(r'[A-Z]', val[i]):
            t += val[i]
        elif (len(t) > 0):
            s = s + t[0:-1].lower() + t[len(t) - 1] + val[i:]
            return s
        else:
            s = s + val[i:]
            return s

def load_content(content):
    return json.loads(content if six.PY2 else content.decode('utf-8'))

def add_model_mapping(model_name, obj):
    mmap = Localops.MODEL_MAPPING.get(model_name, None)
    if mmap:
        for (k, v) in iteritems(mmap):
            obj[k] = {"connect": {"id": obj[v]}}
    return obj

def add_model_relation(model_name, obj):
    mr = Localops.MODEL_RELATION.get(model_name, None)
    if mr:
        for field in mr:
            obj[field] = {"set":obj[field]}
    return obj

def convert_filter(aws_filter):
    if not aws_filter:
        return aws_filter
    local_filter = {}
    for (key, value) in iteritems(aws_filter):
        if isinstance(value, six.string_types):
            local_filter[key] = value
            continue
        for (k, v) in iteritems(value):
            if k == 'eq':
                new_key = key
            elif k == 'ne':
                new_key = key + '_not'
            elif k == 'lt':
                new_key = key + '_lt'
            elif k == 'lte':
                new_key = key + '_lte'
            elif k == 'gt':
                new_key = key + '_gt'
            elif k == 'gte':
                new_key = key + '_gte'
            elif k == 'contains':
                new_key = key + '_contains'
            elif k == 'notContains':
                new_key = key + '_not_contains'
            elif k == 'between':
                new_key = key +'_not_starts_with'
            elif k == 'beginsWith':
                new_key = key +'_starts_with'
            else:
                new_key = key
            local_filter[new_key] = v
    return local_filter

# Get the Auth header for passing to a requests library call (GET, POST, etc.)
def get_auth_header(id_token, use_local_instance=False):
    if not use_local_instance:
        return {"Authorization": id_token}
    elif GQL_PSK:
        return {"X-Api-Key": GQL_PSK}
    else:
        raise ValueError("No Pre Shared Key set for local instance authentication")

# Remove an object of a given model
def remove_obj(endpoint, id_token, model_name, obj,
    custom_query=None, mutations_module=None,
    use_local_instance=False):
    # Get the header
    auth_header = get_auth_header(id_token, use_local_instance=use_local_instance)

    if use_local_instance:
        mutations_module = Localops
    elif not mutations_module:
        mutations_module = Mutations

    # Set the input for delete object query
    vars = {"input": {"id": obj['id']}}
    updated_model_name = model_name[0].upper() + model_name[1:]
    connector_name = "delete" + updated_model_name

    if use_local_instance:
        connector = mutations_module.LOCALOPS[connector_name.lower()]
    elif custom_query:
        connector = custom_query
    else:
        connector = mutations_module.MUTATIONS[connector_name.lower()]

    # Send the POST request.  All queries & mutations are sent
    # as a post request in aws-amplify/graphql, in JSON format.
    try:
        r = requests.post(endpoint, headers=auth_header,
            json={"query": connector, "variables": vars})
        res = load_content(r.content)
    except Exception as e:
        s = "Delete object request failed: " + str(e)
        raise DeleteObjectError(s)

    if r.status_code == 200:
        # Even if the return code was 200, we could still have errors.
        if 'errors' in res:
            s = "Failed to delete object: " + updated_model_name \
                + " ERROR: " + res['errors'][0]['message']
            raise DeleteObjectError(s)
    else:
        s = "ERROR: Failed to delete object: %s CODE: %d REASON: %s MSG: %s" % (updated_model_name, r.status_code, r.reason, res['errors'][0]['message'])
        raise DeleteObjectError(s)

# Insert an object of a given model
def insert_obj(endpoint, id_token, model_name, obj,
    custom_query=None, mutations_module=None,
    use_local_instance=False):
    # Get the header
    auth_header = get_auth_header(id_token, use_local_instance=use_local_instance)

    if use_local_instance:
        mutations_module = Localops
    elif not mutations_module:
        mutations_module = Mutations

    # Set the input for insert object query
    if use_local_instance:
        deleteList=['UsersCanView', 'UsersCanAccess', "GroupsCanView", 'GroupsCanAccess']
        for elem in deleteList:
            if elem in obj:
                del obj[elem]
        obj = add_model_mapping(model_name, obj)
        obj = add_model_relation(model_name, obj)
    vars = {"input": obj}
    updated_model_name = model_name[0].upper() + model_name[1:]
    connector_name = "create" + updated_model_name

    if use_local_instance:
        connector = mutations_module.LOCALOPS[connector_name.lower()]
    elif custom_query:
        connector = custom_query
    else:
        connector = mutations_module.MUTATIONS[connector_name.lower()]

    # Send the POST request.  All queries & mutations are sent
    # as a post request in aws-amplify/graphql, in JSON format.
    try:
        r = requests.post(endpoint, headers=auth_header,
            json={"query": connector, "variables": vars})
        res = load_content(r.content)
    except Exception as e:
        s = "Insert object request failed: " + str(e)
        raise InsertObjectError(s)

    if r.status_code == 200:
        # Even if the return code was 200, we could still have errors.
        if 'errors' in res:
            s = "Failed to insert object: " + updated_model_name \
                + " ERROR: " + res['errors'][0]['message']
            raise InsertObjectError(s)
        else:
            return res['data'][connector_name]
    else:
        s = "ERROR: Failed to insert object: %s CODE: %d REASON: %s MSG: %s" % (updated_model_name, r.status_code, r.reason, res['errors'][0]['message'])
        raise InsertObjectError(s)

# Update an object of a given model
def update_obj(endpoint, id_token, model_name, obj,
    custom_query=None, mutations_module=None,
    use_local_instance=False):
    vars = {}
    # Get the header
    auth_header = get_auth_header(id_token, use_local_instance=use_local_instance)

    updated_model_name = model_name[0].upper() + model_name[1:]
    connector_name = "update" + updated_model_name

    if use_local_instance:
        mutations_module = Localops
    elif not mutations_module:
        mutations_module = Mutations

    if use_local_instance:
        connector = mutations_module.LOCALOPS[connector_name.lower()]
    elif custom_query:
        connector = custom_query
    else:
        connector = mutations_module.MUTATIONS[connector_name.lower()]

    # Set the input for update object query
    if use_local_instance:
        obj = copy.deepcopy(obj)
        model_id = obj['id']
        deleteList=['UsersCanView', 'UsersCanAccess', "GroupsCanView", 'GroupsCanAccess', 'id']
        for elem in deleteList:
            if elem in obj:
                del obj[elem]
        # obj = add_model_mapping(model_name, obj)
        obj = add_model_relation(model_name, obj)
        vars['where'] = {'id': model_id}


    vars["input"] = obj

    # Send the POST request.  All queries & mutations are sent
    # as a post request in aws-amplify/graphql, in JSON format.
    try:
        r = requests.post(endpoint, headers=auth_header,
            json={"query": connector, "variables": vars})
        res = load_content(r.content)
    except Exception as e:
        s = "Update object request failed: " + str(e)
        raise UpdateObjectError(s)

    if r.status_code == 200:
        # Even if the return code was 200, we could still have errors.
        if 'errors' in res:
            s = "Failed to update object: " + updated_model_name \
                + " ERROR: " + res['errors'][0]['message']
            raise UpdateObjectError(s)
        else:
            return res['data'][connector_name]
    else:
        s = "ERROR: Failed to update object: %s CODE: %d REASON: %s MSG: %s" % (updated_model_name, r.status_code, r.reason, res['errors'][0]['message'])
        raise UpdateObjectError(s)

def update_obj_custom(endpoint, id_token, model_name, obj,
    connector, connector_name, use_local_instance=False):
    # Get the header
    auth_header = get_auth_header(id_token, use_local_instance=use_local_instance)

    # Set the input for update object query
    vars = {"input": obj}
    updated_model_name = model_name[0].upper() + model_name[1:]
   
    # Send the POST request.  All queries & mutations are sent
    # as a post request in aws-amplify/graphql, in JSON format.
    try:
        r = requests.post(endpoint, headers=auth_header,
            json={"query": connector, "variables": vars})
        res = json.loads(r.content)
    except Exception as e:
        s = "Update object request failed: " + str(e)
        raise UpdateObjectError(s)

    if r.status_code == 200:
        # Even if the return code was 200, we could still have errors.
        if 'errors' in res:
            s = "Failed to update object: " + updated_model_name \
                + " ERROR: " + res['errors'][0]['message']
            raise UpdateObjectError(s)
        else:
            return res['data'][connector_name]
    else:
        s = "ERROR: Failed to update object: %s CODE: %d REASON: %s MSG: %s" % (updated_model_name, r.status_code, r.reason, res['errors'][0]['message'])
        raise UpdateObjectError(s)

# Get a specific object of a given model with specified field as key
def get_obj(endpoint, id_token, model_name, vars,
            secondaryKeyFunction=False, custom_query=None,
            queries_module=None, use_local_instance=False):
    # Get the header
    auth_header = get_auth_header(id_token, use_local_instance=use_local_instance)

    if not queries_module:
        queries_module = Queries
    if use_local_instance:
        updated_model_name = model_name[0].upper() + model_name[1:]
        connector_name = "get" + updated_model_name
    elif secondaryKeyFunction:
        connector_name = model_name
        updated_model_name = model_name
    else:
        updated_model_name = model_name[0].upper() + model_name[1:]
        connector_name = "get" + updated_model_name

    filter_vars = vars
    if use_local_instance:
        connector = Localops.LOCALOPS[connector_name.lower()]
        filter_vars = {}
        filter_vars = {'filter': vars}
    elif custom_query:
        connector = custom_query
    else:
        connector = queries_module.QUERIES[connector_name.lower()]

    # Send the POST request.  All queries & mutations are sent
    # as a post request in aws-amplify/graphql, in JSON format.
    try:
        r = requests.post(endpoint, headers=auth_header,
                json={"query": connector, "variables": filter_vars})

        res = load_content(r.content)
    except Exception as e:
        s = "Get obj request failed: " + str(e)
        raise GetObjError(s)

    if r.status_code == 200:
        # Even if the return code was 200, we could still have errors.
        if not 'errors' in res:
            if use_local_instance:
                connector_name = make_lower(model_name)
                if res['data'][connector_name]:
                    return res['data'][connector_name]
                else:
                    s = "Could not find object: %s" % (connector_name)
                    raise GetObjError(s)
            if not secondaryKeyFunction:
                return res['data'][connector_name]

            if len(res['data'][connector_name]['items']) == 1:
                return res['data'][connector_name]['items'][0]
            else:
                s = "Could not find object: secondaryKeyFunction: %s" % (connector_name)
                raise GetObjError(s)
        else:
            s = "Failed to get objects: " + updated_model_name \
                + " ERROR: " + res['errors'][0]['message']
            raise GetObjError(s)
    else:
        s = "ERROR: Failed to get objects: %s CODE: %d REASON: %s MSG: %s" % (updated_model_name, r.status_code, r.reason, res['errors'][0]['message'])
        raise GetObjError(s)

# Get all the objects of a given model from a given starting point
def get_objs(endpoint, starting_from, id_token, model_name, filter,
             secondaryKeyFunction=False, custom_query=None,
             queries_module=None, use_local_instance=False,
             custom_query_filter=None):
    # Get the header
    auth_header = get_auth_header(id_token,
        use_local_instance=use_local_instance)

    if not queries_module:
        queries_module = Queries

    # Set the input for list objects query
    limit_count = 100
    vars = {}
    if use_local_instance:
        if filter:
            vars['filter'] = convert_filter(filter)
        vars['skip'] = starting_from
        vars['take'] = limit_count
    else:
        vars = {"limit": limit_count, "nextToken": starting_from}
        if (filter):
            vars['filter'] = filter

    if custom_query_filter:
        vars.update(custom_query_filter)

    if secondaryKeyFunction:
        connector_name = model_name
        updated_model_name = model_name
    else:
        updated_model_name = model_name[0].upper() + model_name[1:]
        connector_name = "list" + updated_model_name + "s"

    if use_local_instance:
        updated_model_name = capitalize(model_name)
        connector_name = 'list' + plural(updated_model_name)
        connector = Localops.LOCALOPS[connector_name.lower()]
        connector_name = plural(make_lower(model_name))
    elif custom_query:
        connector = custom_query
    else:
        connector = queries_module.QUERIES[connector_name.lower()]

    # Send the POST request.  All queries & mutations are sent
    # as a post request in aws-amplify/graphql, in JSON format.
    try:
        r = requests.post(endpoint, headers=auth_header,
            json={"query": connector, "variables": vars})
        res = load_content(r.content)
    except Exception as e:
        s = "List objects request failed: " + str(e)
        raise ListObjectsError(s)

    if r.status_code == 200:
        # Even if the return code was 200, we could still have errors.
        if not 'errors' in res:
            #print "Got Connectors"
            #print res['data']['listConnectorss']['items']
            if use_local_instance:
                if len(res['data'][connector_name]) == limit_count:
                    nextToken = starting_from + limit_count
                else:
                    nextToken = 0
                return (res['data'][connector_name], nextToken)
            else:
                return (res['data'][connector_name]['items'],
                        res['data'][connector_name]['nextToken'])
        else:
            s = "Failed to get objects: " + updated_model_name \
                + " ERROR: " + res['errors'][0]['message']
            raise ListObjectsError(s)
    else:
        s = "ERROR: Failed to get objects: %s CODE: %d REASON: %s MSG: %s" % (updated_model_name, r.status_code, r.reason, res['errors'][0]['message'])
        raise ListObjectsError(s)

def get_model_objects(endpoint, id_token, model_name, filter,
        secondaryKeyFunction=False, custom_query=None,
        queries_module=None, use_local_instance=False):
    next_token = None
    obj_list = []

    while True:
        try:
            tmp_obj_list, next_token = get_objs(endpoint, next_token,
                id_token, model_name, filter,
                secondaryKeyFunction=secondaryKeyFunction,
                custom_query=custom_query,
                queries_module=queries_module,
                use_local_instance=use_local_instance)
            obj_list = obj_list + tmp_obj_list

            if not next_token:
                return obj_list
        except ListObjectsError as e:
            print("ERROR: %s" % (str(e)))
            raise

    return obj_list

def remove_model_objects(endpoint, id_token, model_name, obj_list,
    custom_query=None, mutations_module=None):
    for tmp_obj in obj_list:
        try:
            remove_obj(endpoint, id_token, model_name, tmp_obj,
                custom_query=custom_query, mutations_module=mutations_module)
        except:
            pprint.pprint(tmp_obj)
            traceback.print_exc()
            raise

def insert_model_objects(endpoint, id_token, model_name, obj_list,
    custom_query=None, mutations_module=None):
    for tmp_obj in obj_list:
        insert_obj(endpoint, id_token, model_name, tmp_obj,
            custom_query=custom_query, mutations_module=mutations_module)

def update_model_objects(endpoint, id_token, model_name,
    obj_list, custom_query=None, mutations_module=None):
    for tmp_obj in obj_list:
        update_obj(endpoint, id_token, model_name, tmp_obj,
            custom_query=custom_query, mutations_module=mutations_module)

# Gzip a provided string
def gzip_string(input_str):
    """
    out = StringIO.StringIO()
    f = gzip.GzipFile(fileobj=out, mode="w")
    f.write(input_str)
    return out.getvalue()
    """
    if six.PY3 and type(input_str) == str:
        input_str = input_str.encode()
    return codecs.encode(input_str, 'zlib')

#Gunzip a provided string
def gunzip_bytes(input_bytes):
    return codecs.decode(input_bytes, 'zlib')

def b64encode(input_bytes):
    return base64.b64encode(input_bytes)

def b64decode(input_str):
    return base64.b64decode(input_str)

