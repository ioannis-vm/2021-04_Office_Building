"""Common definitions."""

#
#   _|_|      _|_|_|  _|      _|    _|_|_|
# _|    _|  _|        _|_|  _|_|  _|
# _|    _|    _|_|    _|  _|  _|  _|  _|_|
# _|    _|        _|  _|      _|  _|    _|
#   _|_|    _|_|_|    _|      _|    _|_|_|
#
#
# https://github.com/ioannis-vm/OpenSees_Model_Generator

from __future__ import annotations

import re
from pprint import pprint
from typing import Any, Hashable, OrderedDict

# very big, very small numbers used for
# comparing floats and hashing
EPSILON = 1.00e-6
ALPHA = 1.00e8

# gravitational acceleration
G_CONST_IMPERIAL = 386.22  # in/s**2
G_CONST_SI = 9.81  # m/s**2

# quantities to use for extreme stiffnesses
STIFF_ROT = 1.0e15
STIFF = 1.0e10
TINY = 1.0e-12


def methods(obj: object) -> list[str]:
    """
    Get the methods of an object.

    Returns:
      The names of all methods of an object, excluding the dunder
      methods.

    Example:
        >>> class TestClass:
        ...     def method_1(self):
        ...         pass
        ...
        ...     def method_2(self):
        ...         pass
        ...
        >>> obj = TestClass()
        >>> methods(obj)
        ['method_1', 'method_2']
    """
    object_methods = [
        method_name
        for method_name in dir(obj)
        if callable(getattr(obj, method_name))
    ]
    pattern = r'__.*__'
    return [s for s in object_methods if not re.match(pattern, s)]


def print_methods(obj: object) -> None:
    """Print the methods of an object."""
    object_methods = methods(obj)
    pprint(object_methods)  # noqa: T203


def print_dir(obj: object) -> None:
    """Print the entire output of `dir()` of an object."""
    pprint(dir(obj))  # noqa: T203


def previous_element(
    dct: OrderedDict[Hashable, Any], key: Hashable
) -> Hashable | None:
    """
    Get the previous element.

    Returns the value of the element that comes before the given key
    in an ordered dictionary.
    If the key is not in the dictionary, or if it is the first element
    in the dictionary, returns None.

    Arguments:
        dct: An ordered dictionary.
        key: The key of the element whose previous element we want to
        find.

    Returns:
        The value of the element that comes before the given key in
        the dictionary, or None if there is no such element.

    Example:
        >>> dct = OrderedDict([(1, 'a'), (2, 'b'), (3, 'c')])
        >>> previous_element(dct, 2)  # Returns 'a'
        'a'
        >>> previous_element(dct, 3)  # Returns 'b'
        'b'
        >>> previous_element(dct, 1)  # Returns None

        >>> previous_element(dct, 4)  # Returns None

    """
    if key in dct:
        key_list = list(dct.keys())
        idx = key_list.index(key)
        if idx == 0:
            result = None
        else:
            result = dct[key_list[idx - 1]]
    else:
        result = None
    return result