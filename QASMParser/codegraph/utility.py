"""
Module containing core utility functions
"""


def exp_add(a: float, b: float):
    """ Add the exponents of two numbers
    :param a: input exponent
    :param b: input exponent
    :returns: Sum of exponents"""
    import math
    if b == 0:
        return a
    if a == 0:
        return b

    # Assume that for very large numbers the 1 is irrelevant
    if a > 30 or b > 30:
        return a + b

    if a > b:
        out = math.log2(2**(a - b) + 1) + b
    else:
        out = math.log2(2**(b - a) + 1) + a
    return out

def range_inclusive(start=None, stop=None, step=1):
    """ Actually include the stop like anything sensible would """
    if step < 0:
        return range(start, stop-1, step)
    return range(start, stop+1, step)

def slice_inclusive(start=None, stop=None, step=1):
    """ Actually include the stop like anything sensible would """
    if step < 0:
        return slice(start, stop-1, step)
    return slice(start, stop+1, step)

