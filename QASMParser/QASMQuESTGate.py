from .QASMParser import *
from copy import copy

class QuESTLibGate(Gate):
    def __init__(self, name, cargs, qargs, argOrder, internalName, unitary = False):
        self.type_ = "Gate"
        self.name = name
        self.unitary = unitary
        self._cargs = cargs
        self._qargs = qargs
        self.internalName = internalName
        self.argOrder = argOrder
        Gate.internalGates[self.name] = self
    
    def reorder_args(self, qargs, cargs):
        preCode = []
        args = []
        outCargs = []
        for expect in self.argOrder:
            if expect == "nextQureg":
                args.append('qreg')
            elif expect == "nextIndex":
                qarg = qargs.pop(0)
                args.append(Operation.resolve_arg(self,qarg))
            elif expect[0:6] == "nIndex":
                nArgs = expect[6:]
                if not nArgs.isdecimal() :
                    if nArgs != "*":
                        raise TypeError('Expected number of indices')
                    else:
                        nArgs = len(qargs)
                else:
                    nArgs = int(nArgs)
                tmp = []
                for i in range(nArgs):
                    qarg = qargs.pop(0)
                    tmp.append(Operation.resolve_arg(self,qarg))
                args.append(tmp)
        nTemp = 0
        for arg in self.argOrder:
            if arg == "nextQureg" or arg == "nextIndex" or arg == "index":
                outCargs += [args.pop(0)]
            elif arg[0:6] == "nIndex":
                nTemp+=1
                tempVar   = "tmp"+str(nTemp)
                indices = args.pop(0)
                nIndices  = len(indices)
                preCode  += [Let( (f'{tempVar}[{nIndices}]', "const int") , (indices, None) )]
                outCargs += [f"{tempVar}",f"{nIndices}"]
            elif arg == "nextCarg":
                outCargs += [cargs.pop(0)]
            elif arg == "cargs":
                outCargs += cargs
                cargs = []
            elif arg == "complexCarg":
                nTemp += 1
                tempVar = "tmp"+str(nTemp)
                tempArg = [cargs.pop(0), cargs.pop(0)]
                preCode += [Let(tempVar, tempArg, "Complex")]
                outCargs += [tempVar]
            elif arg == "complexMatrix2Carg":
                nTemp += 1
                tempVar = "tmp"+str(nTemp)
                tempArg = [cargs.pop(0), cargs.pop(0), cargs.pop(0), cargs.pop(0)]
                preString += [f"ComplexMatrix2 {tempVar} = {{{','.join(tempArg)}}};"]
                outCargs += [tempVar]
            elif arg == "not":
                nTemp += 1
                tempVar = "not"
                preCode += [Let( (tempVar, "ComplexMatrix2") , (None, None) ),
                            Let( (tempVar+".r0c0", None ), (["0.", "0."], "Complex") ),
                            Let( (tempVar+".r1c0", None ), (["1.", "0."], "Complex") ),
                            Let( (tempVar+".r0c1", None ), (["1.", "0."], "Complex") ),
                            Let( (tempVar+".r1c1", None ), (["0.", "0."], "Complex") ),
                            ]
                outCargs += [tempVar]
        return preCode, outCargs

# QuESTLibGate(name = "x",   cargs = None, qargs = "a", argOrder = ("nextQureg", "nextIndex"), internalName = "pauliX", unitary = True)
QuESTLibGate(name = "CX",  cargs = None, qargs = "a", argOrder = ("nextQureg", "nextIndex", "nextIndex"), internalName = "controlledNot", unitary = True)
# QuESTLibGate(name = "ccx", cargs = None, qargs = "a,b,c", argOrder = ("nextQureg", "nIndex2", "nextIndex", "not"), internalName = "multiControlledUnitary", unitary = True)
QuESTLibGate(name = "rotateX", cargs = "phi", qargs = "a", argOrder = ("nextQureg", "nextIndex", "cargs"), internalName = "rotateX", unitary = True)
QuESTLibGate(name = "rotateY", cargs = "theta", qargs = "a", argOrder = ("nextQureg", "nextIndex", "cargs"), internalName = "rotateY", unitary = True)
QuESTLibGate(name = "rotateZ", cargs = "lambda", qargs = "a", argOrder = ("nextQureg", "nextIndex", "cargs"), internalName = "rotateZ", unitary = True)
