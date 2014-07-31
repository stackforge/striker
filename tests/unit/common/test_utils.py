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

import unittest

import mock

from striker.common import utils

import tests


class CanonicalizePathTest(unittest.TestCase):
    @mock.patch('os.path.isabs', tests.fake_isabs)
    @mock.patch('os.path.join', tests.fake_join)
    @mock.patch('os.path.abspath', tests.fake_abspath)
    def test_absolute(self):
        result = utils.canonicalize_path('/foo/bar', '/bar/baz')

        self.assertEqual(result, '/bar/baz')

    @mock.patch('os.path.isabs', tests.fake_isabs)
    @mock.patch('os.path.join', tests.fake_join)
    @mock.patch('os.path.abspath', tests.fake_abspath)
    def test_relative(self):
        result = utils.canonicalize_path('/foo/bar', 'bar/baz')

        self.assertEqual(result, '/foo/bar/bar/baz')

    @mock.patch('os.path.isabs', tests.fake_isabs)
    @mock.patch('os.path.join', tests.fake_join)
    @mock.patch('os.path.abspath', tests.fake_abspath)
    def test_relative_with_cwd(self):
        result = utils.canonicalize_path('/foo/bar', './baz')

        self.assertEqual(result, '/foo/bar/baz')

    @mock.patch('os.path.isabs', tests.fake_isabs)
    @mock.patch('os.path.join', tests.fake_join)
    @mock.patch('os.path.abspath', tests.fake_abspath)
    def test_relative_with_parent(self):
        result = utils.canonicalize_path('/foo/bar', '../baz')

        self.assertEqual(result, '/foo/baz')


class BackoffTest(unittest.TestCase):
    @mock.patch('time.sleep')
    def test_backoff(self, mock_sleep):
        max_tries = 5

        for i, trial in enumerate(utils.backoff(max_tries)):
            self.assertEqual(i, trial)

            if i:
                mock_sleep.assert_called_once_with(1 << (i - 1))
            else:
                self.assertFalse(mock_sleep.called)

            mock_sleep.reset_mock()

        self.assertEqual(i, max_tries - 1)
