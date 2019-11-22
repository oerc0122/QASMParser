"""
Module for building adjacency list and firing that through METIS for partitioning
"""
import metis
import numpy as np
import networkx

class Tree:
    """ Class defining tree head """

    def __init__(self, graph=None):
        self._tier = 0
        self._nTier = 0
        self._allNodes = [self]
        self._ID = 0
        self.child = []
        self._codeGraph = graph
        # Default to None if not in current scope
        self._tensor = None
        self._root = self

    def __add__(self, other):
        if self.nChild < 2:
            self.child.append(other)
            return self
        raise IndexError("Binary tree cannot have more than 2 children")


    root = property(lambda self: self._root)

    codeGraph = property(lambda self: self._codeGraph)

    tensorNode = property(lambda self: self._tensor)
    tensor = property(lambda self: self._tensor.tensor)
    indices = property(lambda self: self._tensor.indices)

    tier = property(lambda self: self._tier)
    nTier = property(lambda self: self.root._nTier)

    isLeaf = property(lambda self: not self.child)

    left = property(lambda self: self.child[0])
    right = property(lambda self: self.child[1])
    nChild = property(lambda self: len(self.child))
    allNodes = property(lambda self: self.root._allNodes)
    ID = property(lambda self: self._ID)

    edges = property(lambda self: (edge for edge in self.tensorNode.edges))
    validEdges = property(lambda self: (edge for edge in self.codeGraph.edges
                                        if not any("end" in str(node) for node in edge)))
    nEdge = property(lambda self: len(self.codeGraph))
    nEdges = property(lambda self: len(self.fullEdges))
    vertices = property(lambda self: [self.codeGraph.nodes[vertex]["node"] for vertex in self.codeGraph.nodes])
    nVerts = property(lambda self: len(self._codeGraph))
    vertIDs = property(lambda self: [vertex.ID for vertex in self.vertices])

    @property
    def nodeID(self):
        """ Get ID of node for leaves """
        for node in self.codeGraph.nodes:
            a = node
        return a

    @property
    def vertex(self):
        """ Vertex getter """
        return self.codeGraph.nodes[self.nodeID]["node"]

    @property
    def fullNode(self):
        """ Get full graph's vertex """
        return self.root.codeGraph.nodes[self.nodeID]

    @property
    def fullEdges(self):
        """ Get full graph's vertex """
        return self.root.codeGraph.edges(self.nodeID)

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

    def by_tier(self, tiers=None):
        """ Return nodes in tree-like order """
        if tiers is None:
            tiers = range(self.tier, self.nTier)
        elif isinstance(tiers, int):
            tiers = [tiers]

        for tier in tiers:
            yield from (node for node in self.allNodes if node.tier == tier)

    def least_connect(self):
        """ Return vertices with the fewest edges first """
        for element in reversed(sorted(self.codeGraph, key=lambda elem: elem.nEdge)):
            yield element

    def most_connect(self):
        """ Return vertices with the fewest edges first """
        for element in sorted(self.codeGraph, key=lambda elem: elem.nEdge):
            yield element

    def contract_order(self, order=0):
        """ Generator returning leaves in expected resolution order """
        contractOrder = (self.dfs, self.least_connect, self.most_connect)
        return contractOrder[order]()

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
        firstLine = (middleL + 1) * " " + (sepL - 1) * "_" + asStr + middleR * "_" + (sepR) * " "
        secondLine = middleL * " " + "/" + (sepL - 1 + strLen + middleR) * " " + "\\" + (sepR - 1) * " "
        if heightL < heightR:
            left += [widthL * " "] * (heightR - heightL)
        else:
            right += [widthR * " "] * (heightL - heightR)
        lines = [firstLine, secondLine] + [a + strLen * " " + b for a, b in zip(left, right)]
        return lines, widthL + widthR + strLen, max(heightL, heightR) + 2, widthL + strLen // 2

    def split_graph(self, method="stoer-wagner"):
        """ Recursively split the graph and build the resulting binary tree """
        if method == "stoer-wagner":
            self.split_graph_stoer_wagner()
        elif method == "metis":
            self.split_graph_metis()
        elif method == "girvan-newman":
            self.split_graph_girvan_newman()
        else:
            raise ValueError("Unrecognised method {}".format(method))

    def split_graph_girvan_newman(self):
        """ Split the graph using Girvan-Newaman and build the resulting binary tree """
        graph = self.add_weights()
        parents = [self]
        for tier in networkx.algorithms.community.centrality.girvan_newman(graph):
            children = [None] * len(tier)
            for nodeID, community in enumerate(tier):
                for parent in parents:
                    if community.issubset(parent.codeGraph): # Now we know "Who's the daddy?"
                        children[nodeID] = Node(parent, community)
            # And we become daddy
            parents = children

    def split_graph_stoer_wagner(self):
        """ Recursively split the graph using Stoer-Wagner and build the resulting binary tree """
        if self.nVerts < 2:
            return
        graph = self.add_weights()
        _, (cutL, cutR) = networkx.algorithms.connectivity.stoerwagner.stoer_wagner(graph)
        childL, childR = Node(self, cutL), Node(self, cutR)
        childL.split_graph_stoer_wagner()
        childR.split_graph_stoer_wagner()

    def split_graph_metis(self):
        """ Recursively split the graph and build the resulting binary tree """
        if self.nVerts < 2:
            return
        graph = self.to_metis()
        cut = metis.part_graph(graph, nparts=2)[1]
        if 0 < sum(cut) < len(cut):
            pass
        else: # Handle METIS not splitting small graphs by taking least-connected value
            leastCon = np.argmin(map(len, self.codeGraph.edges))
            cut = [0 if node != leastCon else 1 for node, _ in enumerate(graph)]
        cutL = (node for i, node in enumerate(self.codeGraph) if cut[i])
        cutR = (node for i, node in enumerate(self.codeGraph) if not cut[i])
        childL, childR = Node(self, cutL), Node(self, cutR)
        childL.split_graph_metis()
        childR.split_graph_metis()

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
        for edge in self.validEdges:
            edgeA, edgeB = edge
            nodeA, nodeB = self.codeGraph.nodes[edgeA]["node"], self.codeGraph.nodes[edgeB]["node"]
            self.codeGraph[edgeA][edgeB]["weight"] = self.calc_weight(nodeA, nodeB, edge, 0)
        return self.codeGraph

    def to_metis(self):
        """ Convert tree's graph into metis structure """
        return metis.networkx_to_metis(self.add_weights())


class Node(Tree):
    """ Tree node class """
    def __init__(self, parent, cut):
        Tree.__init__(self, graph=[])
        self.parent = parent
        self._root = parent.root
        parent += self
        self._ID = len(self.allNodes)
        self.root._allNodes.append(self)
        self._tier = self.parent.tier + 1

        if self.tier > self.nTier:
            self.root._nTier = self.tier
        self.child = []
        self._codeGraph = networkx.subgraph(parent.codeGraph, cut)

