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
import argparse
import configparser
import sys
from ecube.run import Run
from ecube.playbook import Playbook

import os
import ecube.gql as gql

DEFAULT_ENV = 'ALPHA'

class MyParser(object):

    def __init__(self):
        self.config_args = {}
        parser = argparse.ArgumentParser(
            description='e3 (ecube) -> epiphani execution engine',
            usage='''e3 <command> [<args>]
The following commands are supported:
    run      Run a local connector
    runcli   Run a cli as a connector 
    playbook Interact with the playbook engine 
    
Please create a config file ~/.e3.ini with following content:
[DEFAULT]
username = <epiphani username> <REQUIRED>
password = <epiphani password> <REQUIRED>
login = URL to epiphani <OPTIONAL>
log_file = foo.log <OPTIONAL>
local_install = true <OPTIONAL | Use local installation | Default: false>
local_install_host = localhost <OPTIONAL | IP/FQDN of local installation | Default: localhost>
local_install_port = 31050 <OPTIONAL | GraphQL server port number | Default: 31050>

If you set local_install_host or local_install_port, local_install is automatically set to true
''')
        config = configparser.ConfigParser()
        FN = os.path.expanduser('~/.e3.ini')
        config.read(FN)
        for key in config['DEFAULT']:
            self.config_args[key] = config['DEFAULT'][key]
        if not self.config_args.get('login'):
            self.config_args['login'] = DEFAULT_ENV
        if not self.config_args.get('username') or not self.config_args.get('password'):
            print("Missing config")
            parser.print_help()
            exit(1)
        tmp_user_list = [{'username': self.config_args['username'], 'passwd': self.config_args['password']}]
        gql.set_env_var(self.config_args['login'], 'USERS', tmp_user_list)
        parser.add_argument('command', help='Subcommand to run')
        # parse_args defaults to [1:] for args, but you need to
        # exclude the rest of the args too, or validation will fail
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command):
            print('Unrecognized command')
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
        parser.add_argument('--publish-playbooks', required=False,
            help="Only publish the playbooks (as epiphani, not developer) and exit",
            default=False, action='store_true')
        args = parser.parse_args(sys.argv[2:])
        self.addKeys(args)
        runCommand(args)
    def runcli(self):
        parser = argparse.ArgumentParser(description='Run the commands')
        parser.add_argument('--name', required=True, help='the name of the connector to create')
        args = parser.parse_args(sys.argv[2:])

        self.addKeys(args)
        runCLI(args)
    def playbook(self):
        parser = argparse.ArgumentParser(
            description="playbook sub commands")
        s1 = parser.add_subparsers(title="commands", dest="command")
        s1.add_parser("show", help="show all the playbooks")
        pbn = s1.add_parser("run", help="run the playbooks")
        pbn.add_argument('--name',  dest="PBName", required=True, help='the name of the playbook to run')
        pbn.add_argument('--vars',  dest="PBVars", required=False, help='the variables to pass to playbook')
        pbn.add_argument('--json',  type=bool, required=False, help='output only json', default=False)
        pbc = s1.add_parser("create", help="create a playbook")
        pbc.add_argument('--directory', required=True, help='the path to the playbook')
        pbc.add_argument('--name',  dest="PBName", required=False, help='overwrite the name of the playbook in yaml')
        pbcon = s1.add_parser("connectors", help="show the list of connectors")
        pbcon.add_argument('--name',  dest="CName", required=False, help='Show details about connector')
        pbres = s1.add_parser("results", help="show the output of the playbook executed")
        pbres.add_argument('--name',  dest="PBName", required=True, help='the result of this playbook')
        pbres.add_argument('--json',  type=bool, required=False, help='output only json', default=False)

        args = parser.parse_args(sys.argv[2:])
        self.addKeys(args)
        playBook(args)

def runCommand(args):
    #validate args 
    x = Run(args)
    x.Execute()

def runCLI(args):
    #validate args 
    x = Run(args)
    x.ExecuteCLI()

def playBook(args):
    x = Playbook(args)
    getattr(x, args.command)()

def main():
    MyParser()
