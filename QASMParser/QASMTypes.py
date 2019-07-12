from .QASMErrors import *
from .QASMTokens import *
from .FileHandle import QASMFile, QASMBlock, NullBlock
import re
import copy

isInt  = re.compile("[+-]?(\d+)(?:[eE][+-]?\d+)?")
isReal = re.compile("[+-]?(\d*\.\d+|\d+\.\d*)(?:[eE][+-]?\d+)?")

# Base types
class Operation:
    """ Base class for callable function-like objects """

    def __init__(self, parent, qargs = None, pargs = None, gargs = None, spargs = None):
        self.parent = parent
        self._loops = None
        self._qargs = qargs
        self._pargs = pargs
        self._spargs = spargs
        self._gargs = gargs

    def add_loop(self, index, start, end):
        """ Wrap self in a loop """

        if self._loops:
            self._loops = NestLoop(self._loops, index, start, end)
        else:
            self.innermost = NestLoop(copy.copy(self), index, start, end)
            self._loops = self.innermost

    def finalise_loops(self):
        """ Dealias references of self if self has changed to avoid infinite loops """

        if self._loops:
            self.innermost._code = [copy.copy(self)]
            self.innermost._code[0]._loops = []
        else:
            pass

    def handle_loops(self, pargs, slice = None):
        """ Handle loop rules according to modified REQASM rules """

        baseStart, baseEnd = pargs[0][1]
        loopable = baseStart != baseEnd

        if loopable:
            loopVar = pargs[0][0].name + "_loop"
            self.add_loop(loopVar, baseStart, baseEnd)
        else:
            loopVar = False

        if loopVar:
            for parg in pargs:
                pargStart, pargEnd = parg[1]
                if pargStart - baseStart:
                    parg[1] = loopVar + str(pargStart - baseStart)
                else:
                    parg[1] = loopVar
        else:
            for parg in pargs:
                parg[1] = parg[1][0]

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class Referencable:
    """ Base class for any element which will exist within scope """

    def __init__(self, parent):
        self.type_ = type(self).__name__
        self.parent = parent

