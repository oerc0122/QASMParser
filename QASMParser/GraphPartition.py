"""
Module for building adjacency list and firing that through METIS for partitioning
"""
import sys
import ctypes
import itertools as it
from collections import defaultdict
import metis
import numpy as np
from numpy.ctypeslib import as_ctypes
import networkx
import matplotlib.pyplot as plot
import pygraphviz as pg

sys.path += ['/home/jacob/QuEST-TN/utilities/']

# Find QuEST and TN libraries
from QuESTPy.QuESTBase import init_QuESTLib
from TNPy.TNBase import init_TNLib
QuESTPath = "/home/jacob/QuEST-TN/build/TN/QuEST"
TNPath = "/home/jacob/QuEST-TN/build/TN/"
init_QuESTLib(QuESTPath)
init_TNLib(TNPath)

import QuESTPy
import TNPy
import TNPy.TNFunc as TNFunc
import TNPy.TNAdditionalGates as TNAdd
import QuESTPy.QuESTFunc as QuESTFunc

def setup(obj):
    """ Call as setup from GraphBuilder """
    obj.adjList = AdjList(obj.nQubits)

def process(obj, *args, **kwargs):
    """ Call as process from GraphBuilder """
    obj.adjList.process(obj, **kwargs)

def finalise(obj):
    """ Call as finalise from GraphBuilder """
    obj.adjList.finalise()
    # Remove fictional node from split
    adjList = obj.adjList.adjList
    adjList = networkx.subgraph(adjList, (node for node in adjList.nodes if node != "end"))
    for vertex in obj.adjList.verts:
        vertex.fix_edges()
    networkx.nx_agraph.to_agraph(adjList).draw('graph.pdf', prog='dot')

    print(networkx.adjacency_matrix(obj.adjList.entang))
    networkx.nx_agraph.to_agraph(obj.adjList.entang).draw('entang.pdf', prog='dot')
    
    tree = Tree(adjList)
    tree.split_graph()
    print(tree.tree_form("vertIDs"))
    tree.contract()

class Vertex():
    """ Class defining a single tensor node vertex """
    def __init__(self, ID, qubitID, age, graph, operation=None):
        self._ID = ID
        self._qubitID = qubitID
        self._age = age
        self._indices = []
        self._op = operation
        self._contracted = []
        self._parent = graph
        self._fixedEdges = None
        self.lastNode = True

    def fix_edges(self):
        """ Lock in edges for later use """
        self._fixedEdges = list(self.edges)

    ID = property(lambda self: self._ID)
    qubitID = property(lambda self: self._qubitID)
    age = property(lambda self: self._age)
    contracted = property(lambda self: self._contracted)
    predecessors = property(lambda self: [i for i in self.graph.predecessors(self.ID) if i not in self.successors])
    successors = property(lambda self: [i for i in self.graph.successors(self.ID)])
    edges = property(lambda self: ([(pred, self.ID) for pred in self.predecessors] +
                                   [(self.ID, succ) for succ in self.successors]))
    fixedEdges = property(lambda self: self._fixedEdges)
    neighbours = property(lambda self: set(self.predecessors) | set(self.successors))
    nEdges = property(lambda self: len(self.edges))
    op = property(lambda self: self._op)
    graph = property(lambda self: self._parent)

