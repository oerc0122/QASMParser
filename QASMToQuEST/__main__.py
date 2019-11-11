#!/usr/bin/env python3
"""
Main program for transpiling QASM scripts into QuEST input format
"""

from .Cli import get_command_args
from QASMParser.Parser.Parser import ProgFile
from QASMParser.Parser.CoreGates import setup_QASM_gates
from QASMParser.Parser.Errors import (noSpecWarning)
from QASMParser.Parser.Types import (QuantumRegister)
from QASMParser.GraphBuilder.Partitioning import (partition)
from QASMParser.GraphBuilder.CodeGraph import (GraphBuilder, parse_code)

def main():
    """ Run main program """
    argList = get_command_args()
    setup_QASM_gates()

    for source in argList.sources:
        myProg = ProgFile(source)
        print(source)
        # Set up the core internal gates


        if  any((argList.analyse, argList.dummy_partition, argList.print)):
            codeGraph = GraphBuilder(QuantumRegister.numQubits, myProg,
                                     analyse=argList.analyse,
                                     printASCII=argList.print,
                                     partition=argList.partition)

            parse_code(myProg, codeGraph, maxDepth=argList.max_depth)
            codeGraph.finalise()


        else:
            lang = None
            if argList.language:
                lang = argList.language
            elif argList.output.endswith('.py'):
                lang = "Python"
            elif argList.output.endswith('.c'):
                lang = "C"
            elif not argList.output:
                raise IOError(noSpecWarning)

            if not lang:
                raise IOError(noSpecWarning)

            if argList.output:
                outputFile = argList.output
            else:
                outputFile = None

            partition(myProg, argList.partition)
            myProg.to_lang(outputFile, lang,
                           include_internals=argList.include_internals,
                           includes=argList.include,
                           module=argList.to_module,
                           verbose=argList.debug)

if __name__ == "__main__":
    main()