class CodeBlock:
    """  Base class for an object which creates its own scope and contains code """

    def __init__(self, block, parent, copyObjs = True, copyFuncs = True):
        self._code = []
        self._qargs= []
        self._pargs= []
        self._spargs = []
        self._gargs = []
        if copyObjs:
            self._objs = copy.copy(parent._objs)
        else:
            self._objs = {}
        self.currentFile = block
        self.instructions = self.currentFile.read_instruction()
        self._error = self.currentFile._error
        QASMType = self.currentFile.QASMType

    def _dump_line(self):
        return self.currentFile.nLine

    def _resolve(self, var, type_, index = ""):
        """
        Resolve an argument and return its corresponding value or location based on current scope.
        """

        # If we've accidentally passed the object through (fix this more thoroughly)
        if isinstance(var, (Constant)): var = getattr(var, 'name', var)

        if type_ in ["ClassicalRegister","QuantumRegister"]:
            if self._check_def(var, create=False, type_ = type_):
                var = self._objs[var]
            elif self._check_def(var, create=False, type_ = "Alias"):
                var = self._objs[var]

            else:
                self._is_def(var, create=False, type_ = type_)

            if index or index is None: # If index or implicit loop

                index = self.parse_range(index, var)

                return [var, index]

            elif isinstance(var,Argument):

                return [var, var.name]


        elif type_ == "Alias":

            self._is_def(var, create=False, type_ = type_)
            var = self._objs[var]

            index = self.parse_range(index, var)
            return [var, index]

        elif type_ == "Constant":
            if isinstance(var, ParseResults):
                var = var.pop()

            if var is None:
                return None
            elif isinstance(var, (list, tuple)):
                return [ self._resolve(elem, type_ = "Constant") for elem in var ]
            elif isinstance(var, int) or isinstance(var, float):
                return var
            elif isinstance(var,str) and re.fullmatch(isInt, var):
                var = float(var)
                return int(var)
            elif isinstance(var,str) and re.fullmatch(isReal, var):
                var = float(var)
                return var
            elif issubclass(type(var), MathOp):
                return self.parse_maths(var)
            else:
                self._is_def(var, create=False, type_ = type_)
                return self._objs[var] #.name

        elif type_ == "Maths":

            if isinstance(var, list):
                if len(var) == 1:
                    var = var.pop()
                elif len(var) == 0:
                    return None
                else:
                    raise NotImplementedError("cannot handle list args")

            if var is None:
                return None
            elif isinstance(var, int) or isinstance(var, float):
                return var
            elif isinstance(var,str) and re.fullmatch(isInt, var):
                return int(var)
            elif isinstance(var,str) and re.fullmatch(isReal, var):
                return float(var)
            elif issubclass(type(var), MathOp):
                return self.parse_maths(var)
            elif isinstance(var, ParseResults):
                if var.get("var", None) is not None:
                    return self._resolve(var.get("var"), type_="Maths", index = var.get("ref"))
                elif var.get("start") or var.get("end"):
                    return self.parse_range(var)
            elif isinstance(var, MathsBlock):
                return var.maths
            else:
                self._is_def(var, create=False, type_ = None)
                var = self._objs[var]

                if isinstance(var,Argument):

                    return [var, var.name]

                elif isinstance(var,Constant):

                    return var.name

                elif isinstance(var, ClassicalRegister ):

                    if index or index is None: # If index or implicit loop
                        index = self.parse_range(index, var)

                        return [var, index]
                    else:
                        return [var, None]
                elif isinstance(var, QuantumRegister):
                    self._error("Cannot use quantum register {} in maths expression".format(var.name))

                else:
                    self._error("Undetermined type {} in maths parsing".format(type(var).__name__))

        elif type_ == "Gate":
            self._is_def(var, create=False, type_ = type_)
            return self._objs[var]

        else:
            self._error("Unrecognised type {} in _resolve".format(type_))

    def _resolve_maths(self, elem, additional_vars = {}, topLevel = True, tempDict = None):
        """
        Perform the set of maths operations to return the final value or an error if it cannot be evaluated
        """

        # Ops which should be unchanged
        identOp = ["-","+","*","/","%","<","<=","==","!=",">=",">","!","sin","cos","tan","sqrt","abs","and","or"]
        # Ops which require simple substitution
        subOp = {"xor":"!=","mod":"%","^":"**","div":"//",
                 "arccos":"acos","arcsin":"asin","arctan":"atan"
                 }

        outStr = ""

        if tempDict is None:
            tempDict = copy.copy(self._objs)
            for key, val in additional_vars.items():
                tempDict[key] = val

        recurse = lambda elem: self._resolve_maths(elem, additional_vars, False, tempDict)

        if isinstance(elem, MathsBlock):
            for point in elem.maths:
                outStr += recurse(point)
        elif isinstance(elem, int) or isinstance(elem, float):
            outStr += str(elem)
        elif isinstance(elem, Constant):
            if not hasattr(elem, "sparg"):
                outStr += recurse(elem.val)
            else:
                outStr += elem.name
        elif isinstance(elem, str) and elem in tempDict:
            outStr += recurse(tempDict[elem])
        elif isinstance(elem, Binary):
            for op, operand in elem.args:
                if op == "nop":
                    operand = recurse(operand)
                    outStr += f"{operand}"
                elif op == "in":
                    if len(operand) == 2:
                        outStr = f"({outStr} > {operand[0]} && {outStr} < {operand[1]})"
                    else:
                        raise OSError
                elif op in identOp:
                    operand = recurse(operand)
                    outStr += f" {op} {operand}"
                elif op in subOp:
                    operand = recurse(operand)
                    outStr += f" {subOp[op]} {operand}"
                else:
                    raise NotImplementedError(op)
        elif isinstance(elem, Function):
            elem = elem.op
            args = []
            for arg in elem.args:
                args.append(self._resolve_maths(parent, arg),additional_vars, False)
            outStr += f"{elem}({', '.join(args)})"
        elif isinstance(elem, ParseResults):
            var = self._resolve(elem, type_="Constant")
            outStr += self._resolve_maths(var,additional_vars, False)
        elif isinstance(elem, list) and isinstance(elem[0], ClassicalRegister):
            self._error("Cannot resolve ClassicalRegister {} to constant value".format(elem[0].name))
        else:
            raise NotImplementedError("Cannot parse {} {} in _resolve_maths".format(type(elem).__name__, elem))

        if not outStr:
            return "0"

        if topLevel:
            try:
                return eval(str(outStr))
            except:
                self._error("Error parsing maths string:\n '{}'\n".format(outStr) )
        else:
            return outStr

    def _check_def(self, name, create:bool, type_ = None):
        """
        Check if object exists in local scope
        Create == True: returns False if an object already exists
        Create == False: returns False if object does not exist or is not of matching type
        """

        if name not in self._objs: return create
        elif type_ is not None and self._objs[name].type_ is not type_: return False
        else: return not create

    def _is_def(self, name, create:bool, type_ = None):
        """
        Check if object exists in local scope
        Create == True: returns an error if an object already exists
        Create == False: returns an error if object does not exist or is not of matching type
        """

        if create: # Check for duplicate naming
            if name in self._objs: self._error(dupWarning.format(Name=name, Type=self._objs[name].type_))

        else: # Check exists and type is right
            if name not in self._objs:
                self._error(existWarning.format(Type=type_, Name=name))
            elif type_ is None: pass
            elif self._objs[name].type_ is not type_:
                self._error(wrongTypeWarning.format(type_,self._objs[name].type_))

    def _check_bounds(self,interval, arg = None):
        """ Check for register over-run and raise error if present """

        if arg is None: return
        if not isinstance(arg.start, int) or not isinstance(arg.size, int) : return

        if isinstance(interval[0],int) and interval[0] < arg.min:
            self._error(indexWarning.format(Req=interval[0], Var = arg.name, Min = arg.min, Max = arg.max))
        elif isinstance(interval[1],int) and interval[1] > arg.max:
            self._error(indexWarning.format(Req=interval[1], Var = arg.name, Min = arg.min, Max = arg.max))

    def comment(self, comment):
        """ Create a comment in scope of self and append it to the code """
        self._code += [Comment(self, comment)]

    def new_variable(self, argName, size, classical):
        """ Create a new register in scope of self and append it to the code """

        self._is_def(argName, create=True)

        if classical:
            variable = ClassicalRegister(self, argName, size)
            self._objs[argName] = variable
        else:
            variable = QuantumRegister(self, argName, size)
            self._objs[argName] = variable

        self._code += [variable]

    def new_alias(self, argName, size):
        """ Create a new alias in scope of self """

        self._is_def(argName, create=True)
        alias = Alias(self, argName, size)
        self._objs[argName] = alias
        self._code += [alias]

    def alias(self, aliasName, argIndex, referee, refIndex):
        """
        If an alias called aliasName exists: assign values to this alias
        If it does not exist:  Create it and if values assign it
        """

        referee, refInter = self._resolve(referee, type_="QuantumRegister", index = refIndex)
        refInter = refInter[0], refInter[1]
        refSize = self._resolve_maths(refInter[1] - refInter[0] + 1)

        if self._check_def(aliasName, create=True, type_ = "Alias"):
            self.new_alias(aliasName, refSize)

        alias, aliasInter = self._resolve(aliasName, type_="Alias", index=argIndex)
        aliasSize = 1 + aliasInter[1] - aliasInter[0]
        if aliasSize != refSize:
            self._error(aliasIndexWarning.format(aliasName, aliasSize, refSize))

        self._code += [SetAlias( self, (alias, aliasInter),  (referee, refInter) )]

    def gate(self, gateName, block,
             pargs = None, qargs = None, spargs = None, gargs = None, byprod = None,
             recursive = False, unitary=False, type_ = "gate"):
        """
        Declare a new gate-like object in current scope and append it to the code
        """

        self._is_def(gateName, create=True)

        if type_ is "gate":
            gate = Gate(self, gateName, block, pargs, qargs, recursive = recursive, unitary = unitary)
        elif type_ is "opaque":
            gate = Opaque(self, gateName, pargs, qargs, spargs, byprod = byprod, recursive = recursive, unitary = unitary)
        elif type_ is "circuit":
            gate = Circuit(self, gateName, block, pargs, qargs, spargs, byprod = byprod, recursive = recursive, unitary = unitary)
        elif type_ is "procedure":
            gate = Procedure(self, gateName, block, pargs, qargs, spargs, gargs, byprod = byprod, recursive = recursive, unitary = unitary)
        else:
            self._error(gateWarning.format(type_))

        self._objs[gate.name] = gate
        self._code += [gate]

    def let(self, var, val):

        varName, varType = var
        value, valType = val

        val = (self._resolve( value, type_="Constant"), valType)
        if self._check_def(varName, create=True, type_="Constant"):
            letobj = Constant( self, var, val )
            self._objs[letobj.name] = letobj
        else:
            var = ( self._resolve( varName, type_="Constant").name, None )
            letobj = Constant( self, var, val )
            self._objs[letobj.name] = letobj

        self._code += [Let( self, letobj )]

    def call_gate(self, gateName, pargs, qargs, gargs=None, spargs=None, modifiers = []):
        self._is_def(gateName, create=False, type_ = "Gate")

        pargs = self.parse_args(pargs, type_ = "Constant")
        qargs = self.parse_args(qargs, type_ = "QuantumRegister")
        gargs = self.parse_args(gargs, type_ = "Gate")
        spargs = self.parse_args(spargs, type_ = "Constant")


        if "INV" in modifiers.asList():
            orig = self._resolve(gateName, type_ = "Gate")
            if self._check_def("inv_"+gateName, create=True, type_ = "Gate"):
                inv = copy.copy(orig)
                inv._code = orig.invert(pargs, qargs)
                inv.name = "inv_"+inv.name
                orig.inverse = inv
                self._code += [inv]
            gateName = "inv_"+gateName

        gate = CallGate(self, gateName, pargs, qargs, gargs, spargs)

        self._code += [gate]

    def measurement(self, qarg, qindex, parg, bindex):
        parg = self._resolve(parg, type_ = "ClassicalRegister", index=bindex)
        qarg = self._resolve(qarg, type_ = "QuantumRegister", index=qindex)

        measure = Measure( self, qarg, parg )

        self._code += [measure]

    def leave(self):
        if hasattr(self, "entry"):
            self.entry.exited()
        else:
            self._error("Cannot exit from a non-recursive gate")

    def reset(self, qarg, qindex):
        qarg = self._resolve(qarg, type_="QuantumRegister", index=qindex)
        reset = Reset( self, qarg )

        self._code += [reset]

    def output(self, parg, bindex):
        parg = self._resolve(parg, type_="ClassicalRegister", index=bindex)
        output = Output ( self, parg )

        self._code += [output]

    def loop(self, var, block, start, end):
        loop = Loop(self, block, var, start, end)
        self._code += [loop]

    def cycle(self, var):
        var = self._resolve(var, type_ = "Constant")
        if not var.loopVar:
            self._error("Cannot cycle non-loop vars")
        self._code += [Cycle( self, var )]

    def escape(self, var):
        var = self._resolve(var, type_ = "Constant")
        if not var.loopVar:
            self._error("Cannot escape non-loop vars")
        self._code += [Escape(self, var)]

    def new_while(self, cond, block):
        self._code += [While(self, cond, block)]

    def new_if(self, cond, block):
        self._code += [IfBlock(self, cond, block)]

    def cBlock(self, block):
        self._code += [CBlock(self,block)]

    def directive(self, directive, args = None, block = None):
        if directive in ["classicallang", "classlang"]:
            if type(self).__name__ is not "ProgFile" : self._error("Cannot set classical language outside of main code")
            if hasattr(self, "classLang") : self._error("Classical language already defined as {}".format(self.classLang))
            self.classLang = args.strip('"\'')
        elif directive == "classical":
            if block:
                self.cBlock(block)
            else:
                self.cBlock([args+";"])
        elif directive == "opaque":
            if not block: self._error("Cannot set opaque by inline directive")
            gate = args[0]
            if self._objs[gate]:
                target = self._objs[gate]
                target.cBlock(block)
            else:
                self._error("Cannot find opaque {}".format(gate))
        else:
            self._error("Unrecognised directive: {}".format(directive))

    def parse_line(self, token):
        non_code = ["alias","exit","comment","barrier","directive"]
        keyword = token.get("keyword", None)
        comment = token.get("comment", "")

        if self.currentFile.version < token["reqVersion"]:
            self._error(instructionWarning.format(keyword, self.currentFile.QASMType, self.currentFile.versionNumber))

        if keyword == "include":
            if hasattr(self,"include"):
                self.include(token["file"])
            else:
                self._error(includeNotMain)

        # Functions and gates
        elif keyword == "call":
            gateName = token["gate"]
            pargs = token.get("pargs", [])
            qargs = token.get("qargs", [])
            spargs = token.get("spargs", [])
            gargs = token.get("gargs", [])
            mods  = token.get("mods",  [])

            self.call_gate(gateName, pargs, qargs, gargs, spargs, modifiers = mods)
        elif keyword == "measure":
            qarg = token["qreg"]["var"]
            qindex = token["qreg"].get("ref", None)
            parg = token["creg"]["var"]
            bindex = token["creg"].get("ref", None)
            self.measurement(qarg, qindex, parg, bindex)
        elif keyword == "reset":
            qarg = token["qreg"]["var"]
            qindex = token["qreg"].get("ref", None)
            self.reset(qarg, qindex)
        elif keyword == "output":
            parg = token["value"]["var"]
            bindex = token["value"].get("ref", None)
            self.output(parg, bindex)
        elif keyword == "if":
            cond = self.parse_maths(token["cond"])
            block = QASMBlock(self.currentFile, token["block"])
            self.new_if(cond, block)

        # Directives
        elif keyword == "directive":
            directive = token["directive"]
            args = token.get("args", None)
            block = token.get("block", None)
            self.directive(directive, args, block)
        elif keyword == "barrier":
            pass

        # Variable-like routines
        elif keyword in ["cbit","creg"]: # Registers default to size 1 if blank
            argName = token["arg"]["var"]
            size = token["arg"].get("ref")
            if size is None: size = {"index": 1}
            else:
                size = token["arg"]["ref"]
            size =self.parse_range(size)
            self.new_variable(argName, size, True)
        elif keyword in ["qbit","qreg"]:

            argName = token["arg"]["var"]
            size = token["arg"].get("ref")
            if size is None: size = {"index": 1}
            else:
                size = token["arg"]["ref"]
            size =self.parse_range(size)
            self.new_variable(argName, size, False)
        elif keyword == "val":
            var = token["var"]
            val = token["val"]
            type_ = token["type"]
            self.let( (var, type_), (val, None) )
        elif keyword == "defAlias":
            name = token["alias"]["var"]
            index = self.parse_range(token["alias"]["ref"])
            self.new_alias(name, index)
        elif keyword == "alias":
            name = token["alias"]["var"]
            index = token["alias"].get("ref", None)
            qarg = token["target"]["var"]
            qindex = token["target"].get("ref", None)
            self.alias(name, index, qarg, qindex)

        # Loop routines
        elif keyword == "for":
            var = token["var"]
            start, end = self.parse_range(token["range"])
            block = QASMBlock(self.currentFile, token.get("block", None))
            self.loop(var, block, start, end) # Handle "<" ending one early
        elif keyword == "while":
            cond = self.parse_maths(token["cond"])
            block = QASMBlock(self.currentFile, token.get("block", None))
            self.new_while(block, cond)
        elif keyword == "next":
            var = token["loopVar"]
            self.cycle(var)
        elif keyword == "escape":
            var = token["loopVar"]
            self.escape(var)
        elif keyword == "exit":
            self.leave()

        elif keyword == "end":
            var = token["process"]
            self.end(var)

        # Gate declaration routines
        elif keyword == "gate":
            gateName = token["gateName"]
            pargs = token.get("pargs", [])
            qargs = token.get("qargs", [])
            unitary = token.get("unitary", False)
            recursive = token.get("recursive", False)
            block = QASMBlock(self.currentFile, token.get("block", None))
            self.gate(gateName, block, pargs, qargs, unitary = unitary, recursive = recursive)

        elif keyword == "circuit":
            gateName = token["gateName"]
            pargs = token.get("pargs", [])
            qargs = token.get("qargs", [])
            spargs = token.get("spargs", [])
            byprod = token.get("byprod", [])
            unitary = token.get("unitary", False)
            recursive = token.get("recursive", False)
            block = QASMBlock(self.currentFile, token.get("block", None))
            self.gate(gateName, block, pargs, qargs, spargs, byprod = byprod, unitary = unitary, recursive = recursive, type_ = "circuit")

        elif keyword == "opaque":

            gateInfo = {"block":None, "type_":"opaque"}
            gateInfo['gateName']  = token.get("name")
            gateInfo['pargs']     = token.get("pargs", [])
            gateInfo['qargs']     = token.get("qargs", [])
            gateInfo['spargs']    = token.get("spargs", [])
            gateInfo['byprod']   = token.get("byprod", [])
            gateInfo['unitary']   = token.get("unitary", False)
            gateInfo['recursive'] = token.get("recursive", False)
            self.gate(**gateInfo)


        # Whole line comment
        elif keyword is None:
            self.comment(comment)
        else:
            self._error(instructionWarning.format(keyword, self.currentFile.QASMType, self.currentFile.versionNumber))

        if len(self._code) == 0: self._code.append(Comment(self,""))
        lastLine = self._code[-1]
        if hasattr(token,"original") and token.original:
            original = token.original
            if not hasattr(lastLine,"original") or keyword not in non_code: lastLine.original = original.strip()
            elif keyword in non_code: lastLine.original += "\n"+original.strip()
        if keyword is not None and comment is not "": lastLine.inlineComment = Comment(self, comment)

    def parse_args(self, args_in, type_):
        if not args_in: return []
        args = []
        if type_ in ["ClassicalRegister", "QuantumRegister"]:
            for arg in args_in:
                args.append(self._resolve(arg["var"], type_, arg.get("ref",None)))
        elif type_ in ["Constant"]:
            for arg in args_in:
                args.append(self._resolve(arg, type_))
        else:
            self._error("Cannot parse args of type {}".format(type_))

        return args

    def parse_instructions(self):
        for instruction in self.instructions:
            self.parse_line(instruction)

    def parse_range(self, rangeSpec, arg = None, indexOnly = False):

        if rangeSpec is None:
            if arg:
                if arg.size is None: interval = ( None, None )
                elif isinstance(arg.size, int):
                    if indexOnly: interval = ( arg.size, arg.size )
                    else: interval = ( 0, arg.size-1 )
                elif isinstance(arg.size, str):
                    if indexOnly: interval = (arg.size, arg.size)
                    else: interval = ( 0, arg.size )
                elif isinstance(arg.size, MathsBlock):
                    return (0, arg.size)
                else:
                    self._error("Unable to determine argument size")
            else:
                self._error(loopSpecWarning.format("start or end"))

        elif rangeSpec.get("index", None) is not None:
            point = rangeSpec.get("index", None)
            if isinstance(point, ParseResults): point = point.get("var", point)
            point = self._resolve(point, type_ = "Constant")
            interval = (point, point)
            self._check_bounds(interval, arg)

        elif rangeSpec.get("start", None) is not None or rangeSpec.get("end", None) is not None:
            if indexOnly: self._error("Passed range specifier to index")
            start, end = rangeSpec.get("start", None), rangeSpec.get("end", None)

            start = self._resolve(start, type_ = "Constant")
            end   = self._resolve(end, type_ = "Constant")

            if arg:
                if not start: start = 0
                if not end: end = arg.size
            else:
                if start is None or end is None:
                    self._error(loopSpecWarning.format("end" if end is None else "start"))

            interval = (start, end)

            self._check_bounds(interval, arg)

        else:
            self._error("Unknown range specification: {}".format(rangeSpec))

        return interval

    def parse_maths(self, maths):
        return MathsBlock(self,maths,topLevel = True)

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))


