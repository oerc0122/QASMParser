"""
Module containing potential warning messages thrown by the parser
"""

# Declare several warnings which may occur
eofWarning = "Unexpected end of file while {}"
includeWarning = "{name} in {other} already defined as {type} in {me}"
indexTypeWarning = "Cannot use {} as index"
langMismatchWarning = "Classical language {} does not match output language {}"
langNotDefWarning = "Language {0} translation not found, check QASMParser/langs/{0}.py exists"
noLangSpecWarning = "No language specified for screen print"
noSpecWarning = "Neither language nor output with recognised language specified"
opaqueWarning = "Opaque gate cannot have body in {}"
parseArgWarning = "Issue parsing {} of type {}"
typeWarning = "Unrecognised type {} requested in function {}"

# File parsing
fileWarning = "{message} in {file} at line {line}"
fnfWarning = "File {} not found"
headerVerWarning = "Header does not contain version"
QASMVerWarning = "Unsupported QASM version: {}.{}"
QASMBlockWarning = "Attempted to read line from QASMBlock"
recursionError = "Include depth exceeds {}, possible recursion"
unknownParseWarning = "Unknown parsing error occurred"

# Tokenising
dupTokenWarning = "{} token {} already defined"
QASMWarning = "Unrecognised QASM Version statement {}"

# Tree building and arg parsing
aliasIndexWarning = "Mismatched indices {}: Requested {}, received {}"
argParseWarning = "Cannot parse args of type {}"
argSizeWarning = "Args {Var} and {Var2} are different sizes and cannot be implicitly assigned."
rangeSpecWarning = "Unknown range specification: {}"
rangeToIndexWarning = "Passed range specifier to index"
badDirectiveWarning = "Unrecognised directive: {}"
argWarning = "Bad argument list in {} expected {}, received {}"
redefClassLangWarning = "Classical language already defined as {}"
inlineOpaqueWarning = "Cannot set opaque by inline directive"
dupWarning = "{Name} is already declared as a {Type}"
existWarning = "{Type} {Name} has not been declared"
gateDeclareWarning = "Cannot declare {} in {}"
gateWarning = "Unrecognised gate-like type {}"
failedOpWarning = "Cannot {} in {}"
includeNotMainWarning = "Attempted to include file from within routine or loop"
indexWarning = "Index {Req} out of expected range for {Var}: [{Min}:{Max}]"
instructionWarning = "Unrecognised instruction: {} not in {} {} format"
langWarning = "QASM instruction {} not implemented in output language."
loopSpecWarning = "Interval specified without {}, both required"
mathsEvalWarning = "Error parsing maths string:\n '{}'\n"
noExitWarning = "Recursive gate {} does not have defined exit"
wrongTypeWarning = "Bad argument, expected {} received {}"


# Partitioning
partitionWarning = ("Partitioning suggests no partitions.\n"
                    "Recommend running with different partitioning method or disable partitioning")


def print_decor(func):
    """Decorator for identifying the location of print statements."""
    import inspect
    import sys
    def wrapper(name):
        sys.stdout.write(
            f"{inspect.currentframe().f_back.f_code.co_filename} {inspect.currentframe().f_back.f_lineno}: ")
        func(name)
    return wrapper

#print = print_decor(print)
