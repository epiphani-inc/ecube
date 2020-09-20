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
local_install = true <OPTIONAL | Use local installation | Default: false>
local_install_host = localhost <OPTIONAL | IP/FQDN of local installation | Default: localhost>
local_install_port = 31050 <OPTIONAL | GraphQL server port number | Default: 31050>

If you set local_install_host or local_install_port, local_install is automatically set to true

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
This will create a connector that will be executed on the machine that is running e3. It can be made a part of any playbooks on the playbook engine. Please see this: https://github.com/epiphani-inc/ecube/wiki/Install

## Use ecube to create & run playbooks

### Create a playbook

There are some simple sample playbooks in the gitrepo @ ./samples/playbooks
You will have to edit them to add you AWS secret and key information where it says <>.

Once you have the samples edited and e3 installed, you can just create the playbook like this:
```
e3 playbook create --directory ./samples/playbooks/threeNode --name EC2CL109
```

### Execute a playbook

To execute a playbook you just need to give the name of the playbook to run

```
e3 playbook run --vars '{"region": "us-west-2"}' --name EC2CL108
```

In this case the playbook needs variables - region where it is going to fetch the state from. 