# Maths Parsing

class MathsBlock:
    """ Block for handling maths as returned from the parser """

    def __init__(self, parent, maths, topLevel=False):
        self.parent = parent
        self.topLevel = topLevel
        elem = copy.deepcopy(maths)

        self.logical = False
        if isinstance(elem, Binary):
            new_args = []
            for op, operand in elem.args:
                # Skip identities
                if (op in "+-") and str(operand) == "0": continue
                if (op in "*/%") and str(operand) == "1": continue

                if issubclass(type(operand), MathOp):
                    operand = MathsBlock(parent, operand)
                    new_args.append( (op, operand) )
                else:
                    operand = parent._resolve(operand, type_="Maths")
                    new_args.append( (op, operand) )
            elem.args = new_args
        elif isinstance(elem, Function):
            new_args = []
            for arg in elem.args:
                if issubclass(type(arg), MathOp):
                    arg = MathsBlock(parent, arg)
                    new_args.append( arg )
                else:
                    arg = parent._resolve(arg, type_="Maths")
                    new_args.append( arg )
            elem.args = new_args

        self.maths = [elem]

    def __add__(self, val):
        return MathsBlock(self.parent, Binary( [[ self.maths, "+", val ]] ))

    def __sub__(self, val):
        return MathsBlock(self.parent, Binary( [[ self.maths, "-", val ]] ))

    def __div__(self, val):
        return MathsBlock(self.parent, Binary( [[ self.maths, "/", val ]] ))

    def __mul__(self, val):
        return MathsBlock(self.parent, Binary( [[ self.maths, "*", val ]] ))


    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))


