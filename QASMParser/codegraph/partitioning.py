"""
Module which performs the partitioning and set-up of quantum registers based on the partitioner request
"""
from enum import (IntEnum)
from ..parser.parser import (ProgFile)
from ..parser.types import (TensorNetwork)
from ..parser.errors import (partitionWarning)
from .codegraph import (GraphBuilder)

def partition(code: ProgFile, partitionLevel: int = 0, maxDepth=-1):
    """ Call correct partitioner based on partition level """
    partitionTypes = IntEnum("PartitionTypes", "NONE REGISTER SPACELIKE FULL", start=0)
    if partitionLevel == partitionTypes.NONE:
        return code

    if partitionLevel == partitionTypes.REGISTER:
        bestSlice = tuple([register.end for register in code.quantumRegisters])

    if partitionLevel == partitionTypes.SPACELIKE:
        codeGraph = GraphBuilder(code.quantumRegisters.numQubits, code,
                                 partition=partitionLevel)
        adjMat = codeGraph.parse_code(maxDepth=maxDepth).adjMat
        bestSlice = adjMat.best_slice_adjmat()
        if not bestSlice:
            print(partitionWarning)

    if partitionLevel == partitionTypes.FULL:
        pass

    code.partition = create_tensor_network(adjMat, code, bestSlice)

    return code

def create_tensor_network(adjMat, code, slices):
    """ Build the tensor network command and calculate the number of virtual qubits needed for the operation """
    tnNodes, virtualQubits = adjMat.divide_qubits(slices)
    *physicalQubits, = map(len, tnNodes)
    code.useTN = True
    return TensorNetwork(code, "qreg", physicalQubits, virtualQubits)
