# Copyright 2014 Rackspace
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the
#    License. You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing,
#    software distributed under the License is distributed on an "AS
#    IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
#    express or implied. See the License for the specific language
#    governing permissions and limitations under the License.

import os
import subprocess
import unittest

import mock

from striker.common import utils
from striker.core import environment

import tests


class ExecResultTest(unittest.TestCase):
    def test_init_success(self):
        cmd = ['arg1', 'arg2 space', 'arg3"double', "arg4'single", 'arg5']
        cmd_text = 'arg1 "arg2 space" "arg3\\"double" "arg4\'single" arg5'
        result = environment.ExecResult(cmd, None, None, 0)

        self.assertEqual(result.cmd, cmd)
        self.assertEqual(result.cmd_text, cmd_text)
        self.assertEqual(result.stdout, None)
        self.assertEqual(result.stderr, None)
        self.assertEqual(result.return_code, 0)
        self.assertEqual(str(result), "'%s' succeeded" % cmd_text)

    def test_init_stdout(self):
        cmd = ['arg1', 'arg2 space', 'arg3"double', "arg4'single", 'arg5']
        cmd_text = 'arg1 "arg2 space" "arg3\\"double" "arg4\'single" arg5'
        result = environment.ExecResult(cmd, 'output', None, 0)

        self.assertEqual(result.cmd, cmd)
        self.assertEqual(result.cmd_text, cmd_text)
        self.assertEqual(result.stdout, 'output')
        self.assertEqual(result.stderr, None)
        self.assertEqual(result.return_code, 0)
        self.assertEqual(str(result), "'%s' said: output" % cmd_text)

    def test_init_stderr(self):
        cmd = ['arg1', 'arg2 space', 'arg3"double', "arg4'single", 'arg5']
        cmd_text = 'arg1 "arg2 space" "arg3\\"double" "arg4\'single" arg5'
        result = environment.ExecResult(cmd, 'output', 'error', 0)

        self.assertEqual(result.cmd, cmd)
        self.assertEqual(result.cmd_text, cmd_text)
        self.assertEqual(result.stdout, 'output')
        self.assertEqual(result.stderr, 'error')
        self.assertEqual(result.return_code, 0)
        self.assertEqual(str(result), "'%s' said: error" % cmd_text)

    def test_init_failure(self):
        cmd = ['arg1', 'arg2 space', 'arg3"double', "arg4'single", 'arg5']
        cmd_text = 'arg1 "arg2 space" "arg3\\"double" "arg4\'single" arg5'
        result = environment.ExecResult(cmd, 'output', 'error', 5)

        self.assertEqual(result.cmd, cmd)
        self.assertEqual(result.cmd_text, cmd_text)
        self.assertEqual(result.stdout, 'output')
        self.assertEqual(result.stderr, 'error')
        self.assertEqual(result.return_code, 5)
        self.assertEqual(str(result), "'%s' failed with return code 5" %
                         cmd_text)

    def test_true(self):
        result = environment.ExecResult(['cmd'], None, None, 0)

        self.assertTrue(result)

    def test_false(self):
        result = environment.ExecResult(['cmd'], None, None, 1)

        self.assertFalse(result)


