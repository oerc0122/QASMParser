
# Declare several warnings which may occur
eofWarning = 'Unexpected end of file while {}'
argWarning  = 'Bad argument list in {} expected {}, received {}'
existWarning  = '{Type} {Name} has not been declared'
dupWarning = '{Name} is already declared as a {Type}'
includeWarning= "'{name} in {other} already defined as {type} in {me}'"
wrongTypeWarning = 'Bad argument, expected {} received {}'
fileWarning = '{message} in {file} at line {line}'
fnfWarning  = 'File {} not found'
typeWarning = 'Unrecognised type {} requested in function {}'
indexWarning = "Index {Req} out of expected range for {Var}: [{Min}:{Max}]"
argSizeWarning = "Args {Var} and {Var2} are different sizes and cannot be implicitly assigned.\n" + indexWarning
QASMWarning = "Unrecognised QASM Version statement {}"
instructionWarning = "Unrecognised instruction: {} not in {} {} format"
langWarning = "QASM instruction {} not implemented in output language."
langNotDefWarning = "Language {0} translation not found, check QASMParser/langs/{0}.py exists"
recursionError = "Include depth exceeds {}, possible recursion"
noExitWarning = "Recursive gate {} does not have defined exit"
loopSpecWarning = "Interval specified without {}, both required"
indexTypeWarning = "Cannot use {} as index"
parseArgWarning = "Issue parsing {} of type {}"
opaqueWarning = "Opaque gate cannot have body in {}"
unknownParseWarning = "Unknown parsing error occurred"
unitaryWarning = "Attempted to call non-unitary gate {} from explicit unitary gate {}"
gateWarning = "Unrecognised gate-like type {}"
aliasIndexWarning = "Mismatched indices {}: Requested {}, received {}"

def print_decor(func):
    import inspect
    import sys
    def wrapper(name):
        sys.stdout.write(f"{inspect.currentframe().f_back.f_code.co_filename} {inspect.currentframe().f_back.f_lineno}: ")
        func(name)
    return wrapper

#print = print_decor(print)

