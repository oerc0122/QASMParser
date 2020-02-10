# QASMParser
A Utility for transpiling an extended QASM variant into QuEST or Pyquest inputs, with the capability to be extended to any other imperative quantum-simulator input.

# Requirements

## Core
 - Python 3.6+
 - [PyParsing][PyParsing]
## Tensor network functionality
 - [METIS][METIS]
 - [NumPy][Numpy]
 - [NetworkX][NetworkX] 
## TN Drawing
 - [PyGraphViz][PyGraphViz]

# Usage

Basic help can be found by running `QASMToQuEST.py -h`

```
usage: QASMToQuEST.py [-h] [-o OUTPUT] [-l LANGUAGE] [-d] [-c]
                      [-I QASMFILE=CFILE,QASMFILE2=CFILE2,...] [-a]
                      [-p [PRINT]] [-e [ENTANGLEMENT]] [-t]
                      [--max-depth MAX_DEPTH] [--include-internals]
                      [-P PARTITION]
                      sources [sources ...]

QASM parser to translate from QASM to QuEST input

positional arguments:
  sources               List of sources to compile

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        File to compile to
  -l LANGUAGE, --language LANGUAGE
                        Output file language
  -d, --debug           Output original QASM in translation
  -c, --to-module       Compile as module for inclusion into larger project
  -I QASMFILE=CFILE,QASMFILE2=CFILE2,..., --include QASMFILE=CFILE,QASMFILE2=CFILE2,...
                        Include a pre-transpiled source
  -a, --analyse         Print adjacency matrix info
  -p [PRINT], --print [PRINT]
                        Print graphical summary of circuit to file
  -e [ENTANGLEMENT], --entanglement [ENTANGLEMENT]
                        Print graphical summary of entanglements to file
  -t, --dummy-partition
                        Calculate effects of partition without compilation
  --max-depth MAX_DEPTH
                        Max depth for analysis and printing
  --include-internals   Include internal gates explicitly
  -P PARTITION, --partition PARTITION
                        Set partitioning optimisation type:
                            0 = None  -- Do not attempt to partition,
                            1 = Registers -- Partition based on specification of qregs in QASM,
                            2 = Space-like -- Slice only in qreg space based on adjacent slice-cost analysis,
                            3 = Space-time-like -- Perform full graph analysis and attempt to partition
```

## Basic usage

In general, a QASM file can be compiled with the following:

```QASMToQuEST.py -o test.c test.qasm```

Provided that all requirements including QASM includes are in the directory from which QASMToQuEST was run. 

## Explicit language

If the output language can be determined through the file extension of the output file, it will be. Otherwise, it will be necessary to define the language using the `-l` flag. 

```QASMToQuEST.py -o temp -l C test.qasm```

## Modules

In order to avoid having to recompile an included file, or to avoid it cluttering the final output, it is possible to part compile to something resembling a module. Essentially, this does not include the main or other includes of the module, allowing it to be imported in the output, rather than being included verbatim. 

```QASMToQuEST.py -c -o module.c module.qasm```

This can then replace a QASM include by using the `-I` flag.

```QASMToQuEST.py -I module.qasm=module.c -o test.c test.qasm```

## Include internals

Included 

[METIS]:https://pypi.org/project/metis/
[PyGraphViz]:https://pypi.org/project/pygraphviz/
[PyParsing]:https://pypi.org/project/pyparsing/
[Numpy]:https://pypi.org/project/numpy/
[NetworkX]:https://pypi.org/project/networkx/
