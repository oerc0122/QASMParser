from .QASMErrors import *
from .QASMTokens import *
from .FileHandle import QASMFile, QASMBlock, NullBlock
import re
import copy

isInt  = re.compile("[+-]?(\d+)(?:[eE][+-]?\d+)?")
isReal = re.compile("[+-]?(\d*\.\d+|\d+\.\d*)(?:[eE][+-]?\d+)?")

# Core types
class Operation:
    def __init__(self, parent, qargs = None, pargs = None):
        self.parent = parent
        self._loops = None
        self._qargs = qargs
        self._pargs = pargs

    def add_loop(self, index, start, end):
        if self._loops:
            self._loops = NestLoop(self._loops, index, start, end)
        else:
            self.innermost = NestLoop(copy.copy(self), index, start, end)
            self._loops = self.innermost

    def finalise_loops(self):
        if self._loops:
            self.innermost._code = [copy.copy(self)]
            self.innermost._code[0]._loops = []
        else:
            pass

    def handle_loops(self, pargs, slice = None):
        if all( ( isinstance( parg[1][0], int ) and isinstance( parg[1][1], int ) for parg in pargs) ):
            ranges = [ parg[1][1] - parg[1][0] for parg in pargs]
            if not all( ( size == ranges[0] for size in ranges ) ):
                self.parent._error("Mismatched indices in implcit loop")

        parg_init = [ parg[0].start for parg in pargs ]

        base = pargs[0]
        start, end = base[1]
        loopVar = False
        for parg in pargs:
            if start == end :
                parg[1] = start
            else:
                loopVar = base[0].name + "_loop"
                parg[1] = loopVar

        if loopVar:
            self.add_loop(loopVar, start, end)

    def resolve_arg(self, arg):
        if type(arg[0]) is Argument:
            if arg[0].start and arg[1]:
                return f"{arg[0].start} + {arg[1]}"
            else:
                return str(arg[0].start)
        elif issubclass(type(arg[0]),Register):
            
            start = arg[1]
            offset = arg[0].start
            if isinstance(start, int):
                return str(offset + start)
            elif isinstance(start, Constant):
                return f"{offset} + {arg[1].val}"
            elif isinstance(start, str):
                if (offset > 0): return f"{start} + {arg[0].start}"
                else: return f"{start}"
            else:
                return arg[1]
        else:
            raise TypeError(parseArgWarning.format("arg", type(arg[0]).__name__))

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class Referencable:
    def __init__(self):
        self.type_ = type(self).__name__

