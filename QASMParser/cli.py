import argparse

# DictKeyPair taken from StackOverflow
class StoreDictKeyPair(argparse.Action):
     def __call__(self, parser, namespace, values, option_string=None):
         my_dict = {}
         for kv in values.split(","):
             k,v = kv.split("=")
             my_dict[k] = v
         setattr(namespace, self.dest, my_dict)

parser = argparse.ArgumentParser(description='QASM parser to translate from QASM to QuEST input', add_help=True)
parser.add_argument('sources', nargs=argparse.REMAINDER, help="List of sources to compile")
parser.add_argument('-o','--output', help="File to compile to")
parser.add_argument('-l','--language', help="Output file language")
parser.add_argument('-d','--debug', help="Output original QASM in translation", action="store_true")
parser.add_argument('-c','--to-module', help = "Compile as module for inclusion into larger project", action="store_true")
parser.add_argument("-I","--include", help = 'Include a pre-"compiled" source', action=StoreDictKeyPair, metavar="QASMFILE=CFILE,QASMFILE2=CFILE2,...", default={})

def get_command_args():
    argList = parser.parse_args()
    if not argList.sources:
        parser.print_help()
        exit()
    return argList
