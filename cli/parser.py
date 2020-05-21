import argparse
import configparser
import sys
from run  import Run
from playbook  import Playbook

import os
class MyParser(object):

    def __init__(self):
        self.config_args = {}
        parser = argparse.ArgumentParser(
            description='e3 (ecube) -> epiphani execution engine',
            usage='''e3 <command> [<args>]
The following commands are supported:
    run      Run a local connector
    playbook Interact with the playbook engine 
    
Please create a config file ~/.e3.ini with following content:
[DEFAULT]
username = <epiphani username>
password = <epiphani password> 
login = URL to epiphani
log_file = foo.log
''')
        config = configparser.ConfigParser()
        FN = os.path.expanduser('~/.e3.ini')
        config.read(FN)
        for key in config['DEFAULT']:
            self.config_args[key] = config['DEFAULT'][key]
        parser.add_argument('command', help='Subcommand to run')
        # parse_args defaults to [1:] for args, but you need to
        # exclude the rest of the args too, or validation will fail
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command):
            print 'Unrecognized command'
            parser.print_help()
            exit(1)
        # use dispatch pattern to invoke method with same name
        getattr(self, args.command)()

    def addKeys(self, args):
        d = vars(args)
        for key in self.config_args:
            d[key] = self.config_args[key]

    def run(self):
        parser = argparse.ArgumentParser(description='Run the commands')
        parser.add_argument('--directory', required=True, help='the path to the connector')
        args = parser.parse_args(sys.argv[2:])
        self.addKeys(args)
        runCommand(args)

    def playbook(self):
        parser = argparse.ArgumentParser(
            description="playbook sub commands")
        s1 = parser.add_subparsers(title="commands", dest="command")
        s1.add_parser("show", help="show all the playbooks")
        pbn = s1.add_parser("run", help="run the playbooks")
        pbn.add_argument('--name',  dest="PBName", required=True, help='the name of the playbook to run')

        args = parser.parse_args(sys.argv[2:])
        self.addKeys(args)
        playBook(args)

def runCommand(args):
    #validate args 
    x = Run(args)
    x.Execute()

def playBook(args):
    x = Playbook(args)
    getattr(x, args.command)()

def main():
    MyParser()
