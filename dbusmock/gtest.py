#!/usr/bin/python3

import os
import sys
import subprocess
import functools
from future.utils import with_metaclass

if sys.version_info[0] < 3:
    PIPE_DEVNULL = open(os.devnull, 'wb')
else:
    PIPE_DEVNULL = subprocess.DEVNULL


class _GTestSingleProp(object):
    """Property which creates a bound method for calling the specified test."""
    def __init__(self, test):
        self.test = test

    @staticmethod
    def __func(self, test):
        self._gtest_single(test)

    def __get__(self, obj, cls):
        bound_method = self.__func.__get__(obj, cls)
        partial_method = functools.partial(bound_method, self.test)
        partial_method.__doc__ = bound_method.__doc__

        return partial_method


class _GTestMeta(type):
    def __new__(cls, name, bases, namespace, **kwds):
        result = type.__new__(cls, name, bases, dict(namespace))

        if result.g_test_exe is not None:
            try:
                _GTestMeta.make_tests(result.g_test_exe, result)
            except Exception as e:
                print('')
                print(e)
                print('Error generating separate test funcs, will call binary once.')
                result.test_all = result._gtest_all

        return result

    @staticmethod
    def make_tests(exe, result):
        test = subprocess.Popen([exe, '-l'], stdout=subprocess.PIPE, stderr=PIPE_DEVNULL)
        stdout, stderr = test.communicate()

        if test.returncode != 0:
            raise AssertionError('Execution of GTest executable to query the tests returned non-zero exit code!')

        stdout = stdout.decode('utf-8')

        for i, test in enumerate(stdout.split('\n')):
            if not test:
                continue

            # Number it and make sure the function name is prefixed with 'test'.
            # Keep the rest as is, we don't care about the fact that the function
            # names cannot be typed in.
            name = 'test_%03d_' % (i + 1) + test
            setattr(result, name, _GTestSingleProp(test))


class GTest(with_metaclass(_GTestMeta)):
    """Helper class to run GLib test. A test function will be created for each
    test from the executable.

    Use by using this class as a mixin and setting g_test_exe to an appropriate
    value.
    """

    #: The GTest based executable
    g_test_exe = None
    #: Timeout when running a single test, only set when using python 3!
    g_test_single_timeout = None
    #: Timeout when running all tests in one go, only set when using python 3!
    g_test_all_timeout = None

    def _gtest_single(self, test):
        assert(test)
        p = subprocess.Popen([self.g_test_exe, '-q', '-p', test], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            if self.g_test_single_timeout:
                stdout, stderr = p.communicate(timeout=self.g_test_single_timeout)
            else:
                stdout, stderr = p.communicate()
        except subprocess.TimeoutExpired:
            p.kill()
            stdout, stderr = p.communicate()
            stdout += b'\n\nTest was aborted due to timeout'

        try:
            stdout = stdout.decode('utf-8')
        except UnicodeDecodeError:
            pass

        if p.returncode != 0:
            self.fail(stdout)

    def _gtest_all(self):
        if self.g_test_all_timeout:
            subprocess.check_call([self.g_test_exe], timeout=self.g_test_all_timeout)
        else:
            subprocess.check_call([self.g_test_exe])
