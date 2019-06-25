from QASMParser.QASMTypes import *

def set_lang():
    ClassicalRegister.to_lang = ClassicalRegister_to_c
    QuantumRegister.to_lang = QuantumRegister_to_c
    DeferredClassicalRegister.to_lang = DeferredClassicalRegister_to_c
    Let.to_lang = Let_to_c
    Argument.to_lang = Argument_to_c
    CallGate.to_lang = CallGate_to_c
    Comment.to_lang = Comment_to_c
    Measure.to_lang = Measure_to_c
    IfBlock.to_lang = IfBlock_to_c
    While.to_lang = While_to_c
    Gate.to_lang = CreateGate_to_c
    Opaque.to_lang = CreateGate_to_c
    CBlock.to_lang = CBlock_to_c
    Loop.to_lang = Loop_to_c
    NestLoop.to_lang = Loop_to_c
    Reset.to_lang = Reset_to_c
    Output.to_lang = Output_to_c
    InitEnv.to_lang = init_env
    Return.to_lang = Return_to_c
    Include.to_lang = Include_to_c
    Cycle.to_lang = Cycle_to_c
    Escape.to_lang = Escape_to_c
    Alias.to_lang = Alias_to_c
    SetAlias.to_lang = SetAlias_to_c
    MathsBlock.to_lang = resolve_maths

# Several details pertaining to the language in question
hoistFuncs = True    # Move functions to front of program
hoistIncludes = True # Move includes to  front of program
hoistVars  = False   # Move variables to front of program
bareCode   = False   # Can code be bare or does it need to be in function
blockOpen = "{"      # Block delimiters
blockClose = "}"     #  ""      ""
indent = "  "        # Standard indent depth

typesTranslation = {
    "int":"int",
    "float":"qreal",
    "qreg":"Qureg",
    "complex":"Complex",
    "ComplexMatrix2":"ComplexMatrix2",
    "listint":"int",
    "listfloat":"float",
    "str":"char",
    "bool":"int",
    None:"void"
    }

def resolve_maths(self, elem):
    if isinstance(elem, MathsBlock):
        value = Maths_to_c(self, elem, False)
    elif isinstance(elem, list) and isinstance(elem[0], ClassicalRegister):
            if isinstance(elem[1], tuple):
                start, end = elem[1]
                if start == end :
                    value = f"{elem[0].name}[{start}]"
                else:
                    size = end - start + 1
                    if start:
                        value = f"decOf({elem[0].name}[{start}], {size})"
                    else:
                        value = f"decOf({elem[0].name}, {size})"
            elif elem[1] is None:
                value = f"decOf({elem[0].name}, {elem[0].size})"
    elif isinstance(elem, int) or isinstance(elem, float) or isinstance(elem, str):
        value = str(elem)
    elif isinstance(elem, Constant):
        value = elem.name
    elif issubclass(type(elem), MathOp):
        value = Maths_to_c(parent, elem, logical)
    else:
        raise NotImplementedError(elem)

    return value

def Include_to_c(self):
    return f'#include "{self.filename}"'

def inc_c(filename):
    return f'#include "{filename}"'

header = [inc_c("QuEST.h"), inc_c("stdio.h"), inc_c("reqasm.h")]

def init_env(self):
    return f'QuESTEnv Env = createQuESTEnv();'

def Output_to_c(self):
    parg, bindex = self._pargs
    return f'printf("%d ", {parg.name}[{bindex}]);'

def Return_to_c(self):
    return f'return {self._pargs[0]};'

def Cycle_to_c(self):
    return "continue;"

def Escape_to_c(self):
    return "break;"

def End_to_c(self):
    return "return;"

def Reset_to_c(self):
    qarg = self._qargs
    qargRef = self.resolve_arg(qarg)
    return f'collapseToOutcome(qreg, {qargRef}, 0);'

def ClassicalRegister_to_c(self):
    return f'int {self.name}[{self.size}];'+"\n"+f'for (int i = 0; i < {self.size}; i++) {self.name}[i] = 0;'

def DeferredClassicalRegister_to_c(self):
    if isinstance(self.size, MathsBlock):
        size = Maths_to_c(self, self.size, False)
    elif type(self.size) is list: size =  f'{{{",".join(self.size)}}}'
    else:  size =  f'{self.size}'

    return f'int* {self.name} = malloc(sizeof(int)*{size});'+"\n"+f'for (int i = 0; i < {size}; i++) {self.name}[i] = 0;'

def QuantumRegister_to_c(self):
    return f"Qureg {self.name} = createQureg({self.size}, Env);"

def Argument_to_c(self):
    if self.classical: return f'qreal {self.name}'
    else: return f'Qureg {self.name}, int {self.name}_index'

def Maths_to_c(parent, maths, logical):

    # Ops which should be unchanged
    identOp = ["-","+","*","/","%","<","<=","==","!=",">=",">","!","sin","cos","tan","sqrt","abs"]
    # Ops which require simple substitution
    subOp = {"and":"&&","or":"||","xor":"!=","mod":"%",
             "arccos":"acos", "arcsin":"asin","arctan":"atan"
             }
    # Ops which will be more complicated
    compSubOp = ["^","div"]
    outStr = ""

    if isinstance(maths.maths, Binary):
        for op, operand in maths.maths.args:
            if op == "nop":
                operand = resolve_maths(parent, operand)
                outStr += f"{operand}"
            elif op == "in":
                if len(operand) == 2:
                    outStr = f"({outStr} > {operand[0]} && {outStr} < {operand[1]})"
                else:
                    raise OSError
            elif op == "^":
                outStr = f"pow({outStr}, {operand})"
            elif op == "div":
                outStr = f"floor({outStr} / {operand})"
            elif op in identOp:
                operand = resolve_maths(parent, operand)
                outStr += f" {op} {operand}"
            elif op in subOp:
                operand = resolve_maths(parent, operand)
                outStr += f" {subOp[op]} {operand}"
            else:
                raise NotImplementedError(op)
    elif isinstance(maths.maths, Function):
        elem = maths.maths.op
        args = []
        for arg in maths.maths.args:
            args.append(resolve_maths(parent, arg))
        outStr += f"{elem}({', '.join(args)})"

    return outStr

