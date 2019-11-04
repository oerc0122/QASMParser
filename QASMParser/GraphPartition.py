"""
Module for building adjacency list and firing that through METIS for partitioning
"""
import sys
import ctypes
from collections import defaultdict
import metis
import numpy as np
import networkx
#import pygraphviz as pg

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
    adjList = obj.adjList.adjList
    ### Drawing
    #edgeList = [tuple([edge, i]) for i, vertex in enumerate(adj.adjList) for edge in vertex.edges]
    #graph = pg.AGraph()
    #for edge in edgeList:
    #    graph.add_edge(*edge)
    #graph.draw('graph.png', prog='neato')
    ### EndDraw

    tree = Tree(adjList)
    tree.split_graph()
    print(tree.tree_form("vertIDs"))
    tree.contract()
    print(tree.tensor.qureg)


class Vertex():
    """ Class defining a single tensor node vertex """
    def __init__(self, ID, qubitID, age, graph, operation=None):
        self._ID = ID
        self._qubitID = qubitID
        self._age = age
        self._edges = []
        self._indices = []
        self._op = operation
        self._contracted = []
        self._parent = graph
        self.lastQubit = True

    ID = property(lambda self: self._ID)
    qubitID = property(lambda self: self._qubitID)
    age = property(lambda self: self._age)
    contracted = property(lambda self: self._contracted)
    edgeIn = property(lambda self: self._edges[1])
    edgeOut = property(lambda self: self._edges[0])
    edges = property(lambda self: networkx.edges(self.parent, self))
    nEdges = property(lambda self: len(self._edges))
    indices = property(lambda self: self._indices)
    op = property(lambda self: self._op)
    graph = property(lambda self: self._parent)
        
    def update(self, remap):
        """ Update indices to new values post contraction """
        for i, index in enumerate(self.indices):
            self._indices[i] = remap.get(index, index)

        for i, index in enumerate(self.edges):
            self._edges[i] = remap.get(index, index)

    def contract(self, right):
        """ Combine two vertices """

        left = self
        print("Contracting", left.ID, right.ID)
        contractionEdges = [[], []]
        freeIndices = [[], []]

        for localQubit, (targetVertex, targetQubit) in enumerate(left.indices):
            if targetVertex == right.ID:
                contractionEdges[0].append(localQubit)
                contractionEdges[1].append(targetQubit)

        freeIndices[0] = [qubit for qubit in range(left.nEdges) if qubit not in contractionEdges[0]]
        freeIndices[1] = [qubit for qubit in range(right.nEdges) if qubit not in contractionEdges[1]]

        remap = {right.ID: left.ID}
        notDropped = 0
        for ind, _ in enumerate(left.indices):
            edge = (left.ID, ind)
            if ind in contractionEdges[0]:
                remap[edge] = None
            else:
                if notDropped != ind:
                    remap[edge] = left.ID, notDropped
                notDropped += 1

        for ind, _ in enumerate(right.indices):
            edge = (right.ID, ind)
            if ind in contractionEdges[1]:
                remap[edge] = None
            else:
                remap[edge] = left.ID, notDropped
                notDropped += 1

        left._edges = ([edge for edge in left.edges if edge != right.ID] +
                       [edge for edge in right.edges if edge != left.ID])
        left._indices = ([index for i, index in enumerate(left.indices) if i not in contractionEdges[0]] +
                         [index for i, index in enumerate(right.indices) if i not in contractionEdges[1]])
        left._contracted += [right.ID] + right.contracted

        return contractionEdges, freeIndices, remap

class AdjList():
    """ Build directed graph using NetworkX """
    def __init__(self, size):
        self._adjList = networkx.DiGraph()
        for i in range(size):
            self._adjList.add_node(i, node=Vertex(ID=i, qubitID=i, age=1, graph=self.adjList))
        self._lastUpdated = [node for node in self.adjList]
        self._nGate = [1]*size

    verts = property(lambda self: [vertex for vertex in self.adjList])
    adjList = property(lambda self: self._adjList)
    nVerts = property(lambda self: len(self.adjList))
    edges = property(lambda self: self.adjList.edges)

    def process(self, obj, **kwargs):
        """ Build graph from code """
        for qubit in obj.qubitsInvolved:
            prev = self._lastUpdated[qubit]
            self._nGate[qubit] += 1
            # Add new state as vertex
            self.adjList.node[prev]["node"].lastQubit = False
            current = self.nVerts
            node = Vertex(ID=self.nVerts, qubitID=qubit, age=self._nGate[qubit], graph=self.adjList, operation=kwargs['lineObj'])
            self._adjList.add_node(current, node=node, weight=1)
            # Link last updated vertex to current
            self._adjList.add_edge(prev, current, weight=1)
            self._lastUpdated[qubit] = current
            if qubit != min(obj.qubitsInvolved): # Skip if initial qubit (nothing to link to)
                self._adjList.add_edge(current, lastVertex, weight=1)
                self._adjList.add_edge(lastVertex, current, weight=1)
            # Link to previous qubit in operation
            lastVertex = current

