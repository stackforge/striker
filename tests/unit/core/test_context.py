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

from striker.core import context
from striker.core import environment


class ContextTest(unittest.TestCase):
    def test_init_base(self):
        ctxt = context.Context('/path/to/workspace', 'config', 'logger')

        self.assertEqual(ctxt.workspace, '/path/to/workspace')
        self.assertEqual(ctxt.config, 'config')
        self.assertEqual(ctxt.logger, 'logger')
        self.assertEqual(ctxt.debug, False)
        self.assertEqual(ctxt.dry_run, False)
        self.assertEqual(ctxt._extras, {})
        self.assertEqual(ctxt._environ, None)

    def test_init_alt(self):
        ctxt = context.Context('/path/to/workspace', 'config', 'logger',
                               debug=True, dry_run=True, accounts='accounts',
                               other='other')

        self.assertEqual(ctxt.workspace, '/path/to/workspace')
        self.assertEqual(ctxt.config, 'config')
        self.assertEqual(ctxt.logger, 'logger')
        self.assertEqual(ctxt.debug, True)
        self.assertEqual(ctxt.dry_run, True)
        self.assertEqual(ctxt._extras, {
            'accounts': 'accounts',
            'other': 'other',
        })
        self.assertEqual(ctxt._environ, None)

    def test_getattr_exists(self):
        ctxt = context.Context('/path/to/workspace', 'config', 'logger',
                               attr='value')

        self.assertEqual(ctxt.attr, 'value')

    def test_getattr_noexist(self):
        ctxt = context.Context('/path/to/workspace', 'config', 'logger',
                               attr='value')

        self.assertRaises(AttributeError, lambda: ctxt.other)

    @mock.patch.object(environment, 'Environment', return_value='environ')
    def test_environ_cached(self, mock_Environment):
        ctxt = context.Context('/path/to/workspace', 'config', 'logger')
        ctxt._environ = 'cached'

        self.assertEqual(ctxt.environ, 'cached')
        self.assertEqual(ctxt._environ, 'cached')
        self.assertFalse(mock_Environment.called)

    @mock.patch.object(environment, 'Environment', return_value='environ')
    def test_environ_uncached(self, mock_Environment):
        ctxt = context.Context('/path/to/workspace', 'config', 'logger')

        self.assertEqual(ctxt.environ, 'environ')
        self.assertEqual(ctxt._environ, 'environ')
        mock_Environment.assert_called_once_with('logger')
