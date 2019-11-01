#!/usr/bin/env python3
"""
Main program for transpiling QASM scripts into QuEST input format
"""

from QASMParser.QASMParser import ProgFile
from QASMParser.QASMQuESTGate import setup_QASM_gates
from QASMParser.Cli import get_command_args
from QASMParser.QASMErrors import (noSpecWarning)
from QASMParser.Partitioning import (partition)
from QASMParser.CodeGraph import (GraphBuilder, parse_code)
from QASMParser.QASMTypes import (QuantumRegister)

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
            if argList.dummy_partition:

                if argList.partition == 0:
                    pass
                elif argList.partition == 1:
                    mat = codeGraph.adjMat
                    bestSlice = [reg.end-1 for reg in myProg.quantumRegisters]

                    print(bestSlice, mat.nQubits, mat.slice_cost(bestSlice))

                elif argList.partition == 2:
                    mat = codeGraph.adjMat
                    bestSlice = mat.best_slice_adjmat()

                    print(bestSlice, mat.nQubits, mat.slice_cost(bestSlice))

                elif argList.partition == 3:
                    adj = codeGraph.adjList

                    ### Drawing
                    #import pygraphviz as pg
                    #edgeList = [tuple([edge, i]) for i, vertex in enumerate(adj.adjList) for edge in vertex.edges]
                    #graph = pg.AGraph()
                    #for edge in edgeList:
                    #    graph.add_edge(*edge)
                    #graph.draw('graph.png', prog='neato')
                    ### EndDraw

                    tree = Tree(adj.adjList)
                    tree.split_graph()
                    print(tree.tree_form("vertIDs"))
                    tree.contract()
                    print(tree.tensor.qureg)
                else:
                    raise IndexError("Unrecognised partition type")


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