class AdjList():
    """ Build directed graph using NetworkX """
    def __init__(self, size):
        self._adjList = networkx.DiGraph()
        self._entang = networkx.MultiGraph()
        for i in range(size):
            self._entang.add_node(i)
            self._adjList.add_node(i, node=Vertex(ID=i, qubitID=i, age=1, graph=self.adjList))
        self._lastUpdated = [node for node in self.adjList]
        end = Vertex(ID="end", qubitID=None, age=None, graph=self.adjList, operation=None)
        self.adjList.add_node("end", node=end)
        self._nGate = [1]*size

    entang = property(lambda self: self._entang)
    verts = property(lambda self: (self.adjList.nodes[vertex]["node"]
                                   for vertex in self.adjList.nodes if vertex != "end"))
    adjList = property(lambda self: self._adjList)
    nVerts = property(lambda self: len(self.adjList)-1)
    edges = property(lambda self: (edge for edge in self.adjList.edges if "end" not in edge))

    def process(self, obj, **kwargs):
        """ Build graph from code """
        for qubit in obj.qubitsInvolved:
            prev = self._lastUpdated[qubit]
            self._nGate[qubit] += 1
            self.adjList.node[prev]["node"].lastNode = False
            current = self.nVerts
            # Add new state as vertex
            node = Vertex(ID=self.nVerts, qubitID=qubit, age=self._nGate[qubit],
                          graph=self.adjList, operation=kwargs['lineObj'])
            self._adjList.add_node(current, node=node)
            # Link last updated vertex to current
            self._adjList.add_edge(prev, current, weight=1)
            self._lastUpdated[qubit] = current
            if qubit != min(obj.qubitsInvolved): # Skip if initial qubit (nothing to link to)
                self._adjList.add_edge(current, lastVertex, weight=1)
                self._adjList.add_edge(lastVertex, current, weight=1)
                self._entang.add_edge(self.adjList.node[lastVertex]["node"].qubitID,
                                      self.adjList.node[current]["node"].qubitID, weight=1)
            # Link to previous qubit in operation
            lastVertex = current

    def finalise(self):
        """ Link final qubit with fictional outlet """
        for node in self._lastUpdated:
            self.adjList.add_edge(node, "end", key="end")
        

class TensorNode:
    """ Class containing details relating to tensor contractions """
    def __init__(self, tensor, node, edges, indices, qubits):
        self.tensor = tensor
        self._node = node
        self._edges = edges
        self._indices = indices
        self._qubits = qubits

    node = property(lambda self: self._node)
    edges = property(lambda self: self._edges)
    indices = property(lambda self: self._indices)
    qubits = property(lambda self: self._qubits)

    @staticmethod
    def inherit(left, right, prop, contractionEdges):
        """ Set self's indices and qubits to the combination of left and right """
        return ([propty for contracted, propty in zip(contractionEdges[0], getattr(left, prop)) if not contracted] +
                [propty for contracted, propty in zip(contractionEdges[1], getattr(right, prop)) if not contracted])

    @staticmethod
    def contract(left, right, contractionEdges):
        """ Contract two tensor nodes and update the respective properties """
        contPass = [[i for i, edges in enumerate(cont) if edges] for cont in contractionEdges]
        freePass = [[i for i, edges in enumerate(cont) if not edges] for cont in contractionEdges]
        # Transform into ctypes arrays
        *contPass, = map(lambda pyarr: (ctypes.c_int * len(pyarr))(*pyarr), contPass)
        *freePass, = map(lambda pyarr: (ctypes.c_int * len(pyarr))(*pyarr), freePass)
        out = TensorNode(TNFunc.contractIndices(left.tensor, right.tensor,
                                                contPass[0], contPass[1], ctypes.c_int(len(contPass[0])),
                                                freePass[0], ctypes.c_int(len(freePass[0])),
                                                freePass[1], ctypes.c_int(len(freePass[1])), env),
                         node=left.node, # Inherit left's ID
                         edges=TensorNode.inherit(left, right, 'edges', contractionEdges),
                         indices=TensorNode.inherit(left, right, 'indices', contractionEdges),
                         qubits=TensorNode.inherit(left, right, 'qubits', contractionEdges))
        return out


