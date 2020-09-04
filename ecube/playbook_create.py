import sys
import ecube.gql as cf
import yaml
import glob
import os
import copy
import json
PLAYBOOK_FILE = "playbook.yml"
VARIABLE_FILE = "variables.yml"
CONNECTORS_DIR = "connectors/"
CONNECTOR_DICT = {}
USERS = []
# Leave this as an empty list, it is used to automatically
# populate all the usernames from the list above.
USER_LIST = []
USERNAME_DICT = {}
USER_DICT = {}


def parse_file(file_name, logger):
    logger.log(cf.Logger.log, "Reading FILE: %s " % (file_name))
    with open(file_name, 'r') as stream:
        try:
            logger.log(cf.Logger.DEBUG, "Parsing: %s" % (file_name))
            f = yaml.safe_load(stream)
        except yaml.YAMLError:
            tb_output = StringIO()
            traceback.print_exc(file=tb_output)
            tmp_output = tb_output.getvalue()
            logger.log(cf.Logger.ERROR, tmp_output)
    return f


def get_files(file_pattern):
    return glob.glob(file_pattern)
# Given a directory, return a list of YML files
# that do not have a corresponding MD file, b/c
# the files that have a MD file are Unreleased
# and are work in progress.


def get_integration_files(dir_name):
    f = get_files(dir_name + "/**/*.yml")
    return f


def readConnectors():
    files = get_integration_files("../integration-scripts/connectors/")
    for file1 in files:
        bn = os.path.basename(file1)
        CONNECTOR_DICT[bn.replace(".yml", "")] = file1


def findAllConnectors(pb):
    d = pb.env
    # try:
    obj = cf.execute_function_with_retry(cf.get_model_objects,
                                         (d['endpoint'], d['id_token'],
                                             "Connectors", None),
                                         {}, d['current_env'], d['username'], 1, 0,
                                         USER_LIST, USER_DICT, USERNAME_DICT, pb.logger)
    for val in obj:
        CONNECTOR_DICT[val['name']] = val
        if (val['commandsType'] == 'gzip/b64encoded'):
            tb = cf.b64decode(val['commands'])
            val['commands'] = json.loads(cf.gunzip_bytes(tb))

    # except Exception as e:
    #     pb.logger.log(cf.Logger.ERROR, "DIC: %r" % (e))


def parsePlaybook(args, pb):
    nda = []
    playDict = {}
    for play in pb['plays']:
        connector = "none"
        args = []
        if ('connector' in play):
            connector = play['connector']
        if (connector in CONNECTOR_DICT):
            coninfo = CONNECTOR_DICT[connector]
            for cmd in coninfo['commands']:
                if (cmd['name'] == play['action']):
                    args = copy.deepcopy(cmd)
            play['ConfigData'] = copy.deepcopy(coninfo)
            play['ConfigData'].pop('commands', None)

        cat = "command"
        pa = None
        # print "PLAY", play, connector
        if (play['id'] == 'start' or play['id'] == 'end'):
            cat = play['id']
            play['name'] = play['id']
            play['ConfigData'] = {"category": "Control"}
            play['action'] = play['id']
            play['config'] = {"category": "Control"}
            args = {'arguments': [], 'name': 'control',
                    'description': 'control'}
        else:
            pa = [{'Path': '#003D7F'}]
        mainForm = {'form': {'name': play['name'], 'ContextPath': ''}}
        arr = {
            'id': play['id'],
            'text': play['name'],
            'commandName': play['action'],
            'category': cat,
            'key': play['id'],
            'full': {
                'node': mainForm,
                'config': {
                    'configData': play['ConfigData'],
                    'formdata': play['config'],
                },
                'command': {
                    'formdata': play['config'],
                    'name': play['action'],
                    'configData': args
                }
            }
        }
        if 'iconPath' in play['ConfigData']:
            arr['icon'] =play['ConfigData']['iconPath']

        if pa != None:
            arr['portArray'] = pa

        playDict[play['id']] = copy.deepcopy(arr)
        nda.append(arr)
    for ll in pb['links']:
        fromPort = ""
        if (ll['from'] == "start" or ll['from'] == 'end'):
            fromPort = "B"
        else:
            fromPort = "#003D7F"
        ll['fromPort'] = fromPort
        ll['text'] = fromPort
        ll['toPort'] = "T"

    full = {
        'linkDataArray': pb['links'],
        'nodeDataArray': nda,
        'linkFromPortIdProperty': "fromPort",
        'linkToPortIdProperty': "toPort",
        'class': "GraphLinksModel",
    }
    return full
    # make nodes


def readDirectory(pb):
    # readConnectors()
    findAllConnectors(pb)
    # sys.Exit(0)
    # main file is playbook.yml
    # variables are in variable.yml
    # connectors are in ./connectors/*yml
    pb1 = parse_file(pb.args.directory+"/"+PLAYBOOK_FILE, pb.logger)
    full = parsePlaybook(pb, pb1)
    full['pbFile'] = pb1
    return full