# Variable types

class Constant(Referencable):
    """ Class pertaining to a constant value or variable object """

    def __init__(self, parent, var, val):
        Referencable.__init__(self, parent)
        self.name = var[0]
        self.var_type = var[1]
        self.val  = val[0]
        self.cast = val[1]
        self.loopVar = False
        self.parent = parent

    def __add__(self, val):
        return MathsBlock(self.parent, Binary( [[ self, "+", val ]] ))

    def __sub__(self, val):
        return MathsBlock(self.parent, Binary( [[ self, "-", val ]] ))

    def __div__(self, val):
        return MathsBlock(self.parent, Binary( [[ self, "/", val ]] ))

    def __mul__(self, val):
        return MathsBlock(self.parent, Binary( [[ self, "*", val ]] ))

    def __deepcopy__(self, memo):
        return Constant(self.parent, (self.name, self.var_type), (self.val, self.cast) )

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class Register(Referencable):
    """
    Base class pertaining to list-like objects:
    - Classical registers (creg)
    - Quantum registers   (qreg)
    - Aliases             (alias)
    """

    def __init__(self, parent, name, size):
        Referencable.__init__(self, parent)
        self.name = name

        self.size = self.render_size(size)

    def render_size(self, inter):
        """
        Take an input interval and assign corresponding min/max and sizes for consistency in checks
        """

        if isinstance(inter, tuple):
            start, end = inter

            if isinstance(start, Constant): start = start.val
            if isinstance(end,   Constant): end   = end.val
            if start == end:
                size = end
                start, end = 0, end
            else:
                size = end - start + 1
            self.min = start
            self.max = end
            self.start = 0
            self.end = size

        else:
            size = inter
            self.min = 0
            self.max = size
            self.start, self.end = self.min, self.max

        return size

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class QuantumRegister(Register):
    """
    Quantum register as created by "qreg"
    """
    numQubits = 0

    def __init__(self, parent, name, inter):
        Register.__init__(self, parent, name, inter)

        self.start += QuantumRegister.numQubits
        self.end   += QuantumRegister.numQubits
        QuantumRegister.numQubits += self.size

