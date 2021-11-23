# Copyright (C) 2021 Aurore Fass
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


"""
    Utility file, stores shared information.
"""

import sys
import resource
import timeit
import logging
import signal
import traceback

sys.setrecursionlimit(100000)


TEST = False

if TEST:  # To test, e.g., the examples
    PDG_EXCEPT = True  # To print the exceptions encountered while building the PDG
    LIMIT_SIZE = 10000  # To avoid list/str values with over 10,000 characters
    LIMIT_RETRAVERSE = 1  # If function called on itself, then max times to avoid infinite recursion
    LIMIT_LOOP = 5  # If iterating through a loop, then max times to avoid infinite loops
    DISPLAY_VAR = True  # To display variable values
    CHECK_JSON = True  # Builds the JS code from the AST, to check for possible bugs in the AST

    NUM_WORKERS = 1

else:  # To run with multiprocessing
    PDG_EXCEPT = False  # To ignore (pass) the exceptions encountered while building the PDG
    LIMIT_SIZE = 10000  # To avoid list/str values with over 10,000 characters
    LIMIT_RETRAVERSE = 1  # If function called on itself, then max times to avoid infinite recursion
    LIMIT_LOOP = 1  # If iterating through a loop, then max times to avoid infinite loops
    DISPLAY_VAR = False  # To not display variable values
    CHECK_JSON = False  # To not build the JS code from the AST

    NUM_WORKERS = 1  # CHANGE THIS ONE


class UpperThresholdFilter(logging.Filter):
    """
    This allows us to set an upper threshold for the log levels since the setLevel method only
    sets a lower one
    """

    def __init__(self, threshold, *args, **kwargs):
        self._threshold = threshold
        super(UpperThresholdFilter, self).__init__(*args, **kwargs)

    def filter(self, rec):
        return rec.levelno <= self._threshold


logging.basicConfig(format='%(levelname)s: %(filename)s: %(message)s', level=logging.CRITICAL)
# logging.basicConfig(filename='pdg.log', format='%(levelname)s: %(filename)s: %(message)s',
#                     level=logging.DEBUG)
# LOGGER = logging.getLogger()
# LOGGER.addFilter(UpperThresholdFilter(logging.CRITICAL))


def micro_benchmark(message, elapsed_time):
    """ Micro benchmarks. """
    logging.info('%s %s%s', message, str(elapsed_time), 's')
    print('CURRENT STATE %s %s%s' % (message, str(elapsed_time), 's'))
    return timeit.default_timer()


class Timeout:
    """ Timeout class using ALARM signal. """

    class Timeout(Exception):
        """ Timeout class throwing an exception. """

    def __init__(self, sec):
        self.sec = sec

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.raise_timeout)
        signal.alarm(self.sec)

    def __exit__(self, *args):
        signal.alarm(0)  # disable alarm

    def raise_timeout(self, *args):
        traceback.print_stack(limit=100)
        raise Timeout.Timeout()


def limit_memory(maxsize):
    """ Limiting the memory usage to maxsize (in bytes), soft limit. """

    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (maxsize, hard))