class CodeBlock:
    def __init__(self, block, parent, copyObjs = True, copyFuncs = True):
        self._code = []
        self._qargs= []
        self._pargs= []
        if copyObjs:
            self._objs = copy.copy(parent._objs)
        else:
            self._objs = {}
        self.currentFile = block
        self.instructions = self.currentFile.read_instruction()
        self._error = self.currentFile._error
        QASMType = self.currentFile.QASMType

    def _resolve(self, var, type_, index = ""):

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

                return [var, var.name + "_index"]


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
            else:
                self._is_def(var, create=False, type_ = None)
                var = self._objs[var]

                if isinstance(var,Argument):

                    return [var, var.name + "_index"]

                elif isinstance(var,Constant):

                    return var.name

                elif isinstance(var, ClassicalRegister):

                    if index or index is None: # If index or implicit loop

                        index = self.parse_range(index, var)

                        return [var, index]
                    else:
                        return [var, None]
                elif isinstance(var, QuantumRegister):
                    self._error("Cannot use quantum register {} in maths expression".format(var.name))
                    
                else:
                    self._error("Undetermined type in maths parsing")

        elif type_ == "Gate":
            self._is_def(var, create=False, type_ = type_)
            # Add argument checking?
            return self._objs[var]

        else:
            self._error("Unrecognised type {} in _resolve".format(type_))

    def _check_def(self, name, create:bool, type_ = None):
        if name not in self._objs: return create
        elif type_ is not None and self._objs[name].type_ is not type_: return False
        else: return not create

    def _is_def(self, name, create:bool, type_ = None):

        if create: # Check for duplicate naming
            if name in self._objs: self._error(dupWarning.format(Name=name, Type=self._objs[name].type_))

        else: # Check exists and type is right
            if name not in self._objs:
                self._error(existWarning.format(Type=type_, Name=name))
            elif type_ is None: pass
            elif self._objs[name].type_ is not type_:
                self._error(wrongTypeWarning.format(type_,self._objs[name].type_))

    def _check_bounds(self,interval, arg = None):
        if arg is None: return
        if isinstance(interval[0],int) and interval[0] < arg.start:
            self._error(indexWarning.format(Req=interval[0], Var = arg.name, Min = arg.min, Max = arg.max))
        elif isinstance(interval[1],int) and interval[1] > arg.size:
            self._error(indexWarning.format(Req=interval[1], Var = arg.name, Min = arg.min, Max = arg.max))

    def comment(self, comment):
        self._code += [Comment(self,comment)]

    def new_variable(self, argName, size, classical):
        self._is_def(argName, create=True)

        if classical:
            variable = ClassicalRegister(argName, size)
            self._objs[argName] = variable
        else:
            variable = QuantumRegister(argName, size)
            self._objs[argName] = variable

        self._code += [variable]

    def new_alias(self, argName, size):
        self._is_def(argName, create=True)
        self._objs[argName] = Alias(argName, size)

    def alias(self, aliasName, argIndex, referee, refIndex):
        referee, refInter = self._resolve(referee, type_="QuantumRegister", index = refIndex)
        refInter = refInter[0], refInter[1]
        refSize = 1 + refInter[1] - refInter[0]
        
        if self._check_def(aliasName, create=True, type_ = "Alias"):
            self.new_alias(aliasName, refSize)

        alias, aliasInter = self._resolve(aliasName, type_="Alias", index=argIndex)
        aliasSize = 1 + aliasInter[1] - aliasInter[0]
        if aliasSize != refSize:
            self._error(f"Mismatched indices {aliasName}: Requested {refInter[1] - refInter[0]}, received {aliasInter[1] - aliasInter[0]}")

        alias.set_target(aliasInter, referee, refInter )

    def gate(self, gateName, block,
             pargs = None, qargs = None, spargs = None, gargs = None, byprod = None,
             recursive = False, unitary=False, type_ = "gate"):
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
        valName, valType = val
        
        val = (self._resolve( valName, type_="Constant"), valType)
        if self._check_def(varName, create=True, type_="Constant"):
            letobj = Constant( var, val )
            self._objs[letobj.name] = letobj
        else:
            var = ( self._resolve( varName, type_="Constant").name, None )
            letobj = Constant( var, val )
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

        gate = CallGate(self, gateName, pargs, qargs)

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
            mods  = token.get("mods",  [])

            self.call_gate(gateName, pargs, qargs, modifiers = mods)
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

    def __init__(self, parent, maths, topLevel=False):
        self.parent = parent
        self.topLevel = topLevel
        elem = maths
        self.logical = False
        if isinstance(elem, Binary):
            new_args = []
            for op, operand in elem.args:
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

        self.maths = elem

    def __add__(self, val):
        return MathsBlock(self.parent, Binary( [[ self.maths, "+", val ]] ))

    def __sub__(self, val):
        return MathsBlock(self.parent, Binary( [[ self.maths, "-", val ]] ))

    def __div__(self, val):
        return MathsBlock(self.parent, Binary( [[ self.maths, "*", val ]] ))

    def __mul__(self, val):
        return MathsBlock(self.parent, Binary( [[ self.maths, "*", val ]] ))

        
    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))
    
class ExternalLang:
    pass


# Variable types
class Constant(Referencable):
    def __init__(self, var, val):
        Referencable.__init__(self)
        self.name = var[0]
        self.var_type = var[1]
        self.val  = val[0]
        self.cast = val[1]
        self.loopVar = False

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class Register(Referencable):
    def __init__(self, name, size):
        Referencable.__init__(self)
        self.name = name

        self.size = self.render_size(size)

    def render_size(self, inter):
        if isinstance(inter, tuple):
            start, end = inter

            if isinstance(start, Constant): start = start.val
            if isinstance(end,   Constant): end   = end.val
            
            if start == end:
                size = end
                inter = (0, end)
            else:
                size = end - start + 1

            self.min = start
            self.max = end
        else:
            size = inter
            self.min = 0
            self.max = size

        return size
        
    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class QuantumRegister(Register):

    numQubits = 0

    def __init__(self, name, inter):
        Register.__init__(self, name, size)
        if size is None: return                            # Size is None implies argument
 
        self.start = QuantumRegister.numQubits
        if isinstance(inter, tuple): self.start -= inter[0]
        self.end   = QuantumRegister.numQubits + self.size
        QuantumRegister.numQubits += self.size

class ClassicalRegister(Register):
    def __init__(self, name, inter):
        size = self.render_size(inter)        

        Register.__init__(self, name, size)
        if size is None: return # Size is None implies argument

        self.start = 0
        self.end = size