class ClassicalRegister(Register):
    """
    Classical register as created by "creg"
    """
    def __init__(self, parent, name, inter):
        Register.__init__(self, parent, name, inter)

        self.start = 0
        self.end = self.size

class DeferredClassicalRegister(ClassicalRegister):
    """
    Classical register whose size is unknown until execution of the code,
    e.g. size is a function variable
    """
    def __init__(self, parent, name, size):
        Register.__init__(self, parent, name, size)
        self.type_ = "ClassicalRegister"

class Alias(Register):
    """
    Alias as specified in REQASM
    """

    def __init__(self, parent, name, inter):
        Register.__init__(self, parent, name, inter)
        self.type_ = "Alias"
        self.targets = [(None, None)]*self.size
        self.all_set = False

    def set_target(self, indices, target, interval):
        """ Aliases target to indices """
        for index in range(indices[0],indices[1]+1):
            self.targets[index - self.min] = (target, interval[0] + index)

        self.all_set = all(target is not (None, None) for target in self.targets)

class Argument(Register):
    """
    Dummy register for arguments to gates permitted to have size under REQASM specifications
    """

    def __init__(self, parent, name, size = None):
        Register.__init__(self, parent, name, size)
        self.name = name
        self.type_ = "QuantumRegister"
        self.start = name
        self.end = self.size


    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))


