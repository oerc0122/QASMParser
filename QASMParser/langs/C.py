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
    "pointint":"int *",
    "pointfloat":"float *",
    "str":"char",
    None:"void"
    }

def resolve_maths(self, maths):
    if isinstance(maths, MathsBlock):
        value = Maths_to_c(self, maths, False)
    elif type(maths) is list: value =  f'{{{",".join(maths)}}}'
    else:  value =  f'{maths}'
    return value
    
def Include_to_c(self):
    return f'#include "{self.filename}"'

def inc_c(filename):
    return f'#include "{filename}"'

header = [inc_c("QuEST.h"), inc_c("stdio.h"), inc_c("reqasm.h")]

def init_env(self):
    return f'QuESTEnv Env = createQuESTEnv();'

def Output_to_c(self):
    carg, bindex = self._cargs
    return f'printf("%d ", {carg.name}[{bindex}]);'

def Return_to_c(self):
    return f'return {self._cargs[0]};'

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
             "arccos":"acos", "arcsin":"asin","arctan":"atan",
             }
    # Ops which will be more complicated
    compSubOp = ["^","div","in"]
    outStr = " "

    # if maths.topLevel and maths.logical is not logical:
    #     raise TypeError("Cannot pass logical expression to mathematical expression or vice-versa")
    for elem in maths.maths:
        if isinstance(elem, list) and isinstance(elem[0], ClassicalRegister):
            if isinstance(elem[1], tuple):
                start, end = elem[1]
                if start == end :
                    elem[1] = start
                else:
                    if start:
                        outStr += f"decOf({elem[0].name}[{start}], {end-start})"
                    else:
                        outStr += f"decOf({elem[0].name}, {end-start})"
            elif elem[1] is None:
                outStr += f"decOf({elem[0].name}, {elem[0].size})"
        elif isinstance(elem, str):
            if elem not in MathsBlock.special:
                outStr += elem
            elif elem in identOp:
                outStr += elem
            elif elem in subOp:
                outStr += subOp[elem]
            else:
                raise NotImplementedError(elem)
        elif isinstance(elem, int) or isinstance(elem, float):
            outStr += str(elem)
        elif isinstance(elem, MathsBlock):
            outStr += Maths_to_c(parent, elem, logical)
        elif isinstance(elem, Constant):
            outStr += elem.name
        elif isinstance(elem, In):
            arg = Maths_to_c(parent, elem.var, logical)
            outStr += f"{arg} > {elem.inter[0]} && {arg} < {elem.inter[1]}"
        else:
            raise NotImplementedError(elem)
        outStr += " "
    if (maths.topLevel): return outStr
    else: return "(" + outStr + ")"
        
def Let_to_c(self):
    var = self.const

    assignee = var.name
    if var.var_type: assignee = f"{var.var_type} {assignee}"

    # Simple declaration
    if var.val is None: return f"{assignee};"

    value = resolve_maths(self, var.val)
    
    if var.cast: value = f"({var.cast}) {value}"

    return f"{assignee} = {value};"

def CBlock_to_c(self):
    return "\n".join(self.block)
    
def CallGate_to_c(self):
    printArgs = ""
    if self._qargs:
        printArgs += "qreg, "
        printArgs += ", ".join([self.resolve_arg(qarg) for qarg in self._qargs])
    if self._cargs:
        if self._qargs:
            printArgs += ", "
        printArgs += ", ".join([resolve_maths(self, carg) for carg in self._cargs])
    printGate = self.name
    preString = []
    outString = ""    
    for line in preString:
        outString += line + ";\n"
    outString += f"{printGate}({printArgs});"
    return outString

def Comment_to_c(self):
    if (len(self.comment.splitlines()) > 1): return "/*\n" + self.comment + "\n*/"
    else: return "//" + self.comment

def Measure_to_c(self):
    carg = self._cargs
    qarg = self._qargs
    qargRef = self.resolve_arg(qarg)
    cargRef = self.resolve_arg(carg)
    return f"{carg[0].name}[{cargRef}] = measure(qreg, {qargRef});"

def IfBlock_to_c(self):
    outStr = Maths_to_c(self, self._cond, True)
    return f"if ({outStr}) "

def While_to_c(self):
    outStr = Maths_to_c(self, self._cond, True)
    return f"while ({outStr}) "
    

def CreateGate_to_c(self):
    printQargs = ""
    printPargs = ""
    if self._qargs: printQargs = "Qureg qreg, " + ", ".join((f"int {qarg.name}_index" for qarg in self._qargs))
    if self._cargs: printPargs = ", ".join((f"{carg.var_type} {carg.name}" for carg in self._cargs))
        
    printArgs = ", ".join((printQargs, printPargs)).rstrip(", ")
    returnType = typesTranslation[self.returnType]
    outStr = f"{returnType} {self.name}({printArgs}) "
    return outStr

def Loop_to_c(self):
    return  f"for (int {self.var} = {self.start}; {self.var} < {self.end}; {self.var} += {self.step}) "