class EnvironmentTest(unittest.TestCase):
    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(environment.Environment, 'chdir')
    def test_init_base(self, mock_chdir, mock_getcwd):
        env = environment.Environment('logger')

        self.assertEqual(env, {'TEST_VAR1': '1', 'TEST_VAR2': '2'})
        self.assertEqual(env.logger, 'logger')
        self.assertEqual(env.cwd, '/some/path')
        self.assertEqual(env.venv_home, None)
        self.assertFalse(mock_chdir.called)

    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(environment.Environment, 'chdir')
    def test_init_alt(self, mock_chdir, mock_getcwd):
        environ = {
            'TEST_VAR3': '3',
            'TEST_VAR4': '4',
        }
        env = environment.Environment('logger', environ, '/other/path',
                                      '/venv/home')

        self.assertEqual(env, environ)
        self.assertEqual(env.logger, 'logger')
        self.assertEqual(env.cwd, '/some/path')
        self.assertEqual(env.venv_home, '/venv/home')
        mock_chdir.assert_called_once_with('/other/path')

    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2')
    @mock.patch.object(os.path, 'join', tests.fake_join)
    @mock.patch.object(os, 'pathsep', ':')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(environment.Environment, 'chdir')
    @mock.patch.object(utils, 'canonicalize_path', return_value='/canon/path')
    @mock.patch.object(utils, 'backoff', return_value=[0])
    @mock.patch.object(subprocess, 'Popen', return_value=mock.Mock(**{
        'returncode': 0,
        'communicate.return_value': (None, None),
    }))
    def test_call_basic(self, mock_Popen, mock_backoff, mock_canonicalize_path,
                        mock_chdir, mock_getcwd):
        logger = mock.Mock()
        env = environment.Environment(logger)

        result = env(['test', 'one', 'two'])

        self.assertEqual(result.cmd, ['test', 'one', 'two'])
        self.assertEqual(result.stdout, None)
        self.assertEqual(result.stderr, None)
        self.assertEqual(result.return_code, 0)
        self.assertFalse(mock_canonicalize_path.called)
        mock_backoff.assert_called_once_with(1)
        mock_Popen.assert_called_once_with(
            ['test', 'one', 'two'], env=env, cwd='/some/path', close_fds=True)
        logger.assert_has_calls([
            mock.call.debug(
                "Executing command: ['test', 'one', 'two'] (cwd /some/path)"),
        ])
        self.assertEqual(len(logger.method_calls), 1)

    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(environment.Environment, 'chdir')
    @mock.patch.object(utils, 'canonicalize_path', return_value='/canon/path')
    @mock.patch.object(utils, 'backoff', return_value=[0])
    @mock.patch.object(subprocess, 'Popen', return_value=mock.Mock(**{
        'returncode': 0,
        'communicate.return_value': (None, None),
    }))
    def test_call_string(self, mock_Popen, mock_backoff,
                         mock_canonicalize_path, mock_chdir, mock_getcwd):
        logger = mock.Mock()
        env = environment.Environment(logger)

        result = env("test one two")

        self.assertEqual(result.cmd, ['test', 'one', 'two'])
        self.assertEqual(result.stdout, None)
        self.assertEqual(result.stderr, None)
        self.assertEqual(result.return_code, 0)
        self.assertFalse(mock_canonicalize_path.called)
        mock_backoff.assert_called_once_with(1)
        mock_Popen.assert_called_once_with(
            ['test', 'one', 'two'], env=env, cwd='/some/path', close_fds=True)
        logger.assert_has_calls([
            mock.call.debug(
                "Notice: splitting command string 'test one two'"),
            mock.call.debug(
                "Executing command: ['test', 'one', 'two'] (cwd /some/path)"),
        ])
        self.assertEqual(len(logger.method_calls), 2)

    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(environment.Environment, 'chdir')
    @mock.patch.object(utils, 'canonicalize_path', return_value='/canon/path')
    @mock.patch.object(utils, 'backoff', return_value=[0])
    @mock.patch.object(subprocess, 'Popen', return_value=mock.Mock(**{
        'returncode': 0,
        'communicate.return_value': (None, None),
    }))
    def test_call_cwd(self, mock_Popen, mock_backoff, mock_canonicalize_path,
                      mock_chdir, mock_getcwd):
        logger = mock.Mock()
        env = environment.Environment(logger)

        result = env(['test', 'one', 'two'], cwd='/other/path')

        self.assertEqual(result.cmd, ['test', 'one', 'two'])
        self.assertEqual(result.stdout, None)
        self.assertEqual(result.stderr, None)
        self.assertEqual(result.return_code, 0)
        mock_canonicalize_path.assert_called_once_with(
            '/some/path', '/other/path')
        mock_backoff.assert_called_once_with(1)
        mock_Popen.assert_called_once_with(
            ['test', 'one', 'two'], env=env, cwd='/canon/path', close_fds=True)
        logger.assert_has_calls([
            mock.call.debug(
                "Executing command: ['test', 'one', 'two'] (cwd /canon/path)"),
        ])
        self.assertEqual(len(logger.method_calls), 1)

    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(environment.Environment, 'chdir')
    @mock.patch.object(utils, 'canonicalize_path', return_value='/canon/path')
    @mock.patch.object(utils, 'backoff', return_value=[0])
    @mock.patch.object(subprocess, 'Popen', return_value=mock.Mock(**{
        'returncode': 0,
        'communicate.return_value': ('output', 'error'),
    }))
    def test_call_capture(self, mock_Popen, mock_backoff,
                          mock_canonicalize_path, mock_chdir, mock_getcwd):
        logger = mock.Mock()
        env = environment.Environment(logger)

        result = env(['test', 'one', 'two'], capture_output=True)

        self.assertEqual(result.cmd, ['test', 'one', 'two'])
        self.assertEqual(result.stdout, 'output')
        self.assertEqual(result.stderr, 'error')
        self.assertEqual(result.return_code, 0)
        self.assertFalse(mock_canonicalize_path.called)
        mock_backoff.assert_called_once_with(1)
        mock_Popen.assert_called_once_with(
            ['test', 'one', 'two'], env=env, cwd='/some/path', close_fds=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.assert_has_calls([
            mock.call.debug(
                "Executing command: ['test', 'one', 'two'] (cwd /some/path)"),
        ])
        self.assertEqual(len(logger.method_calls), 1)

    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(environment.Environment, 'chdir')
    @mock.patch.object(utils, 'canonicalize_path', return_value='/canon/path')
    @mock.patch.object(utils, 'backoff', return_value=[0])
    @mock.patch.object(subprocess, 'Popen', return_value=mock.Mock(**{
        'returncode': 1,
        'communicate.return_value': (None, None),
    }))
    def test_call_failure_raise(self, mock_Popen, mock_backoff,
                                mock_canonicalize_path, mock_chdir,
                                mock_getcwd):
        logger = mock.Mock()
        env = environment.Environment(logger)

        try:
            result = env(['test', 'one', 'two'])
        except environment.ExecResult as exc:
            self.assertEqual(exc.cmd, ['test', 'one', 'two'])
            self.assertEqual(exc.stdout, None)
            self.assertEqual(exc.stderr, None)
            self.assertEqual(exc.return_code, 1)
        else:
            self.fail("Expected ExecResult to be raised")

        self.assertFalse(mock_canonicalize_path.called)
        mock_backoff.assert_called_once_with(1)
        mock_Popen.assert_called_once_with(
            ['test', 'one', 'two'], env=env, cwd='/some/path', close_fds=True)
        logger.assert_has_calls([
            mock.call.debug(
                "Executing command: ['test', 'one', 'two'] (cwd /some/path)"),
        ])
        self.assertEqual(len(logger.method_calls), 1)

    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(environment.Environment, 'chdir')
    @mock.patch.object(utils, 'canonicalize_path', return_value='/canon/path')
    @mock.patch.object(utils, 'backoff', return_value=[0])
    @mock.patch.object(subprocess, 'Popen', return_value=mock.Mock(**{
        'returncode': 1,
        'communicate.return_value': (None, None),
    }))
    def test_call_failure_noraise(self, mock_Popen, mock_backoff,
                                  mock_canonicalize_path, mock_chdir,
                                  mock_getcwd):
        logger = mock.Mock()
        env = environment.Environment(logger)

        result = env(['test', 'one', 'two'], do_raise=False)

        self.assertEqual(result.cmd, ['test', 'one', 'two'])
        self.assertEqual(result.stdout, None)
        self.assertEqual(result.stderr, None)
        self.assertEqual(result.return_code, 1)
        self.assertFalse(mock_canonicalize_path.called)
        mock_backoff.assert_called_once_with(1)
        mock_Popen.assert_called_once_with(
            ['test', 'one', 'two'], env=env, cwd='/some/path', close_fds=True)
        logger.assert_has_calls([
            mock.call.debug(
                "Executing command: ['test', 'one', 'two'] (cwd /some/path)"),
        ])
        self.assertEqual(len(logger.method_calls), 1)

    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(environment.Environment, 'chdir')
    @mock.patch.object(utils, 'canonicalize_path', return_value='/canon/path')
    @mock.patch.object(utils, 'backoff', return_value=[0])
    @mock.patch.object(subprocess, 'Popen', return_value=mock.Mock(**{
        'returncode': 0,
        'communicate.return_value': ('output', 'error'),
    }))
    def test_call_retry_success(self, mock_Popen, mock_backoff,
                                mock_canonicalize_path, mock_chdir,
                                mock_getcwd):
        logger = mock.Mock()
        env = environment.Environment(logger)
        retry = mock.Mock(return_value=True)

        result = env(['test', 'one', 'two'], retry=retry)

        self.assertEqual(result.cmd, ['test', 'one', 'two'])
        self.assertEqual(result.stdout, 'output')
        self.assertEqual(result.stderr, 'error')
        self.assertEqual(result.return_code, 0)
        self.assertFalse(mock_canonicalize_path.called)
        mock_backoff.assert_called_once_with(5)
        mock_Popen.assert_called_once_with(
            ['test', 'one', 'two'], env=env, cwd='/some/path', close_fds=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.assert_has_calls([
            mock.call.debug(
                "Executing command: ['test', 'one', 'two'] (cwd /some/path)"),
        ])
        self.assertEqual(len(logger.method_calls), 1)
        self.assertFalse(retry.called)

    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(environment.Environment, 'chdir')
    @mock.patch.object(utils, 'canonicalize_path', return_value='/canon/path')
    @mock.patch.object(utils, 'backoff', return_value=[0])
    @mock.patch.object(subprocess, 'Popen', return_value=mock.Mock(**{
        'returncode': 0,
        'communicate.return_value': (None, None),
    }))
    def test_call_retry_success_badretries(self, mock_Popen, mock_backoff,
                                           mock_canonicalize_path, mock_chdir,
                                           mock_getcwd):
        logger = mock.Mock()
        env = environment.Environment(logger)
        retry = mock.Mock(return_value=True)

        result = env(['test', 'one', 'two'], retry=retry, max_tries=-1)

        self.assertEqual(result.cmd, ['test', 'one', 'two'])
        self.assertEqual(result.stdout, None)
        self.assertEqual(result.stderr, None)
        self.assertEqual(result.return_code, 0)
        self.assertFalse(mock_canonicalize_path.called)
        mock_backoff.assert_called_once_with(1)
        mock_Popen.assert_called_once_with(
            ['test', 'one', 'two'], env=env, cwd='/some/path', close_fds=True)
        logger.assert_has_calls([
            mock.call.debug(
                "Executing command: ['test', 'one', 'two'] (cwd /some/path)"),
        ])
        self.assertEqual(len(logger.method_calls), 1)
        self.assertFalse(retry.called)

    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(environment.Environment, 'chdir')
    @mock.patch.object(utils, 'canonicalize_path', return_value='/canon/path')
    @mock.patch.object(utils, 'backoff', return_value=[0, 1, 2, 3, 4, 5, 6])
    @mock.patch.object(subprocess, 'Popen', return_value=mock.Mock(**{
        'returncode': 0,
        'communicate.return_value': ('output', 'error'),
    }))
    def test_call_retry_withtries(self, mock_Popen, mock_backoff,
                                  mock_canonicalize_path, mock_chdir,
                                  mock_getcwd):
        logger = mock.Mock()
        env = environment.Environment(logger)
        retry = mock.Mock(return_value=True)
        exec_results = [
            mock.Mock(__nonzero__=mock.Mock(return_value=False),
                      __bool__=mock.Mock(return_value=False)),
            mock.Mock(__nonzero__=mock.Mock(return_value=False),
                      __bool__=mock.Mock(return_value=False)),
            mock.Mock(__nonzero__=mock.Mock(return_value=True),
                      __bool__=mock.Mock(return_value=True)),
        ]

        with mock.patch.object(environment, 'ExecResult',
                               side_effect=exec_results) as mock_ExecResult:
            result = env(['test', 'one', 'two'], retry=retry, max_tries=7)

        self.assertEqual(result, exec_results[-1])
        self.assertFalse(mock_canonicalize_path.called)
        mock_backoff.assert_called_once_with(7)
        mock_Popen.assert_has_calls([
            mock.call(['test', 'one', 'two'], env=env, cwd='/some/path',
                      close_fds=True, stdout=subprocess.PIPE,
                      stderr=subprocess.PIPE),
            mock.call(['test', 'one', 'two'], env=env, cwd='/some/path',
                      close_fds=True, stdout=subprocess.PIPE,
                      stderr=subprocess.PIPE),
            mock.call(['test', 'one', 'two'], env=env, cwd='/some/path',
                      close_fds=True, stdout=subprocess.PIPE,
                      stderr=subprocess.PIPE),
        ])
        self.assertEqual(mock_Popen.call_count, 3)
        mock_ExecResult.assert_has_calls([
            mock.call(['test', 'one', 'two'], 'output', 'error', 0),
            mock.call(['test', 'one', 'two'], 'output', 'error', 0),
            mock.call(['test', 'one', 'two'], 'output', 'error', 0),
        ])
        self.assertEqual(mock_ExecResult.call_count, 3)
        logger.assert_has_calls([
            mock.call.debug(
                "Executing command: ['test', 'one', 'two'] (cwd /some/path)"),
            mock.call.warn('Failure caught; retrying command (try #2)'),
            mock.call.warn('Failure caught; retrying command (try #3)'),
        ])
        self.assertEqual(len(logger.method_calls), 3)
        retry.assert_has_calls([mock.call(res) for res in exec_results[:-1]])
        self.assertEqual(retry.call_count, len(exec_results) - 1)

    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(environment.Environment, 'chdir')
    @mock.patch.object(utils, 'canonicalize_path', return_value='/canon/path')
    @mock.patch.object(utils, 'backoff', return_value=[0, 1])
    @mock.patch.object(subprocess, 'Popen', return_value=mock.Mock(**{
        'returncode': 0,
        'communicate.return_value': ('output', 'error'),
    }))
    def test_call_retry_withtries_failure(self, mock_Popen, mock_backoff,
                                          mock_canonicalize_path, mock_chdir,
                                          mock_getcwd):
        logger = mock.Mock()
        env = environment.Environment(logger)
        retry = mock.Mock(return_value=True)
        exec_results = [
            mock.Mock(__nonzero__=mock.Mock(return_value=False),
                      __bool__=mock.Mock(return_value=False)),
            mock.Mock(__nonzero__=mock.Mock(return_value=False),
                      __bool__=mock.Mock(return_value=False)),
            mock.Mock(__nonzero__=mock.Mock(return_value=True),
                      __bool__=mock.Mock(return_value=True)),
        ]

        with mock.patch.object(environment, 'ExecResult',
                               side_effect=exec_results) as mock_ExecResult:
            result = env(['test', 'one', 'two'], retry=retry, max_tries=2,
                         do_raise=False)

        self.assertEqual(result, exec_results[-2])
        self.assertFalse(mock_canonicalize_path.called)
        mock_backoff.assert_called_once_with(2)
        mock_Popen.assert_has_calls([
            mock.call(['test', 'one', 'two'], env=env, cwd='/some/path',
                      close_fds=True, stdout=subprocess.PIPE,
                      stderr=subprocess.PIPE),
            mock.call(['test', 'one', 'two'], env=env, cwd='/some/path',
                      close_fds=True, stdout=subprocess.PIPE,
                      stderr=subprocess.PIPE),
        ])
        self.assertEqual(mock_Popen.call_count, 2)
        mock_ExecResult.assert_has_calls([
            mock.call(['test', 'one', 'two'], 'output', 'error', 0),
            mock.call(['test', 'one', 'two'], 'output', 'error', 0),
        ])
        self.assertEqual(mock_ExecResult.call_count, 2)
        logger.assert_has_calls([
            mock.call.debug(
                "Executing command: ['test', 'one', 'two'] (cwd /some/path)"),
            mock.call.warn('Failure caught; retrying command (try #2)'),
            mock.call.warn('Unable to retry: too many attempts'),
        ])
        self.assertEqual(len(logger.method_calls), 3)
        retry.assert_has_calls([mock.call(res) for res in exec_results[:-2]])
        self.assertEqual(retry.call_count, len(exec_results) - 1)

    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(utils, 'canonicalize_path', return_value='/canon/path')
    def test_chdir(self, mock_canonicalize_path, mock_getcwd):
        with mock.patch.object(environment.Environment, 'chdir'):
            env = environment.Environment('logger')

        result = env.chdir('test/directory')

        self.assertEqual(result, '/canon/path')
        self.assertEqual(env.cwd, '/canon/path')
        mock_canonicalize_path.assert_called_once_with(
            '/some/path', 'test/directory')

    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2',
                     PATH='/bin')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(os.path, 'exists', return_value=False)
    @mock.patch('shutil.rmtree')
    @mock.patch.object(environment.Environment, 'chdir')
    @mock.patch.object(environment.Environment, '__call__')
    @mock.patch.object(utils, 'canonicalize_path', return_value='/canon/path')
    def test_create_venv_basic(self, mock_canonicalize_path, mock_call,
                               mock_chdir, mock_rmtree, mock_exists,
                               mock_getcwd):
        logger = mock.Mock()
        env = environment.Environment(logger)
        expected = dict(env)
        expected.update({
            'VIRTUAL_ENV': '/canon/path',
            'PATH': '/canon/path/bin:/bin',
        })
        mock_chdir.reset_mock()

        new_env = env.create_venv('venv/dir')

        self.assertNotEqual(id(new_env), id(env))
        self.assertTrue(isinstance(new_env, environment.Environment))
        self.assertEqual(new_env, expected)
        self.assertEqual(new_env.logger, logger)
        self.assertEqual(new_env.cwd, '/some/path')
        self.assertEqual(new_env.venv_home, '/canon/path')
        mock_canonicalize_path.assert_called_once_with(
            '/some/path', 'venv/dir')
        mock_exists.assert_called_once_with('/canon/path')
        self.assertFalse(mock_rmtree.called)
        mock_call.assert_called_once_with(['virtualenv', '/canon/path'])
        mock_chdir.assert_called_once_with('/canon/path')
        logger.assert_has_calls([
            mock.call.debug('Preparing virtual environment /canon/path'),
            mock.call.info('Creating virtual environment /canon/path'),
        ])
        self.assertEqual(len(logger.method_calls), 2)

    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2',
                     PATH='/bin')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(os.path, 'exists', return_value=False)
    @mock.patch('shutil.rmtree')
    @mock.patch.object(environment.Environment, 'chdir')
    @mock.patch.object(environment.Environment, '__call__')
    @mock.patch.object(utils, 'canonicalize_path', return_value='/canon/path')
    def test_create_venv_update(self, mock_canonicalize_path, mock_call,
                                mock_chdir, mock_rmtree, mock_exists,
                                mock_getcwd):
        logger = mock.Mock()
        env = environment.Environment(logger)
        expected = dict(env)
        expected.update({
            'VIRTUAL_ENV': 'bah',
            'PATH': '/canon/path/bin:/bin',
            'a': 'foo',
        })
        mock_chdir.reset_mock()

        new_env = env.create_venv('venv/dir', VIRTUAL_ENV='bah', a='foo')

        self.assertNotEqual(id(new_env), id(env))
        self.assertTrue(isinstance(new_env, environment.Environment))
        self.assertEqual(new_env, expected)
        self.assertEqual(new_env.logger, logger)
        self.assertEqual(new_env.cwd, '/some/path')
        self.assertEqual(new_env.venv_home, '/canon/path')
        mock_canonicalize_path.assert_called_once_with(
            '/some/path', 'venv/dir')
        mock_exists.assert_called_once_with('/canon/path')
        self.assertFalse(mock_rmtree.called)
        mock_call.assert_called_once_with(['virtualenv', '/canon/path'])
        mock_chdir.assert_called_once_with('/canon/path')
        logger.assert_has_calls([
            mock.call.debug('Preparing virtual environment /canon/path'),
            mock.call.info('Creating virtual environment /canon/path'),
        ])
        self.assertEqual(len(logger.method_calls), 2)

    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2',
                     PATH='/bin')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(os.path, 'exists', return_value=True)
    @mock.patch('shutil.rmtree')
    @mock.patch.object(environment.Environment, 'chdir')
    @mock.patch.object(environment.Environment, '__call__')
    @mock.patch.object(utils, 'canonicalize_path', return_value='/canon/path')
    def test_create_venv_exists(self, mock_canonicalize_path, mock_call,
                                mock_chdir, mock_rmtree, mock_exists,
                                mock_getcwd):
        logger = mock.Mock()
        env = environment.Environment(logger)
        expected = dict(env)
        expected.update({
            'VIRTUAL_ENV': '/canon/path',
            'PATH': '/canon/path/bin:/bin',
        })
        mock_chdir.reset_mock()

        new_env = env.create_venv('venv/dir')

        self.assertNotEqual(id(new_env), id(env))
        self.assertTrue(isinstance(new_env, environment.Environment))
        self.assertEqual(new_env, expected)
        self.assertEqual(new_env.logger, logger)
        self.assertEqual(new_env.cwd, '/some/path')
        self.assertEqual(new_env.venv_home, '/canon/path')
        mock_canonicalize_path.assert_called_once_with(
            '/some/path', 'venv/dir')
        mock_exists.assert_called_once_with('/canon/path')
        self.assertFalse(mock_rmtree.called)
        self.assertFalse(mock_call.called)
        mock_chdir.assert_called_once_with('/canon/path')
        logger.assert_has_calls([
            mock.call.debug('Preparing virtual environment /canon/path'),
            mock.call.info('Using existing virtual environment /canon/path'),
        ])
        self.assertEqual(len(logger.method_calls), 2)

    @mock.patch.dict(os.environ, clear=True, TEST_VAR1='1', TEST_VAR2='2',
                     PATH='/bin')
    @mock.patch.object(os, 'getcwd', return_value='/some/path')
    @mock.patch.object(os.path, 'exists', return_value=True)
    @mock.patch('shutil.rmtree')
    @mock.patch.object(environment.Environment, 'chdir')
    @mock.patch.object(environment.Environment, '__call__')
    @mock.patch.object(utils, 'canonicalize_path', return_value='/canon/path')
    def test_create_venv_rebuild(self, mock_canonicalize_path, mock_call,
                                 mock_chdir, mock_rmtree, mock_exists,
                                 mock_getcwd):
        logger = mock.Mock()
        env = environment.Environment(logger)
        expected = dict(env)
        expected.update({
            'VIRTUAL_ENV': '/canon/path',
            'PATH': '/canon/path/bin:/bin',
        })
        mock_chdir.reset_mock()

        new_env = env.create_venv('venv/dir', True)

        self.assertNotEqual(id(new_env), id(env))
        self.assertTrue(isinstance(new_env, environment.Environment))
        self.assertEqual(new_env, expected)
        self.assertEqual(new_env.logger, logger)
        self.assertEqual(new_env.cwd, '/some/path')
        self.assertEqual(new_env.venv_home, '/canon/path')
        mock_canonicalize_path.assert_called_once_with(
            '/some/path', 'venv/dir')
        mock_exists.assert_called_once_with('/canon/path')
        mock_rmtree.assert_called_once_with('/canon/path')
        mock_call.assert_called_once_with(['virtualenv', '/canon/path'])
        mock_chdir.assert_called_once_with('/canon/path')
        logger.assert_has_calls([
            mock.call.debug('Preparing virtual environment /canon/path'),
            mock.call.info('Destroying old virtual environment /canon/path'),
            mock.call.info('Creating virtual environment /canon/path'),
        ])
        self.assertEqual(len(logger.method_calls), 3)