# Operation types
class Return(Operation):
    def __init__(self, parent, parg):
        Operation.__init__(self, parent, pargs = parg)

class Comment:
    def __init__(self, parent, comment):
        self.parent = parent
        self.name = comment
        self.comment = comment

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class Let(Operation):
    def __init__(self, parent, var, val = None):
        self.parent = parent
        if type(var) is Constant:
            self.const = var
        elif type(var) in [tuple, list]:
            self.const = Constant(self.parent, var, val)
        else:
            raise TypeError("Bad assignment of let")

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class CallGate(Operation):
    def __init__(self, parent, gate, pargs, qargs, gargs, spargs):
        self.name = gate
        Operation.__init__(self, parent, qargs, pargs, gargs, spargs)

        self.callee = self.parent._resolve(self.name, type_="Gate")

        self._check_args(pargs, qargs, gargs, spargs)

        self.handle_loops(self._qargs)

    def _check_args(self, pargs, qargs, gargs, spargs):
        """ Check gate arguments are valid and of the right size. Raise error if not """


        # Check number of args matches
        for name, args, expect in zip(["pargs", "gargs", "spargs"],
                                      [pargs, gargs, spargs],
                                      [self.callee._pargs, self.callee._gargs, self.callee._spargs]):
            if len(args) != len(expect):
                self.parent._error(argWarning.format(f"call to {self.name}", f"{len(expect)} {name}", len(args)))

        parsed_sparg = zip((sparg.name for sparg in self.callee._spargs), spargs)

        new_spargs = dict(parsed_sparg)
        new_qargs = []

        for sparg in spargs: # Disambiguate?
            if sparg in self.parent._spargs:
                new_spargs[sparg.name] = 0


        for qarg in self.callee._qargs:
            new_qargs.append([qarg, int(self.parent._resolve_maths(qarg.size, additional_vars = new_spargs ))])

        self.resolved_qargs = new_qargs

        self.nLoops = 0
        # Implicit loops mean we handle qargs separately
        for id_, qarg in enumerate(qargs):
            # Hack to bypass stupidity of Python's object fiddling
            if isinstance(qarg[1][1], (Constant, MathsBlock)) or isinstance(qarg[1][0], (Constant, MathsBlock)) or \
               new_qargs[id_][1] == 0:
                continue
            nArg = qarg[1][1] - qarg[1][0] + 1
            expect = new_qargs[id_][1]
            if not isinstance(nArg, int): continue                # Skip constants which cannot be resolved
            if not self.nLoops : self.nLoops = nArg // expect  # Assume all vars much have the same number of loops
            if nArg % expect != 0:
                self.parent._error(argWarning.format(f"call to {self.name} in qarg {id_+1}",
                                                     f"multiple of {expect}", f"{nArg}"))
            elif nArg // expect != self.nLoops:
                self.parent._error(argWarning.format(f"call to {self.name} in qarg {id_+1} for implicit {self.nLoops} loops",
                                                     f"{expect*self.nLoops} qubits", f"{nArg}"))

    def handle_loops(self, pargs):
        """
        Handle loops for calling of gates:
        If gate args all just qubits not registers:
            Use regular handling
        If gate takes qregs, but can be looped (based on args):
            Loop in blocks
        If gate takes qregs and is not looped:
            Use prevars
        """

        # Gates need special loop handling for multi-args
        if all( qarg[1] == 1 for qarg in self.resolved_qargs ): # Can use regular loop if everyone only takes 1 arg
            Operation.handle_loops(self, pargs)
        elif self.nLoops < 2:
            for parg in pargs:
                pargStart, pargEnd = parg[1]

                if pargStart == pargEnd:
                    parg[1] = pargStart
                else:
                    pass
        else:
            raise NotImplementedError("Cannot currently loop non-linear gates")

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class SetAlias(Operation):
    def __init__(self, parent, alias, target):
        Operation.__init__(self, parent, pargs = alias, qargs = target)
        self.alias = alias[0]
        self.alias.set_target(alias[1], target[0], target[1] )

