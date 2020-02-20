"""
Module to handle reading of QASM files, blocks and perform error handling with useful output
"""

import sys
import os.path
from pyparsing import (ParseException)
from .tokens import (QASMcodeParser, lineParser, errorKeywordParser, reserved, parse_version,
                         qops, cops, blocks)
from .errors import (headerVerWarning, QASMVerWarning, fileWarning, recursionError, fnfWarning,
                         unknownParseWarning, instructionWarning, eofWarning, QASMBlockWarning)

class QASMFile:
    """
    Main class to handle QASM text files and sensibly handle errors.

    :param filename: File to load and parse
    :param reqVersion: Needs to be at least this version
    """
    _QASMFiles = []
    depth_limit = 10

    def __init__(self, filename, reqVersion=(1, 2, 0)):
        if filename in QASMFile._QASMFiles:
            raise IOError('Circular dependency in includes')
        if os.path.isfile(filename):
            self.openFile = open(filename, 'r')
        else:
            raise FileNotFoundError(fnfWarning.format(filename))

        self.path = filename
        self.name = filename[filename.rfind('/')+1:] # Remove path
        if len(QASMFile._QASMFiles) > self.depth_limit:
            self.error(recursionError.format(self.depth_limit))
        QASMFile._QASMFiles.append(self.name)
        self.nLine = 0
        self.header = []
        self.classLang = None

        for line in self.read_instruction():
            if line.get('keyword', None) is None:
                if line.get("comment", None) is not None:
                    self.header += [line['comment']]
                else:
                    pass
            elif line.get('keyword') == "version":
                self.version = parse_version(line["version"][0])
                self.QASMType = line["version"]["type"]
                self.versionNumber = line["version"]["versionNumber"]
                break
            else:
                self.error(headerVerWarning)

        if reqVersion[0] > self.version[0]:
            self.error(QASMVerWarning.format(*self.version))

    def error(self, message=""):
        """ Raise error formatted with filename and line number for help debugging """
        print(fileWarning.format(message=message,
                                 file=self.name, line=self.nLine))
        import traceback
        traceback.print_stack()
        sys.exit(1)

    def __del__(self):
        try:
            openFiles = QASMFile._QASMFiles
            del openFiles[openFiles.index(self.name)]
            self.openFile.close()
        except AttributeError:
            return

    def _handler(self, err, line):
        """ Make errors from parsing more comprehensible by trying different parsers independently """
        if not err.line:
            print("No line found")
            self.error(unknownParseWarning)
        if len(line) < 80:
            print(" ".join(line.splitlines()))
            print(" "*(line.index(err.line) + err.column-1) + "^")
        else:
            print(err.line)
            print(" "*(err.column-1) + "^")
        problem = errorKeywordParser.parseString(err.line)
        key = problem["keyword"]
        try:
            if key in qops.keys():
                qops[key].parser.parseString(err.line)
            elif key in cops.keys():
                cops[key].parser.parseString(err.line)
            elif key in blocks.keys():
                blocks[key].parser.parseString(err.line)
            else:
                raise ParseException(instructionWarning.format(key, self.QASMType, self.versionNumber))
            if key in ["gate", "circuit", "opaque"]:
                if reserved.searchString(err.line.replace(key, "")):
                    raise ParseException("Reserved keyword '{}' used in {} declaration".format(
                        reserved.searchString(err.line.replace(key, "")).pop().pop(), key
                        ))
            raise ParseException(unknownParseWarning + f" with parsing {problem['keyword']}")

        except ParseException as subErr:
            print(fileWarning.format(message=subErr.msg, file=self.name, line=self.nLine))
            import traceback
            traceback.print_stack()
            sys.exit(1)

    def read_instruction(self):
        """ Generator to read a single instruction from the file """
        line = self.readline()
        currentLine = line
        while line is not None:
            *test, = lineParser.scanString(currentLine.strip())

            if test and test[0][1] == 0: # If line looks like valid instruction
                try:
                    prev = 0
                    for inst, start, end in QASMcodeParser.scanString(currentLine.lstrip()):
                        if start != prev:
                            if prev != 0:
                                break
                            else: QASMcodeParser.parseString(currentLine, parseAll=True)
                        if not currentLine[start:end].strip():
                            continue # Skip blank lines
                        instruction = inst[0]
                        instruction.original = currentLine[start:end]
                        prev = end
                        yield instruction
                        currentLine = currentLine[end:].lstrip()
                except ParseException as err:
                    self._handler(err, currentLine)

            if currentLine.strip().startswith(";"): # Handle null statement
                currentLine = currentLine.lstrip(" ;\n\t")
            line = self.readline()
            if line is not None:
                currentLine += line

        if currentLine.strip(): # Catch remainder
            try:
                if list(QASMcodeParser.scanString(currentLine))[0][0] != 0:
                    raise IOError(eofWarning.format("parsing remainder:\n" + currentLine))
                for inst, start, end in QASMcodeParser.scanString(currentLine):
                    instruction = inst[0]
                    instruction.original = currentLine[start:end]
                    prev = end
                    yield instruction
                    currentLine = currentLine[end:].lstrip()

            except ParseException as err:
                self._handler(err, currentLine)

    def readline(self):
        """ Reads a line from a file """
        for line in self.openFile:
            self.nLine += 1
            if not line.strip():
                continue
            return line

        return None

    def _parent_file(self, parent):
        self.name = parent.name
        self.version = parent.version
        self.QASMType = parent.QASMType
        self.nLine = parent.nLine

class QASMString(QASMFile):
    """ Class to spoof a QASM file """
    def __init__(self, block):
        import io
        self.parent = self
        self.classLang = None
        self.version = (2, 2, 0)
        self.versionNumber = 2.0
        self.QASMType = "REQASM"
        self.name = "Internal"
        self.openFile = io.StringIO(block)
        self.currentFile = self
        self.nLine = 0
        self._objs = {}

    def get_objs(self, _):
        """ Objs getter to mimic main file """
        return self._objs

    def __del__(self):
        pass

class QASMBlock(QASMFile):
    """ Class to handle sub blocks of code such as if/for """
    def __init__(self, parent, block, startline=None):
        self._parent_file(parent)
        if startline:
            self.nLine = startline
        self.openFile = block

    def __len__(self):
        return len(self.openFile)

    def read_instruction(self):
        """ Generator to read a single instruction from the block """
        for instruction in self.openFile[0]:
            self.nLine += 1
            yield instruction

    def readline(self):
        """ Raise error because readline should not be called for blocks """
        raise NotImplementedError(QASMBlockWarning)

    def __del__(self):
        pass

class NullBlock(QASMFile):
    """ Class to serve as dummy block in case of opaque gates """
    def __init__(self, parent):
        self._parent_file(parent)
        self.openFile = [';']
        self.read = False

    def __len__(self):
        return 0

    def readline(self):
        """ Return null """
        if not self.read:
            self.read = True
            return " "
        return None

    def __del__(self):
        pass