class Tree:
    """ Class defining tree head """

    def __init__(self, graph=None):
        self._tier = 0
        self.child = []
        self._adjList = graph
        # Default to None if not in current scope
        self._tensor = None
        self.root = self

    def __add__(self, other):
        if self.nChild < 2:
            self.child.append(other)
            return self
        raise IndexError('Binary tree cannot have more than 2 children')

    tensorNode = property(lambda self: self._tensor)
    tensor = property(lambda self: self._tensor.tensor)
    indices = property(lambda self: self._tensor.indices)
    tier = property(lambda self: self._tier)
    isLeaf = property(lambda self: not self.child)
    left = property(lambda self: self.child[0])
    right = property(lambda self: self.child[1])
    nChild = property(lambda self: len(self.child))
    nVerts = property(lambda self: len(self._adjList))
    edges = property(lambda self: (edge for edge in self.tensorNode.edges))
    vertices = property(lambda self: [self.adjList.nodes[vertex]["node"] for vertex in self.adjList.nodes])
    vertIDs = property(lambda self: [vertex.ID for vertex in self.vertices])
    nEdge = property(lambda self: len(self.adjList))
    adjList = property(lambda self: self._adjList)
    nEdges = property(lambda self: len(self.fullEdges))

    @property
    def nodeID(self):
        """ Get ID of node for leaves """
        for node in self.adjList.nodes:
            a = node
        return a

    @property
    def vertex(self):
        """ Vertex getter """
        return self.adjList.node[self.nodeID]["node"]

    @property
    def fullNode(self):
        """ Get full graph's vertex """
        return self.root.adjList.node[self.nodeID]

    @property
    def fullEdges(self):
        """ Get full graph's vertex """
        return self.root.adjList.edges(self.nodeID)

    @property
    def vertices(self):
        for i in self.adjList.nodes:
            yield self.adjList.nodes[i]["node"]

    def __str__(self):
        return self.tree_form("vertIDs")

    def leaves(self):
        """ Return leaves """
        if self.isLeaf:
            yield self
        else:
            for child in self.child:
                yield from child.leaves()

    def dfs(self):
        """ Search left edge for non-contracted children and resolve left-up """
        for child in self.child:
            yield from child.dfs()
        yield self

    def least_connect(self):
        """ Return vertices with the fewest edges first """
        for element in reversed(sorted(self.adjList, key=lambda elem: elem.nEdge)):
            yield element

    def most_connect(self):
        """ Return vertices with the fewest edges first """
        for element in sorted(self.adjList, key=lambda elem: elem.nEdge):
            yield element

    def contract_order(self, order=0):
        """ Generator returning leaves in expected resolution order """
        contractOrder = (self.dfs, self.least_connect, self.most_connect)
        return contractOrder[order]()

    def resolve(self):
        """
        Initialise tensor/qureg
        Call our operation on qubits
        Update self resolved

        Return TensorObject
        """
        
        vertex = self.vertex
        print(f"Hi, I'm {vertex.ID}") 
        nVirtQubit = vertex.nEdges - 1

        print(f"I have {vertex.nEdges} edges and 1 physical qubit")
        print(f"My edges are {list(vertex.edges)}")
        self._tensor = TensorNode(TNFunc.createTensor(1, nVirtQubit, env),
                                  edges=vertex.fixedEdges,
                                  node=vertex.ID,
                                  indices=[(vertex.ID, i) for i in range(vertex.nEdges)],
                                  qubits=[vertex.qubitID for i in range(vertex.nEdges)])

        # If we're initialise -- createTensor => |0>
        if vertex.op is None:
            return

        # Entangle first virtual with physical qubit
        print("TARGET HALF")
        TNAdd.TN_controlledGateTargetHalf(QuESTFunc.controlledNot, self.tensor, 1, 0)

        if vertex.op.name == "CX":
            gate = QuESTFunc.controlledNot
            args = [0, 2]
        elif vertex.op.name == "U":
            gate = QuESTFunc.hadamard
            args = [0]

        for vertex in self.vertices:
            if gate.control:
                if vertex.qubitID == vertex.op.qargs[gate.control-1][1]:
                    print("Control")
                    # physical qubit is the control, virtual qubit is the target
                    print(args)
                    TNAdd.TN_controlledGateControlHalf(gate, self.tensor, *args)
                else:
                    print("Target")
                    # virtual qubit is the control, physical qubit is the target
                    print(args[::-1])
                    TNAdd.TN_controlledGateTargetHalf(gate, self.tensor, *args[::-1])
            else:
                TNAdd.TN_singleQubitGate(gate, self.tensor, *args)

    @staticmethod
    def compute_contraction_edges(left, right):
        return ([edge[::-1] in right.tensorNode.edges or
                 edge in right.tensorNode.edges for edge in left.edges],
                [edge[::-1] in left.tensorNode.edges or
                 edge in left.tensorNode.edges for edge in right.edges])


    def contracted_nodes(self, left, right):
        self._adjList = networkx.contracted_nodes(self._adjList, left, right)
    
    def contract(self):
        """ Contract entire tree  """
        if isinstance(self, Tree):
            global env
            env = QuESTFunc.createQuESTEnv()

        if self.isLeaf:
            self.resolve()
            return

        for child in self.child:
            child.contract()

        print("Left", self.left.vertex.ID, list(self.left.edges))
        print("Right", self.right.vertex.ID, list(self.right.edges))

        left = self.left.tensorNode
        right = self.right.tensorNode
        contractionEdges = self.compute_contraction_edges(self.left, self.right)
        # My vertex becomes child's merged vertex
        self._tensor = TensorNode.contract(left, right, contractionEdges)

        if self.tier == 0:
            return
        
        self.root.contracted_nodes(self.vertex.ID, self.right.vertex.ID)
        self.vertex._contracted += [self.left.vertex.ID]
        self.child = []

        print("Hi, I'm ", self.vertex.ID, list(self.edges), "I ate ", self.vertex.contracted)


    def tree_form(self, prop):
        """ Return printout tree displaying property """
        lines, _, _, _ = self.display_aux(prop)
        strOut = "\n".join(lines)
        return strOut

    def display_aux(self, prop):
        """Returns list of strings, width, height, and horizontal coordinate of the root."""
        asStr = str(list(getattr(self, prop)))

        # No child.
        if self.nChild == 0:
            width = len(asStr)
            height = 1
            middle = width // 2
            return [asStr], width, height, middle

        # Two children.
        left, widthL, heightL, middleL = self.left.display_aux(prop)
        right, widthR, heightR, middleR = self.right.display_aux(prop)
        sepL, sepR = widthL - middleL, widthR - middleR
        strLen = len(asStr)
        firstLine = (middleL + 1) * ' ' + (sepL - 1) * '_' + asStr + middleR * '_' + (sepR) * ' '
        secondLine = middleL * ' ' + '/' + (sepL - 1 + strLen + middleR) * ' ' + '\\' + (sepR - 1) * ' '
        if heightL < heightR:
            left += [widthL * ' '] * (heightR - heightL)
        else:
            right += [widthR * ' '] * (heightL - heightR)
        lines = [firstLine, secondLine] + [a + strLen * ' ' + b for a, b in zip(left, right)]
        return lines, widthL + widthR + strLen, max(heightL, heightR) + 2, widthL + strLen // 2

    def split_graph(self):
        """ Recursively split the graph and build the resulting binary tree """
        if self.nVerts < 2:
            return
        graph = self.to_metis()
        cutL = np.asarray(metis.part_graph(graph, nparts=2)[1])
        if 0 < sum(cutL) < len(cutL):
            pass
        else: # Handle METIS not splitting small graphs by taking least-connected value
            leastCon = np.argmin(map(len, self.adjList.edges))
            cutL = [0 if node != leastCon else 1 for node, _ in enumerate(graph)]
        cutR = np.logical_not(cutL)
        childL, childR = Node(self, cutL), Node(self, cutR)
        childL.split_graph()
        childR.split_graph()

    @staticmethod
    def flat_weight(vertexA, vertexB, edge):
        """ Flat weighting system """
        return 1

    @staticmethod
    def leftness_weight(vertexA, vertexB, edge):
        """ Favour cuts in a timelike fashion and favour cuts to the left """
        return vertexA.age

    @staticmethod
    def spacelike_weight(vertexA, vertexB, edge):
        """ Favour space-like cuts """

    def calc_weight(self, vertexA, vertexB, edge, method):
        """ Return calculated metis weight """
        weightMethod = (self.flat_weight, self.leftness_weight, self.spacelike_weight)
        return weightMethod[method](vertexA, vertexB, edge)

    def add_weights(self):
        """ Add weights necessary for METIS partitioning """
        for edge in self.adjList.edges:
            edgeA, edgeB = edge
            nodeA, nodeB = self.adjList.node[edgeA]["node"], self.adjList.node[edgeB]["node"]
            self.adjList[edgeA][edgeB]["weight"] = self.calc_weight(nodeA, nodeB, edge, 1)
        return self.adjList

    def to_metis(self):
        """ Convert tree's graph into metis structure """
        return metis.networkx_to_metis(self.add_weights())


class Node(Tree):
    """ Tree node class """
    def __init__(self, parent, cut):
        Tree.__init__(self, graph=[])
        self.parent = parent
        parent += self
        self.root = parent.root
        self._tier = self.parent.tier + 1
        self.child = []
        self._adjList = networkx.subgraph(parent.adjList,
                                          (node for i, node in enumerate(parent.adjList) if cut[i]))

env = None