class Measure(Operation):
    def __init__(self, parent, qarg, parg):
        Operation.__init__(self, parent, qarg, parg)
        self.handle_loops([self._pargs, self._qargs])
        parg = self._pargs[0]
        bindex = self._pargs[1]
        qarg = self._qargs[0]
        qindex = self._qargs[1]
        # Check bindices
        if bindex is None:
            if parg.size < qarg.size:
                raise IOError(argSizeWarning.format(Req=qarg.size, Var=parg.name, Var2 = qarg.name, Max=parg.size))
            if parg.size > qarg.size:
                raise IOError(argSizeWarning.format(Req=parg.size, Var=qarg.name, Var2 = parg.name, Max=qarg.size))
            self._pargs[1] = self._qargs[1]
        self.finalise_loops()

class Reset(Operation):
    def __init__(self, parent, qarg):
        Operation.__init__(self, parent, qarg)
        self.handle_loops([self._qargs])

class Output(Operation):
    def __init__(self, parent, parg):
        Operation.__init__(self, parent, pargs = parg)
        self.handle_loops([self._pargs])

class EntryExit:
    def __init__(self, parent):
        self.parent = parent
        self.depth = 1

    def exited(self):
        self.depth = 0

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class While(CodeBlock):
    def __init__(self, parent, block, cond):
        self._cond = cond
        CodeBlock.__init__(self,block, parent=parent)
        self.parse_instructions()

class IfBlock(CodeBlock, Operation):
    def __init__(self, parent, cond, block):
        self._cond = cond
        CodeBlock.__init__(self, block, parent=parent)
        self.parse_instructions()

class Gate(Referencable, CodeBlock):
    """
    Type to handle general general gates and their extensions (circuit, procedure, etc.)
    """

    internalGates = {}

    def __init__(self, parent, name, block, pargs = [], qargs = [], spargs = [], gargs = [], byprod = [], recursive = False, unitary = False, returnType = None):

        Referencable.__init__(self, parent)
        self.name = name
        self._spargs = []
        self._gargs  = []

        CodeBlock.__init__(self, block, parent=parent)
        self.unitary = unitary

        self._inverse = None

        if recursive:
            self.gate(name, NullBlock(block), pargs, qargs, unitary = unitary)
            self._code = []
            self.entry = EntryExit(self.name)

        self.parse_gate_args(pargs,  "ClassicalArgument")
        self.parse_gate_args(spargs, "SpecialArgument")
        self.parse_gate_args(qargs,  "QuantumArgument")
        self.parse_gate_args(gargs,  "Gates")

        self.parse_instructions()

        if not byprod:
            self.returnType = None
        else:
            self._code.append( Return(self, byprod) )
            self.returnType = "listint"

        if returnType is not None: self.returnType = returnType

        if recursive and self.entry.depth > 0: self._error(noExitWarning.format(self.name))

    def invert(self, pargs, qargs):
        """
        Calculates the inverse of the gate and called gates and assigns it to self._inverse
        """

        if not self.unitary: self._error("Non-unitary object not invertible")
        if self._inverse: return self._inverse
        self._inverse = []

        for line in reversed(self._code):
            if type(line) is CallGate:
                self._inverse += self._objs[line.name].invert(pargs = line._pargs, qargs = line._qargs)
            else:
                self._error("Non-invertible object in gate {}".format(self.name))

        return self._inverse

    def parse_gate_args(self, args, type_):
        """
        Parse classes of arguments and assign them in scope
        """

        if not args: return []
        if type_ in ["ClassicalArgument"]:
            for arg in args:
                self._objs[arg] = Constant( self, (arg, "float") , ( MathsBlock(self, arg), None) )
                self._pargs.append(self._objs[arg])
        elif type_ in ["SpecialArgument"]:
            for arg in args:
                self._objs[arg] = Constant( self, (arg, "int") , ( MathsBlock(self, arg), None) )
                self._spargs.append(self._objs[arg])
        elif type_ in ["QuantumArgument"]:
            for argTok in args:
                arg = argTok["var"]
                size = argTok.get("ref", {"index":1})
                if size is not None: size = self.parse_range(size)
                self._objs[arg] = Argument(self, arg, size)
                self._qargs.append(self._objs[arg])
        elif type_ in ["Gates"]:
            for arg in args:
                self.gate(arg, NullBlock(block), unitary = self.unitary)

    def new_variable(self, argument):
        if not argument.classical: self._error("Cannot declare new qarg in gate")
        else : self._error("Cannot declare new parg in gate")

    def call_gate(self, gateName, pargs, qargs, gargs=None, spargs=None, modifiers = []):
        self._is_def(gateName, create=False, type_ = "Gate")
        # Perform unitary checks
        if self.unitary and not self._objs[gateName].unitary:
            self._error(unitaryWarning.format(gateName, self.name))

        CodeBlock.call_gate(self,gateName, pargs, qargs, gargs, spargs, modifiers)

    def measurement(self, *args, **kwargs):
        self._error("Cannot perform measure in gate")