def Alias_to_c(self):
    return f"int {self.name}[{self.size}];"

def SetAlias_to_c(self):
    outStr = ""

    if self.parent._resolve_maths( self._pargs[1][1] - self._pargs[1][0] + 1) > 1:
        aliasIndex, targetIndex = (self.alias.name+"_index",self._qargs[0].name+"_index")
        outStr += Loop(self.parent, NullBlock(self.parent.currentFile),
                       (aliasIndex, targetIndex),
                       (self._pargs[1][0], self._qargs[1][0]),
                       (self._pargs[1][1], self._qargs[1][1]), step = None).to_lang()
        if self._qargs[0].start > 0:
            outStr += f"\n  {self.alias.name}[{aliasIndex}] = {targetIndex} + {self._qargs[0].start};"
        else:
            outStr += f"\n  {self.alias.name}[{aliasIndex}] = {targetIndex};"
    else:
        self._qargs = (self._qargs[0], self._qargs[1][0])
        outStr = f"{self.alias.name}[{self._pargs[1][0]}] = {self.resolve_arg(self._qargs)};"
    return outStr

def Let_to_c(self):
    var = self.const

    assignee = var.name
    if var.var_type:
        assignee = f"{typesTranslation[var.var_type]} {assignee}"
        if var.var_type in ["listint", "listfloat"]: assignee += f"[{len(var.val)}]"

    # Simple declaration
    if var.val is None: return f"{assignee};"

    if isinstance(var.val, (list, tuple) ) :
        if var.var_type: value = f"{assignee};\n"
        else: value = ""
        for index, val in enumerate(var.val):
            if val is not None:
                value += f"{var.name}[{index}] = {val};\n"
        return value
    else:
        value = resolve_maths(self, var.val)
        if var.cast: value = f"({var.cast}) {value}"

    return f"{assignee} = {value};"

def CBlock_to_c(self):
    return "\n".join(self.block)

def CallGate_to_c(self):
    printArgs = ""
    outString = ""
    for index, (start, end) in enumerate(self._prevars):
        if start or end:
            varName = "temp_" + self._qargs[index][0].name
            varIndex = self._qargs[index][0].name + "_index"
            targetIndex = "temp_index"
            outString += Let( self.parent, ( varName, "listint" ), ( [None]*(end-start+1), None) ).to_lang()
            outString += Loop(self.parent, NullBlock(self.parent.currentFile),
                           (varIndex, targetIndex),
                           (0, start),
                           (end - start + 1, end), step = None).to_lang()
            if self._qargs[index][0].start > 0:
                outString += f"\n  {varName}[{varIndex}] = {targetIndex} + {self._qargs[index][0].start}; \n"
            else:
                outString += f"\n  {varName}[{varIndex}] = {targetIndex}; \n"

    if self._qargs:
        printArgs += "qreg"
        for index, qarg in enumerate(self._qargs):
            if self._prevars and self._prevars[index]:
                printArgs += ", "+qarg[1]
            else:
                printArgs += ", "+self.resolve_arg(qarg)
    if self._pargs:
        if self._qargs:
            printArgs += ", "
        printArgs += ", ".join([resolve_maths(self, parg) for parg in self._pargs])
    printGate = self.name
    preString = []
    for line in preString:
        outString += line + ";\n"
    outString += f"{printGate}({printArgs});"
    return outString

def Comment_to_c(self):
    if (len(self.comment.splitlines()) > 1): return "/*\n" + self.comment.replace("*/","**") + "\n*/"
    else: return "//" + self.comment.replace("/*","**").replace("*/","**")

def Measure_to_c(self):
    parg = self._pargs
    qarg = self._qargs
    qargRef = self.resolve_arg(qarg)
    pargRef = self.resolve_arg(parg)
    return f"{parg[0].name}[{pargRef}] = measure(qreg, {qargRef});"

def IfBlock_to_c(self):
    outStr = Maths_to_c(self, self._cond, True)
    return f"if ({outStr}) "

def While_to_c(self):
    outStr = Maths_to_c(self, self._cond, True)
    return f"while ({outStr}) "


def CreateGate_to_c(self):
    printQargs = ""
    printPargs = ""
    if self._qargs: printQargs = "Qureg qreg, " + ", ".join(
            (f"int {qarg.name}_index" if qarg.size == 1 else f"int* {qarg.name}_index" for qarg in self._qargs )
    )
    if self._pargs: printPargs = ", ".join((f"{parg.var_type} {parg.name}" for parg in self._pargs))

    printArgs = ", ".join((printQargs, printPargs)).rstrip(", ")
    returnType = typesTranslation[self.returnType]
    outStr = f"{returnType} {self.name}({printArgs}) "
    return outStr

def Loop_to_c(self):
    resolve = lambda b: resolve_maths(self, b)
    start = map ( resolve, self.start )
    end   = map ( resolve, self.end )
    step  = map ( resolve, self.step )

    var  = ( f"int {var} = {init}" for var, init in zip(self.var, start) )
    term = ( f"{var} <= {term}"    for var, term in zip(self.var, end) )
    inc  = ( f"{var} += {inc}"     for var, inc  in zip(self.var, step) )
    return f"for ( {', '.join(var)}; {' && '.join(term)}; {', '.join(inc)} )"