class DeferredClassicalRegister(Register):
    def __init__(self, name, size):
        Referencable.__init__(self)
        self.name = name
        self.size = size
        self.type_ = "ClassicalRegister"
        self.start = 0
        self.end = size

class Alias(Register):
    def __init__(self, name, inter):
        Register.__init__(self, name, size)
        self.type_ = "Alias"
        self.start = inter[0]
        self.end = inter[0] + self.size
        self.targets = [(None, None)]*self.size

    def contiguous(self):
        self.blocks = []
        currBlock = []
        prev_target, prev_index = self.targets[0]
        prev_index -= 1
        for target, index in self.targets:
            if target != prev_target or index != prev_index + 1:
                self.blocks.append(currBlock)
                currBlock = []
            currBlock.append( (target, index) )
            prev_target, prev_index = target, index
        self.blocks.append(currBlock)
        if len(self.blocks) > 1: raise NotImplementedError("Cannot currently handle arbitrary aliasing")
        self.all_set = all(target is not (None, None) for target in self.targets)

    def set_target(self, indices, target, interval):

        for index in range(indices[0],indices[1]+1):
            self.targets[index - self.start] = (target, interval[0] + index)

        self.contiguous()

class Argument(Register):
    def __init__(self, name, size = None):
        Register.__init__(self,name,size)
        self.name = name
        self.type_ = "QuantumRegister"
        self.start = name + "_index"
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
            self.const = Constant(var, val)
        else:
            raise TypeError("Bad assignment of let")

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class CallGate(Operation):
    def __init__(self, parent, gate, pargs, qargs):
        self.name = gate

        Operation.__init__(self, parent, qargs, pargs)
        self.handle_loops(self._qargs)

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

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

    internalGates = {}

    def __init__(self, parent, name, block, pargs = [], qargs = [], spargs = [], gargs = [], byprod = [], recursive = False, unitary = False, returnType = None):

        Referencable.__init__(self)
        self.name = name
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
            self._code.append( Return(byprod) )
            self.returnType = "pointint"

        if returnType is not None: self.returnType = returnType

        if recursive and self.entry.depth > 0: self._error(noExitWarning.format(self.name))

    def invert(self, pargs, qargs):
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
        if not args: return []
        if type_ in ["ClassicalArgument"]:
            for arg in args:
                self._objs[arg] = Constant( (arg, "float") , ( MathsBlock(self, [arg]) , None) )
                self._pargs.append(self._objs[arg])
        elif type_ in ["SpecialArgument"]:
            for arg in args:
                self._objs[arg] = Constant( (arg, "int") , ( MathsBlock(self, [arg]), None) )
                self._pargs.append(self._objs[arg])
        elif type_ in ["QuantumArgument"]:
            for argTok in args:
                arg = argTok["var"]
                size = argTok.get("ref", {"index":1})
                if size is not None: size = self.parse_range(size)
                self._objs[arg] = Argument(arg, size)
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
    def __init__(self, *args, **kwargs):
        Gate.__init__(self, *args, **kwargs)
        self.type_ = "Gate"
        self.measurement = CodeBlock.measurement

    def new_variable(self, argName, size, classical):
        self._is_def(argName, create=True)

        if classical:
            variable = DeferredClassicalRegister(argName, self._resolve(size, "Constant"))
            self._objs[argName] = variable
        else:
            self._error("Cannot declare new qarg in circuit")

        self._code += [variable]

class Opaque(Gate):
    
    def __init__(self, parent, name, pargs = [], qargs = [], spargs = [], gargs = [], byprod = [], recursive = False, unitary = False, returnType = None):
        self.type_ = "Gate"
        self.name = name
        self.inverse = None
        self.parent = parent
        self.parentFile = parent.currentFile
        self.returnType = returnType
        self.set_block(NullBlock(self.parentFile))
        self.unitary = unitary
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
    def __init__(self, parent, block, var, start, end, step = 1):
        CodeBlock.__init__(self,block, parent=parent)
        self._objs[var] = Constant( (var, "int") , (var, None) )
        self._objs[var].loopVar = True
        self.depth = 1
        self.var = var
        self.start = start
        self.end = end
        if step != 1: raise NotImplementedError("Non contiguous loops not currently permitted")
        self.step = step
        self.parse_instructions()

class NestLoop(Loop):
    def __init__(self, block, var, start, end, step = 1):
        self._code = [block]
        self.depth = 1
        self.var = var
        self.start = start
        self.end = end
        if step != 1: raise NotImplementedError("Non contiguous loops not currently permitted")
        self.step = step

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
