# ecube
epiphani execution engine (e3) allows running local scripts and commands in conjunction with other cloud based connectors to create low-code playbooks. These can be shared with other team members using collaboration tools such as Slack. For more information visit: https://www.epiphani.ai

## Installation
```
$ pip install epiphani-ecube
```

## ecube config & arguments

In order to use ecube, you need to first create an epiphani account. Once you have the account, you need to setup ecube by adding your credentials in **~/.e3.ini**
```
(ecube) pmadhav@ip-172-31-46-212:~$ e3 --help
usage: e3 <command> [<args>]
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

e3 (ecube) -> epiphani execution engine

positional arguments:
  command     Subcommand to run

optional arguments:
  -h, --help  show this help message and exit
(ecube) pmadhav@ip-172-31-46-212:~$ 
```

## Using ecube examples

### runcli

```
e3 runcli --name pmCli
```