class Tree:
    """ Class defining tree head """

    def __init__(self, graph=None):
        self._tier = 0
        self.child = []
        self._adjList = graph
        # Default to None if not in current scope
        self.remap = defaultdict(lambda: None, {i:i for i, _ in enumerate(graph)})
        self.unmap = self.remap
        self.tensor = None
        self.tree = self

    def __add__(self, other):
        if self.nChild < 2:
            self.child.append(other)
            return self
        raise IndexError('Binary tree cannot have more than 2 children')

    tier = property(lambda self: self._tier)
    isLeaf = property(lambda self: not self.child)
    left = property(lambda self: self.child[0])
    right = property(lambda self: self.child[1])
    nChild = property(lambda self: len(self.child))
    nVerts = property(lambda self: len(self._adjList))
    vertIDs = property(lambda self: [vertex for vertex in self.adjList])
    vertices = property(lambda self: (vertex.node for vertex in self.adjList))
    nEdge = property(lambda self: len(self.adjList))
    adjList = property(lambda self: self._adjList)
    neighbours = property(lambda self:
                          set(edge for vertex in self.vertices for edge in vertex.edges if edge is not None))


    def to_local(self, edge):
        """ find local index of vertex """
        return self.remap[edge]

    def to_global(self, edge):
        """ Find global index of vertex """
        return self.unmap[edge]

    @property
    def adjListMap(self):
        """ Return the adjacency list mapped to local context, removing adjacencies outside local space """
        out = [tuple(self.remap[edge] for edge in vertex.edges if edge in self.remap) for vertex in self.adjList]
        return np.asarray(out)

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
        print(self.vertex)
        quit()
        nVirtQubit = vertex.fullVertex.edges() - 1
        
        print(f"Hi,I'm {vertex.ID}, I have {vertex.nEdges} edges and 1 physical qubit")
        self.tensor = TNFunc.createTensor(1, nVirtQubit, env)
        # Entangle first virtual with physical qubit

        # If we're initialise -- createTensor => |0>
        if vertex.op is None:
            return

        TNAdd.TN_controlledGateTargetHalf(QuESTFunc.controlledNot, self.tensor, 1, 0)

        if vertex.op.name == "CX":
            gate = QuESTFunc.controlledNot
            args = [0, 2]
        elif vertex.op.name == "U":
            gate = QuESTFunc.hadamard
            args = [0]

        for vertex in self.vertices:
            if gate.control:
                print(vertex.qubitID, vertex.op.qargs[gate.control])
                if vertex.qubitID == vertex.op.qargs[gate.control-1][1]:
                    print("Control")
                    # physical qubit is the control, virtual qubit is the target
                    print(args)
                    TNAdd.TN_controlledGateControlHalf(gate, self.tensor, *args)
                else:
                    print("Target")
                    # virtual qubit is the control, physical qubit is the target
                    print(*args[::-1])
                    TNAdd.TN_controlledGateTargetHalf(gate, self.tensor, *args[::-1])
            else:
                TNAdd.TN_singleQubitGate(gate, self.tensor, *args)

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

        print(self.left.vertex.ID, self.left.vertex.indices)
        print(self.right.vertex.ID, self.right.vertex.indices)
        contractionEdges, freeIndices, remap = self.left.vertex.contract(self.right.vertex)
        *contPass, = map(lambda pyarr: (ctypes.c_int * len(pyarr))(*pyarr), contractionEdges)
        *freePass, = map(lambda pyarr: (ctypes.c_int * len(pyarr))(*pyarr), freeIndices)

        print("Left")
        print(self.left.tensor.qureg)
        print("Right")
        print(self.right.tensor.qureg)

        print("contractionEdges", contractionEdges, "\n free", freeIndices, "\nremap", remap)

        self.tensor = TNFunc.contractIndices(self.left.tensor, self.right.tensor,
                                             contPass[0], contPass[1], ctypes.c_int(len(contractionEdges[0])),
                                             freePass[0], ctypes.c_int(len(freeIndices[0])),
                                             freePass[1], ctypes.c_int(len(freeIndices[1])), env)

        print("Output qureg")
        print(self.tensor.qureg)
        # My vertex becomes child's merged vertex
        self._adjList = self.left.adjList
        verts = list(self.tree.vertices)
        neighbours = [verts[neighbour] for neighbour in self.neighbours]
        print("Neigh", self.neighbours)
        print("Hi, I'm ", self.vertex.ID, self.vertex.indices, "I ate ", self.vertex.contracted)
        for neighbour in neighbours:
            print("Howdy", neighbour.ID, neighbour.indices)
            neighbour.update(remap)
            print("Doody", neighbour.ID, neighbour.indices)

        if self.tier == 0:
            return
        # Remove global reference to child
        self.tree._adjList[self.right.vertex.ID] = None
        self.child = []

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
        self.tree = parent.tree
        self._tier = self.parent.tier + 1
        self.child = []
        self._adjList = networkx.subgraph(parent.adjList,
                                          (node for i, node in enumerate(parent.adjList) if cut[i]))

    @property
    def vertex(self):
        """ Vertex getter """
        for node in self.adjList.nodes:
            a = node
        vertex = self.adjList.node[a]["node"]
        return vertex
env = None
