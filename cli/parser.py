import argparse
from run  import Run
def runCommand(args):
    #validate args 
    print ("Run Commands called", args)
    x = Run(args)
    x.Execute()

def main():
    parser = argparse.ArgumentParser(description='e3 (ecube) -> epiphani execution engine')
    parser.add_argument('-l', '--login', required=True, help='login url')
    parser.add_argument('-u', '--username', required=True, help='username to login')
    parser.add_argument('-p', '--password', required=True, help='password to login')
    parser.add_argument('-log_file', help='log to file')

    run = parser.add_subparsers(help='run the connector')

    parser_b = run.add_parser('run', help='run connector')
    parser_b.set_defaults(func=runCommand)
    parser_b.add_argument('--directory', help='the path to the connector')
    args = parser.parse_args()

    #call the fu nction in the subparser
    args.func(args)

