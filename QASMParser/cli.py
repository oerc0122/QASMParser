"""
Module to handle command line interface options for QASM transpiler
"""
import argparse

# DictKeyPair taken from StackOverflow
class StoreDictKeyPair(argparse.Action):
    """ Class to convert a=b into dictionary key, value pair """
    def __call__(self, parser, namespace, values, optionString=None):
        newDict = {}
        for keyVal in values.split(","):
            key, value = keyVal.split("=")
            newDict[key] = value
        setattr(namespace, self.dest, newDict)

_parser = argparse.ArgumentParser(description='QASM parser to translate from QASM to QuEST input', add_help=True)
_parser.add_argument('sources', nargs=argparse.REMAINDER, help="List of sources to compile")
_parser.add_argument('-o', '--output', help="File to compile to", default="")
_parser.add_argument('-l', '--language', help="Output file language")
_parser.add_argument('-d', '--debug', help="Output original QASM in translation", action="store_true")
_parser.add_argument('-c', '--to-module', help="Compile as module for inclusion into larger project",
                     action="store_true")
_parser.add_argument("-I", "--include", help='Include a pre-transpiled source',
                     action=StoreDictKeyPair, metavar="QASMFILE=CFILE,QASMFILE2=CFILE2,...", default={})
_parser.add_argument('-a', '--analyse', help="Print adjacency matrix info", action="store_true")
_parser.add_argument('-p', '--print', help="Print graphical summary of circuit", action="store_true")

def get_command_args():
    """Run parser and parse arguments

    :returns: List of arguments
    :rtype: argparse.Namespace

    """
    argList = _parser.parse_args()
    if not argList.sources:
        _parser.print_help()
        exit()
    return argList