class Circuit(Gate):
    """
    Type reflecting REQASM extension to gate
    """

    def __init__(self, *args, **kwargs):
        Gate.__init__(self, *args, **kwargs)
        self.type_ = "Gate"
        self.measurement = CodeBlock.measurement

    def new_variable(self, argName, size, classical):
        self._is_def(argName, create=True)

        if classical:
            variable = DeferredClassicalRegister(self, argName, size)
            self._objs[argName] = variable
        else:
            self._error("Cannot declare new qarg in circuit")

        self._code += [variable]

    measurement = CodeBlock.measurement
        
class Opaque(Gate):
    """
    Type reflecting OpenQASM opaque gate
    Allows the definition of a block through directive extensions
    """

    def __init__(self, parent, name, pargs = [], qargs = [], spargs = [], gargs = [], byprod = [], recursive = False, unitary = False, returnType = None):
        self.type_ = "Gate"
        self.name = name
        self.inverse = None
        self.parent = parent
        self.parentFile = parent.currentFile
        self.returnType = returnType
        self.set_block(NullBlock(self.parentFile))
        self.unitary = unitary

        self._pargs = []
        self._qargs  = []
        self._spargs = []
        self._gargs  = []
        self.parse_gate_args(pargs,  "ClassicalArgument")
        self.parse_gate_args(spargs, "SpecialArgument")
        self.parse_gate_args(qargs,  "QuantumArgument")
        self.parse_gate_args(gargs,  "Gates")

    def set_block(self, block):
        CodeBlock.__init__(self, block, parent=self.parent)
        self.parse_instructions()

    def set_inverse(self, block):
        CodeBlock.__init__(self, block, parent=self.parent)
        self.inverse = block

class ExternalLang:
    pass

class CBlock(ExternalLang):
    def __init__(self, parent, block):
        self.parent = parent
        self.block = block

class Loop(CodeBlock):
    def __init__(self, parent, block, var, start, end, step = None):
        CodeBlock.__init__(self,block, parent=parent)
        self._objs[var] = Constant( self, (var, "int") , (0, None) ) # Value is 0 for disambiguating resolution
        self._objs[var].loopVar = True
        self.loopVar = self._objs[var]
        self.name = var+"_loop"
        self.depth = 1

        if not isinstance(var, (list,tuple) ): var = [var]
        if not isinstance(start, (list,tuple) ): start = [start]
        if not isinstance(end, (list,tuple) ): end = [end]

        self.var = var
        self.start = start
        self.end = end
        self.step = step or (1,)*len(start)
        if not isinstance(self.step, (list,tuple) ): self.step = [step]
        self.parse_instructions()

class NestLoop(Loop):
    def __init__(self, block, var, start, end, step = 1):
        self._code = [block]
        self.depth = 1
        if not isinstance(var, (list,tuple) ): var = [var]
        if not isinstance(start, (list,tuple) ): start = [start]
        if not isinstance(end, (list,tuple) ): end = [end]

        self.var = var
        self.start = start
        self.end = end
        self.step = step
        if not isinstance(self.step, (list,tuple) ): self.step = [step]

class InitEnv:
    # Initialise QuESTEnv
    def __init__(self):
        pass

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class Verbatim:
    def __init__(self, line):
        self.line = str(line)

    def to_lang(self):
        return self.line

class Include:
    def __init__(self, parent, filename, code):
        self.parent = parent
        self.filename = filename
        self.code = code

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class Cycle:
    def __init__(self, var):
        self.var = var

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class Escape:
    def __init__(self, var):
        self.var = var

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class TheEnd:
    def __init__(self, process):
        self.process = process

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))
