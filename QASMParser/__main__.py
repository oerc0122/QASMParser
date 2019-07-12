#!/usr/bin/env python3

from QASMParser.QASMParser import *
import QASMParser.QASMQuESTGate
from QASMParser.cli import get_command_args
from QASMParser.partition import quickDispl

def main():
    argList = get_command_args()
    
    if argList.print:
        for source in argList.sources:
            myProg = ProgFile(source)
            print(source)
            quickDispl(myProg, topLevel = True)
        return

    lang = None
    if argList.language:
        lang = argList.language
    elif argList.output.endswith('.py'):
        lang = "Python"
    elif argList.output.endswith('.c'):
        lang = "C"
    elif not argList.output:
        raise IOError('Neither language nor output specified')

    if not lang: raise IOError('No language specified')

    if argList.output:
        outputFile = argList.output
    else:
        outputFile = None

    for source in argList.sources:
        myProg = ProgFile(source)
        myProg.to_lang(outputFile, argList.to_module, lang, includes= argList.include, verbose=argList.debug)

if __name__ == "__main__":
    main()
