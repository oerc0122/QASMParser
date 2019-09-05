"""
Module to handle command line interface options for QASM transpiler
"""
import argparse

# SmartFormatter taken from StackOverflow
class SmartFormatter(argparse.HelpFormatter):
    """ Class to allow raw formatting only on certain lines """
    def _split_lines(self, text, width):
        if text.startswith('R|'):
            return text[2:].splitlines()
        # this is the RawTextHelpFormatter._split_lines
        return argparse.HelpFormatter._split_lines(self, text, width)

# DictKeyPair taken from StackOverflow
class StoreDictKeyPair(argparse.Action):
    """ Class to convert a=b into dictionary key, value pair """
    def __call__(self, parser, namespace, values, optionString=None):
        newDict = {}
        for keyVal in values.split(","):
            key, value = keyVal.split("=")
            newDict[key] = value
        setattr(namespace, self.dest, newDict)

_parser = argparse.ArgumentParser(description='QASM parser to translate from QASM to QuEST input',
                                  add_help=True, formatter_class=SmartFormatter)
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
_parser.add_argument('--max-depth', help="Max depth for analysis and printing", type=int, default=-1)
_parser.add_argument('--include-internals', help="Include internal gates explicitly", action="store_true")
_parser.add_argument('-P', '--partition', help=
                     """R|Set partitioning optimisation type: 
    0 = None  -- Do not attempt to partition,
    1 = Registers -- Partition based on specification of qregs in QASM,
    2 = Space-like -- Slice only in qreg space based on adjacent slice-cost analysis,
    3 = Space-time-like -- Perform full graph analysis and attempt to partition
""", type=int, default=0)

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
