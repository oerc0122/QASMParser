#!/usr/bin/env python3
"""
Main program for transpiling QASM scripts into QuEST input format
"""
from QASMParser.parser.parser import (ProgFile)
from QASMParser.parser.coregates import setup_QASM_gates
from QASMParser.parser.types import (QuantumRegister)
from QASMParser.codegraph.partitioning import (partition)
from QASMParser.codegraph.codegraph import (CodeGraph)
from .cli import get_command_args
from .printer import (to_lang)
from .errors import (noSpecWarning)

def main():
    """ Run main program """
    argList = get_command_args()

    if any((argList.analyse, argList.dummy_partition, argList.print, argList.partition > 1)):
        from QASMParser.codegraph.codegraph import (GraphBuilder)

    # Set up the core internal gates
    setup_QASM_gates()

    for source in argList.sources:
        myProg = ProgFile(source)
        print(source)

        if  any((argList.analyse, argList.dummy_partition, argList.print)):

            if argList.print:
                codeGraph = CodeGraph(QuantumRegister.numQubits, myProg)
                codeGraph.draw("graph.pdf", labelAttr="opName")
                del codeGraph

            if argList.dummy_partition:
                partition(myProg, argList.partition, argList.max_depth, dummy=True)

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
            to_lang(myProg, outputFile, lang,
                    include_internals=argList.include_internals,
                    includes=argList.include,
                    module=argList.to_module,
                    verbose=argList.debug)

if __name__ == "__main__":
    main()
