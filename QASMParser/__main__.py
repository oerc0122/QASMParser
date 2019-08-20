#!/usr/bin/env python3
"""
Main program for transpiling QASM scripts into QuEST input format
"""

from QASMParser.QASMParser import ProgFile
from QASMParser.QASMQuESTGate import setup_QASM_gates
from QASMParser.Cli import get_command_args
from QASMParser.CircuitDiag import (print_circuit_diag)
from QASMParser.AdjMat import (calculate_adjmat, best_slice_adjmat)
from QASMParser.QASMErrors import (noSpecWarning)
from QASMParser.Partitioning import (partition)
from QASMParser.METISPartition import (calculate_adjlist, Tree)

def main():
    """ Run main program """
    argList = get_command_args()

    # Set up the core internal gates
    setup_QASM_gates()
    if argList.print:
        for source in argList.sources:
            myProg = ProgFile(source)
            print(source)
            print_circuit_diag(myProg, maxDepth=argList.max_depth)
        return

    if argList.analyse:
        # for source in argList.sources:
        #     myProg = ProgFile(source)
        #     print(source)
        #     mat = calculate_adjmat(myProg, maxDepth=argList.max_depth)
        #     regNames = ["{reg.name:.5}" for reg in myProg.quantumRegisters]
        #     bestSlice = best_slice_adjmat(mat)

        #     print(bestSlice, mat.nQubits, mat.slice_cost(bestSlice))
        for source in argList.sources:
            myProg = ProgFile(source)
            print(source)
            adj = calculate_adjlist(myProg, maxDepth=argList.max_depth)
            for i, vert in enumerate(adj.adjList):
                print(vert, "# ",i)
            tree = Tree(adj.adjList)
            tree.split_graph()
            print(tree.tree_form("vertices"))
            print(adj.nVerts)
        return

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

    for source in argList.sources:
        myProg = ProgFile(source)
        partition(myProg, argList.partition)
        myProg.to_lang(outputFile, argList.to_module, argList.include, lang, argList.debug)

if __name__ == "__main__":
    main()
