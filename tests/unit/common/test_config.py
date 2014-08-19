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

import collections
import contextlib
import fnmatch
import unittest

import mock
from six.moves import builtins

from striker.common import config

import tests


class SchemaInvalidateTest(unittest.TestCase):
    def test_base(self):
        parent1 = mock.Mock(spec=['_parents', '_schema_cache'],
                            _schema_cache='parent1_cached',
                            _parents=set(['foo']))
        parent2 = mock.Mock(spec=['_parents'], _parents=set([parent1]))
        parent3 = mock.Mock(spec=['_schema_cache', '_parents'],
                            _schema_cache='parent3_cached', _parents=set())
        parent4 = mock.Mock(spec=['_schema_cache', '_parents'],
                            _schema_cache='parent4_cached',
                            _parents=set([parent2]))
        child = mock.Mock(spec=['_parents', '_schema_cache'],
                          _schema_cache='child_cached',
                          _parents=set([parent4, parent3]))

        config._schema_invalidate(child)

        self.assertEqual(child._schema_cache, None)
        self.assertEqual(parent1._schema_cache, 'parent1_cached')
        self.assertEqual(parent3._schema_cache, None)
        self.assertEqual(parent4._schema_cache, None)

    def test_parent_loop(self):
        # Should never happen, but just in case...
        parent1 = mock.Mock(spec=['_parents', '_schema_cache'],
                            _schema_cache='parent1_cached',
                            _parents=set())
        parent2 = mock.Mock(spec=['_parents', '_schema_cache'],
                            _schema_cache='parent2_cached',
                            _parents=set([parent1]))
        parent1._parents.add(parent2)
        child = mock.Mock(spec=['_parents', '_schema_cache'],
                          _schema_cache='child_cached',
                          _parents=set([parent2]))

        config._schema_invalidate(child)

        self.assertEqual(child._schema_cache, None)
        self.assertEqual(parent1._schema_cache, None)
        self.assertEqual(parent2._schema_cache, None)


class SchemaTest(unittest.TestCase):
    def test_get_cached(self):
        cls = mock.Mock(
            __doc__='',
            _keys={},
            _schema_raw={},
            _schema_cache='cached',
        )
        schema = config.Schema()

        result = schema.__get__(None, cls)

        self.assertEqual(result, 'cached')
        self.assertEqual(cls._schema_cache, 'cached')

    def test_get_uncached(self):
        opt1 = mock.Mock(
            spec=config.Option,
            _parents=set(),
            __schema__='opt1_sch',
            __default__='default',
        )
        opt2 = mock.Mock(
            spec=config.Option,
            _parents=set(),
            __schema__='opt2_sch',
            __default__=config._unset,
        )
        cls = mock.Mock(
            __doc__='description',
            _keys={
                'option1': opt1,
                'option2': opt2,
            },
            _schema_raw={'extra': 'data'},
            _schema_cache=None,
        )
        schema = config.Schema()

        result = schema.__get__(None, cls)

        expected = {
            'description': 'description',
            'extra': 'data',
            'properties': {
                'option1': 'opt1_sch',
                'option2': 'opt2_sch',
            },
            'required': ['option2'],
        }
        self.assertEqual(result, expected)
        self.assertEqual(cls._schema_cache, expected)

    def test_get_uncached_nodoc(self):
        opt1 = mock.Mock(
            spec=config.Option,
            _parents=set(),
            __schema__='opt1_sch',
            __default__='default',
        )
        opt2 = mock.Mock(
            spec=config.Option,
            _parents=set(),
            __schema__='opt2_sch',
            __default__=config._unset,
        )
        cls = mock.Mock(
            __doc__=None,
            _keys={
                'option1': opt1,
                'option2': opt2,
            },
            _schema_raw={'extra': 'data'},
            _schema_cache=None,
        )
        schema = config.Schema()

        result = schema.__get__(None, cls)

        expected = {
            'extra': 'data',
            'properties': {
                'option1': 'opt1_sch',
                'option2': 'opt2_sch',
            },
            'required': ['option2'],
        }
        self.assertEqual(result, expected)
        self.assertEqual(cls._schema_cache, expected)

    def test_set(self):
        schema = config.Schema()

        self.assertRaises(AttributeError, schema.__set__, 'obj', 'value')

    def test_delete(self):
        schema = config.Schema()

        self.assertRaises(AttributeError, schema.__delete__, 'obj')


class BindingTest(unittest.TestCase):
    def test_init(self):
        binding = config.Binding('attr', 'key', 'option')

        self.assertEqual(binding.__attr__, 'attr')
        self.assertEqual(binding.__key__, 'key')
        self.assertEqual(binding.__option__, 'option')

    def test_call_cached(self):
        option = mock.Mock(return_value='converted', __default__='default')
        obj = mock.Mock(_raw={'key': 'config'}, _xlated={'attr': 'cached'})
        binding = config.Binding('attr', 'key', option)

        result = binding(obj)

        self.assertEqual(result, 'cached')
        self.assertEqual(obj._raw, {'key': 'config'})
        self.assertEqual(obj._xlated, {'attr': 'cached'})
        self.assertFalse(option.called)

    def test_call_translate(self):
        option = mock.Mock(return_value='converted', __default__='default')
        obj = mock.Mock(_raw={'key': 'config'}, _xlated={})
        binding = config.Binding('attr', 'key', option)

        result = binding(obj)

        self.assertEqual(result, 'converted')
        self.assertEqual(obj._raw, {'key': 'config'})
        self.assertEqual(obj._xlated, {'attr': 'converted'})
        option.assert_called_once_with('config')

    def test_call_default(self):
        option = mock.Mock(return_value='converted', __default__='default')
        obj = mock.Mock(_raw={}, _xlated={})
        binding = config.Binding('attr', 'key', option)

        result = binding(obj)

        self.assertEqual(result, 'default')
        self.assertEqual(obj._raw, {})
        self.assertEqual(obj._xlated, {'attr': 'default'})
        self.assertFalse(option.called)

    def test_call_unset(self):
        option = mock.Mock(return_value='converted', __default__=config._unset)
        obj = mock.Mock(_raw={}, _xlated={})
        binding = config.Binding('attr', 'key', option)

        self.assertRaises(AttributeError, binding, obj)
        self.assertEqual(obj._raw, {})
        self.assertEqual(obj._xlated, {})
        self.assertFalse(option.called)

    def test_getattr(self):
        option = mock.Mock(opt_attr='spam')
        binding = config.Binding('attr', 'key', option)

        self.assertEqual(binding.opt_attr, 'spam')

    def test_contains(self):
        option = mock.MagicMock()
        option.__contains__.return_value = True
        binding = config.Binding('attr', 'key', option)

        self.assertTrue('spam' in binding)

    def test_getitem(self):
        option = mock.MagicMock()
        option.__getitem__.return_value = 'value'
        binding = config.Binding('attr', 'key', option)

        self.assertEqual(binding['spam'], 'value')

    @mock.patch.object(config.Binding, '__call__', return_value='spam')
    def test_get_cls(self, mock_call):
        binding = config.Binding('attr', 'key', 'option')

        result = binding.__get__(None, 'class')

        self.assertEqual(result, binding)
        self.assertFalse(mock_call.called)

    @mock.patch.object(config.Binding, '__call__', return_value='spam')
    def test_get_obj(self, mock_call):
        binding = config.Binding('attr', 'key', 'option')

        result = binding.__get__('obj', 'class')

        self.assertEqual(result, 'spam')
        mock_call.assert_called_once_with('obj')

    def test_set(self):
        binding = config.Binding('attr', 'key', 'option')

        self.assertRaises(AttributeError, binding.__set__, 'obj', 'value')

    def test_delete(self):
        binding = config.Binding('attr', 'key', 'option')

        self.assertRaises(AttributeError, binding.__delete__, 'obj')


class COWDictTest(unittest.TestCase):
    def test_init_base(self):
        result = config.COWDict('orig')

        self.assertEqual(result._orig, 'orig')
        self.assertEqual(result._new, {})
        self.assertEqual(result._lookaside, {})
        self.assertEqual(result._root, None)
        self.assertEqual(result._children, [])

    def test_init_root(self):
        root = mock.Mock(_children=[1, 2])

        result = config.COWDict('orig', root)

        self.assertEqual(result._orig, 'orig')
        self.assertEqual(result._new, {})
        self.assertEqual(result._lookaside, {})
        self.assertEqual(result._root, root)
        self.assertEqual(result._children, [])
        self.assertEqual(root._children, [1, 2, result])

    def test_getitem_lookaside(self):
        orig = {'a': 1, 'b': 2, 'c': 3}
        cowd = config.COWDict(orig)
        cowd._lookaside['b'] = 'lookaside'

        self.assertEqual(cowd['b'], 'lookaside')

    def test_getitem_unset(self):
        orig = {'a': 1, 'b': 2, 'c': 3}
        cowd = config.COWDict(orig)

        self.assertRaises(KeyError, lambda: cowd['d'])

    def test_getitem_deleted(self):
        orig = {'a': 1, 'b': 2, 'c': 3}
        cowd = config.COWDict(orig)
        cowd._new['b'] = config._unset

        self.assertRaises(KeyError, lambda: cowd['b'])

    def test_getitem_dict(self):
        orig = {'a': 1, 'b': 2, 'c': {'ca': 31, 'cb': 32, 'cc': 33}}
        cowd = config.COWDict(orig)

        result = cowd['c']

        self.assertTrue(isinstance(result, config.COWDict))
        self.assertEqual(id(result._orig), id(orig['c']))
        self.assertEqual(result._root, cowd)
        self.assertEqual(cowd._lookaside, {'c': result})

    def test_getitem_subdict(self):
        root = mock.Mock(_children=[])
        orig = {'a': 1, 'b': 2, 'c': {'ca': 31, 'cb': 32, 'cc': 33}}
        cowd = config.COWDict(orig, root)

        result = cowd['c']

        self.assertTrue(isinstance(result, config.COWDict))
        self.assertEqual(id(result._orig), id(orig['c']))
        self.assertEqual(result._root, root)
        self.assertEqual(cowd._lookaside, {'c': result})

    def test_getitem_base(self):
        orig = {'a': 1, 'b': 2, 'c': 3}
        cowd = config.COWDict(orig)

        self.assertEqual(cowd['b'], 2)

    def test_getitem_overridden(self):
        orig = {'a': 1, 'b': 2, 'c': 3}
        cowd = config.COWDict(orig)
        cowd._new['b'] = 4

        self.assertEqual(cowd['b'], 4)

    def test_setitem_base(self):
        orig = {'a': 1, 'b': 2, 'c': 3}
        cowd = config.COWDict(orig)
        cowd._lookaside['b'] = 'lookaside'

        cowd['b'] = 4

        self.assertEqual(cowd._orig, {'a': 1, 'b': 2, 'c': 3})
        self.assertEqual(cowd._new, {'b': 4})
        self.assertEqual(cowd._lookaside, {})

    def test_setitem_reset(self):
        orig = {'a': 1, 'b': 2, 'c': 3}
        cowd = config.COWDict(orig)
        cowd._lookaside['b'] = 'lookaside'

        cowd['b'] = 2

        self.assertEqual(cowd._orig, {'a': 1, 'b': 2, 'c': 3})
        self.assertEqual(cowd._new, {})
        self.assertEqual(cowd._lookaside, {})

    def test_delitem_base(self):
        orig = {'a': 1, 'b': 2, 'c': 3}
        cowd = config.COWDict(orig)
        cowd._new['d'] = 4
        cowd._lookaside['d'] = 'lookaside'

        del cowd['d']

        self.assertEqual(cowd._orig, {'a': 1, 'b': 2, 'c': 3})
        self.assertEqual(cowd._new, {})
        self.assertEqual(cowd._lookaside, {})

    def test_delitem_override(self):
        orig = {'a': 1, 'b': 2, 'c': 3}
        cowd = config.COWDict(orig)
        cowd._new['b'] = 4
        cowd._lookaside['b'] = 'lookaside'

        del cowd['b']

        self.assertEqual(cowd._orig, {'a': 1, 'b': 2, 'c': 3})
        self.assertEqual(cowd._new, {'b': config._unset})
        self.assertEqual(cowd._lookaside, {})

    def test_iter(self):
        orig = {'a': 1, 'b': 2, 'c': 3}
        cowd = config.COWDict(orig)
        cowd._new = {'b': config._unset, 'd': 4}

        result = sorted(iter(cowd))

        self.assertEqual(result, ['a', 'c', 'd'])

    def test_len(self):
        orig = {'a': 1, 'b': 2, 'c': 3}
        cowd = config.COWDict(orig)
        cowd._new = {'b': config._unset, 'd': 4}

        self.assertEqual(len(cowd), 3)

    def test_keys(self):
        orig = {'a': 1, 'b': 2, 'c': 3}
        cowd = config.COWDict(orig)
        cowd._new = {'b': config._unset, 'd': 4}

        result = cowd._keys()

        self.assertEqual(result, set(['a', 'b', 'c', 'd']))

    def test_apply_internal(self):
        orig = {'a': 1, 'b': 2, 'c': 3}
        cowd = config.COWDict(orig)
        cowd._new = {'b': config._unset, 'd': 4}

        cowd._apply()

        self.assertEqual(orig, {'a': 1, 'c': 3, 'd': 4})

    @mock.patch.object(config.COWDict, '_apply')
    def test_apply(self, mock_apply):
        children = [mock.Mock(), mock.Mock(), mock.Mock()]
        cowd = config.COWDict({})
        cowd._children = children[:]
        cowd._new = {'a': 3, 'b': 2, 'c': 1}
        cowd._lookaside = {'a': 1, 'b': 2, 'c': 3}

        cowd.apply()

        mock_apply.assert_called_once_with()
        for child in children:
            child._apply.assert_called_once_with()
        self.assertEqual(len(children), 3)
        self.assertEqual(cowd._new, {})
        self.assertEqual(cowd._lookaside, {})
        self.assertEqual(cowd._children, [])


class LoadTest(unittest.TestCase):
    @mock.patch('functools.partial', return_value='partial')
    def test_get_class(self, mock_partial):
        load = config.Load()

        result = load.__get__(None, 'cls')

        self.assertEqual(result, 'partial')
        mock_partial.assert_called_once_with(load.class_load, 'cls')

    @mock.patch('functools.partial', return_value='partial')
    def test_get_inst(self, mock_partial):
        load = config.Load()

        result = load.__get__('inst', 'cls')

        self.assertEqual(result, 'partial')
        mock_partial.assert_called_once_with(load.inst_load, 'inst')

    DIR = 'dir'
    FILE = 'file'

    fs_mock = collections.namedtuple(
        'fs_mock', ['mock_isfile', 'mock_isdir', 'mock_listdir',
                    'mock_glob', 'mock_join'])

    @contextlib.contextmanager
    def mock_fs(self, files):
        def fake_isfile(name):
            return files.get(name) == self.FILE
        patch_isfile = mock.patch('os.path.isfile', side_effect=fake_isfile)

        def fake_isdir(name):
            return files.get(name) == self.DIR
        patch_isdir = mock.patch('os.path.isdir', side_effect=fake_isdir)

        def fake_listdir(dirname):
            dirname = dirname.rstrip('/') + '/'
            return list(set(key[len(dirname):].lstrip('/').split('/')[0]
                            for key in files.keys()
                            if key.startswith(dirname)))
        patch_listdir = mock.patch('os.listdir', side_effect=fake_listdir)

        def fake_glob(pattern):
            # Note this isn't fully accurate; /foo/* will match
            # /foo/bar/baz
            return fnmatch.filter(files.keys(), pattern)
        patch_glob = mock.patch('glob.glob', side_effect=fake_glob)

        patch_join = mock.patch('os.path.join', side_effect=tests.fake_join)

        # Start the mocks and build the tuple we're yielding
        fs_mocks = self.fs_mock(
            patch_isfile.start(),
            patch_isdir.start(),
            patch_listdir.start(),
            patch_glob.start(),
            patch_join.start(),
        )

        try:
            yield fs_mocks
        finally:
            patch_join.stop()
            patch_glob.stop()
            patch_listdir.stop()
            patch_isdir.stop()
            patch_isfile.stop()

    def test_iter_files_file(self):
        with self.mock_fs({
            'one': self.FILE,
        }) as fs_mocks:
            result = list(config.Load._iter_files('one'))

        self.assertEqual(result, ['one'])
        fs_mocks.mock_isfile.assert_called_once_with('one')
        self.assertFalse(fs_mocks.mock_isdir.called)
        self.assertFalse(fs_mocks.mock_listdir.called)
        self.assertFalse(fs_mocks.mock_glob.called)

    def test_iter_files_dir(self):
        with self.mock_fs({
            'dir': self.DIR,
            'dir/one': self.FILE,
            'dir/two': self.FILE,
            'dir/three': self.DIR,
            'dir/four': self.FILE,
        }) as fs_mocks:
            result = list(config.Load._iter_files('dir'))

        self.assertEqual(result, ['dir/four', 'dir/one', 'dir/two'])
        fs_mocks.mock_isfile.assert_has_calls([
            mock.call('dir'),
            mock.call('dir/four'),
            mock.call('dir/one'),
            mock.call('dir/three'),
            mock.call('dir/two'),
        ])
        self.assertEqual(fs_mocks.mock_isfile.call_count, 5)
        fs_mocks.mock_isdir.assert_called_once_with('dir')
        fs_mocks.mock_listdir.assert_called_once_with('dir')
        self.assertFalse(fs_mocks.mock_glob.called)

    def test_iter_files_glob(self):
        with self.mock_fs({
            'bad_one': self.FILE,
            'bad_two': self.FILE,
            'bad_three': self.DIR,
            'bad_four': self.FILE,
            'good_one': self.FILE,
            'good_two': self.FILE,
            'good_three': self.DIR,
            'good_four': self.FILE,
        }) as fs_mocks:
            result = list(config.Load._iter_files('good_*'))

        self.assertEqual(result, ['good_four', 'good_one', 'good_two'])
        fs_mocks.mock_isfile.assert_has_calls([
            mock.call('good_*'),
            mock.call('good_four'),
            mock.call('good_one'),
            mock.call('good_three'),
            mock.call('good_two'),
        ])
        self.assertEqual(fs_mocks.mock_isfile.call_count, 5)
        fs_mocks.mock_isdir.assert_called_once_with('good_*')
        self.assertFalse(fs_mocks.mock_listdir.called)
        fs_mocks.mock_glob.assert_called_once_with('good_*')

    def test_iter_files_list(self):
        with self.mock_fs({
            'one': self.FILE,
            'two': self.FILE,
            'four': self.FILE,
            'five': self.FILE,
        }) as fs_mocks:
            result = list(config.Load._iter_files(
                ['one', 'two', 'three', 'four', 'five']))

        self.assertEqual(result, ['one', 'two', 'four', 'five'])
        fs_mocks.mock_isfile.assert_has_calls([
            mock.call('one'),
            mock.call('two'),
            mock.call('three'),
            mock.call('four'),
            mock.call('five'),
        ])
        self.assertEqual(fs_mocks.mock_isfile.call_count, 5)
        fs_mocks.mock_isdir.assert_called_once_with('three')
        self.assertFalse(fs_mocks.mock_listdir.called)
        fs_mocks.mock_glob.assert_called_once_with('three')

    def test_merge_dict_unchanged(self):
        lhs = {
            'a': 1,
            'b': 2,
            'c': 3,
        }
        rhs = {}

        config.Load._merge_dict(lhs, rhs)

        self.assertEqual(lhs, {
            'a': 1,
            'b': 2,
            'c': 3,
        })
        self.assertEqual(rhs, {})

    def test_merge_dict_flat(self):
        lhs = {
            'a': 1,
            'b': 2,
            'c': 3,
        }
        rhs = {
            'b': 12,
            'd': 14,
        }

        config.Load._merge_dict(lhs, rhs)

        self.assertEqual(lhs, {
            'a': 1,
            'b': 12,
            'c': 3,
            'd': 14,
        })
        self.assertEqual(rhs, {
            'b': 12,
            'd': 14,
        })

    def test_merge_dict_nested(self):
        lhs = {
            'a': 1,
            'b': 2,
            'c': {
                'ca': 31,
                'cb': 32,
                'cc': 33,
            },
        }
        rhs = {
            'b': 12,
            'c': {
                'cb': 132,
                'cd': 134,
            },
            'd': 14,
        }

        config.Load._merge_dict(lhs, rhs)

        self.assertEqual(lhs, {
            'a': 1,
            'b': 12,
            'c': {
                'ca': 31,
                'cb': 132,
                'cc': 33,
                'cd': 134,
            },
            'd': 14,
        })
        self.assertEqual(rhs, {
            'b': 12,
            'c': {
                'cb': 132,
                'cd': 134,
            },
            'd': 14,
        })

    def test_merge_dict_loop(self):
        loop_lhs = {
            'loop_a': 91,
            'loop_b': 92,
            'loop_c': 93,
        }
        loop_rhs = {
            'loop_b': 192,
            'loop_d': 194,
        }
        lhs = {
            'a': 1,
            'b': loop_lhs,
            'c': loop_lhs,
        }
        rhs = {
            'b': loop_rhs,
            'c': loop_rhs,
            'd': 4,
        }

        config.Load._merge_dict(lhs, rhs)

        self.assertEqual(lhs, {
            'a': 1,
            'b': {
                'loop_a': 91,
                'loop_b': 192,
                'loop_c': 93,
                'loop_d': 194,
            },
            'c': {
                'loop_a': 91,
                'loop_b': 192,
                'loop_c': 93,
                'loop_d': 194,
            },
            'd': 4,
        })
        self.assertEqual(rhs, {
            'b': {
                'loop_b': 192,
                'loop_d': 194,
            },
            'c': {
                'loop_b': 192,
                'loop_d': 194,
            },
            'd': 4,
        })

    def test_merge_dict_nondict_lhs(self):
        lhs = {
            'a': 1,
            'b': 2,
            'c': 3,
        }
        rhs = {
            'b': 12,
            'c': {
                'cb': 132,
                'cd': 134,
            },
            'd': 14,
        }

        self.assertRaises(config.ConfigException, config.Load._merge_dict,
                          lhs, rhs)
        self.assertEqual(rhs, {
            'b': 12,
            'c': {
                'cb': 132,
                'cd': 134,
            },
            'd': 14,
        })

    def test_merge_dict_nondict_rhs(self):
        lhs = {
            'a': 1,
            'b': 2,
            'c': {
                'cb': 32,
                'cd': 34,
            },
        }
        rhs = {
            'b': 12,
            'c': 13,
            'd': 14,
        }

        self.assertRaises(config.ConfigException, config.Load._merge_dict,
                          lhs, rhs)
        self.assertEqual(rhs, {
            'b': 12,
            'c': 13,
            'd': 14,
        })

    @mock.patch.object(builtins, 'open')
    @mock.patch('yaml.safe_load', side_effect=lambda s: s.data)
    @mock.patch.object(config.Load, '_iter_files',
                       return_value=['file1', 'file2', 'file3', 'file4'])
    @mock.patch.object(config.Load, '_merge_dict')
    def test_load_basic(self, mock_merge_dict, mock_iter_files,
                        mock_safe_load, mock_open):
        files = {
            'file1': mock.MagicMock(data='file1_data'),
            'file2': mock.MagicMock(data='file2_data'),
            'file3': mock.MagicMock(data='file3_data'),
            'file4': mock.MagicMock(data='file4_data'),
        }
        for fobj in files.values():
            fobj.__enter__.return_value = fobj
        mock_open.side_effect = lambda fname: files[fname]
        load = config.Load()

        result = load._load('files')

        self.assertEqual(result, {})
        mock_iter_files.assert_called_once_with('files')
        mock_open.assert_has_calls([
            mock.call('file1'),
            mock.call('file2'),
            mock.call('file3'),
            mock.call('file4'),
        ])
        self.assertEqual(mock_open.call_count, 4)
        mock_safe_load.assert_has_calls([
            mock.call(files['file1']),
            mock.call(files['file2']),
            mock.call(files['file3']),
            mock.call(files['file4']),
        ])
        self.assertEqual(mock_safe_load.call_count, 4)
        mock_merge_dict.assert_has_calls([
            mock.call({}, 'file1_data'),
            mock.call({}, 'file2_data'),
            mock.call({}, 'file3_data'),
            mock.call({}, 'file4_data'),
        ])
        self.assertEqual(mock_merge_dict.call_count, 4)

    @mock.patch.object(builtins, 'open')
    @mock.patch('yaml.safe_load', side_effect=lambda s: s.data)
    @mock.patch.object(config.Load, '_iter_files',
                       return_value=['file1', 'file2', 'file3', 'file4'])
    @mock.patch.object(config.Load, '_merge_dict')
    def test_load_startwith(self, mock_merge_dict, mock_iter_files,
                            mock_safe_load, mock_open):
        files = {
            'file1': mock.MagicMock(data='file1_data'),
            'file2': mock.MagicMock(data='file2_data'),
            'file3': mock.MagicMock(data='file3_data'),
            'file4': mock.MagicMock(data='file4_data'),
        }
        for fobj in files.values():
            fobj.__enter__.return_value = fobj
        mock_open.side_effect = lambda fname: files[fname]
        load = config.Load()

        result = load._load('files', 'startwith')

        self.assertEqual(result, 'startwith')
        mock_iter_files.assert_called_once_with('files')
        mock_open.assert_has_calls([
            mock.call('file1'),
            mock.call('file2'),
            mock.call('file3'),
            mock.call('file4'),
        ])
        self.assertEqual(mock_open.call_count, 4)
        mock_safe_load.assert_has_calls([
            mock.call(files['file1']),
            mock.call(files['file2']),
            mock.call(files['file3']),
            mock.call(files['file4']),
        ])
        self.assertEqual(mock_safe_load.call_count, 4)
        mock_merge_dict.assert_has_calls([
            mock.call('startwith', 'file1_data'),
            mock.call('startwith', 'file2_data'),
            mock.call('startwith', 'file3_data'),
            mock.call('startwith', 'file4_data'),
        ])
        self.assertEqual(mock_merge_dict.call_count, 4)

    @mock.patch.object(config.Load, '_load', return_value='raw')
    def test_class_load_validate(self, mock_load):
        cls = mock.Mock(return_value='instance')
        load = config.Load()

        result = load.class_load(cls, 'files')

        self.assertEqual(result, 'instance')
        mock_load.assert_called_once_with('files')
        cls.validate.assert_called_once_with('raw')
        cls.assert_called_once_with('raw')

    @mock.patch.object(config.Load, '_load', return_value='raw')
    def test_class_load_novalidate(self, mock_load):
        cls = mock.Mock(return_value='instance')
        load = config.Load()

        result = load.class_load(cls, 'files', False)

        self.assertEqual(result, 'instance')
        mock_load.assert_called_once_with('files')
        self.assertFalse(cls.validate.called)
        cls.assert_called_once_with('raw')

    @mock.patch.object(config, 'COWDict', return_value='cow')
    @mock.patch.object(config.Load, '_load')
    def test_inst_load_validate(self, mock_load, mock_COWDict):
        inst = mock.Mock(_raw='raw')
        load = config.Load()

        result = load.inst_load(inst, 'files')

        self.assertEqual(result, inst)
        mock_COWDict.assert_called_once_with('raw')
        mock_load.assert_called_once_with('files', 'cow')
        cow = mock_load.return_value
        inst.validate.assert_called_once_with(cow)
        cow.apply.assert_called_once_with()
        inst._xlated.clear.assert_called_once_with()

    @mock.patch.object(config, 'COWDict', return_value='cow')
    @mock.patch.object(config.Load, '_load')
    def test_inst_load_novalidate(self, mock_load, mock_COWDict):
        inst = mock.Mock(_raw='raw')
        load = config.Load()

        result = load.inst_load(inst, 'files', False)

        self.assertEqual(result, inst)
        mock_COWDict.assert_called_once_with('raw')
        mock_load.assert_called_once_with('files', 'cow')
        cow = mock_load.return_value
        self.assertFalse(inst.validate.called)
        cow.apply.assert_called_once_with()
        inst._xlated.clear.assert_called_once_with()


class BaseConfigTest(unittest.TestCase):
    def test_init(self):
        result = config.BaseConfig('value')

        self.assertEqual(result._raw, 'value')
        self.assertEqual(result._xlated, {})

    def test_lookup_noname(self):
        class TestConfig(config.BaseConfig):
            _attrs = {}

        self.assertRaises(KeyError, TestConfig.lookup, '')

    def test_lookup_simplename(self):
        class TestConfig(config.BaseConfig):
            _attrs = {'spam': 'value'}

        result = TestConfig.lookup('spam')

        self.assertEqual(result, 'value')

    def test_lookup_shortlist(self):
        class TestConfig(config.BaseConfig):
            _attrs = {'spam': 'value'}

        result = TestConfig.lookup(['spam'])

        self.assertEqual(result, 'value')

    def test_lookup_descend(self):
        class TestConfig(config.BaseConfig):
            _attrs = {
                'spam': mock.Mock(_attrs={
                    'a': mock.Mock(_attrs={
                        'b': mock.Mock(_attrs={
                            'c': 'value',
                        }),
                    }),
                }),
            }

        result = TestConfig.lookup('//spam/a//b/c//')

        self.assertEqual(result, 'value')

    def test_lookup_descend_list(self):
        class TestConfig(config.BaseConfig):
            _attrs = {
                'spam': mock.Mock(_attrs={
                    'a': mock.Mock(_attrs={
                        'b': mock.Mock(_attrs={
                            'c': 'value',
                        }),
                    }),
                }),
            }

        result = TestConfig.lookup(['', 'spam', 'a', '', 'b', 'c', ''])

        self.assertEqual(result, 'value')

    @mock.patch.object(config.BaseConfig, '_extend')
    @mock.patch.object(config.BaseConfig, 'lookup')
    def test_extend_noattr(self, mock_lookup, mock_extend):
        class TestConfig(config.BaseConfig):
            _attrs = {}

        self.assertRaises(config.ConfigException, TestConfig.extend,
                          '', 'option')
        self.assertFalse(mock_lookup.called)
        self.assertFalse(mock_extend.called)

    @mock.patch.object(config.BaseConfig, '_extend')
    @mock.patch.object(config.BaseConfig, 'lookup')
    def test_extend_simpleattr(self, mock_lookup, mock_extend):
        opt = mock.Mock()

        class TestConfig(config.BaseConfig):
            _attrs = {'spam': opt}

        TestConfig.extend('foo', 'option')

        self.assertFalse(mock_lookup.called)
        mock_extend.assert_called_once_with('foo', 'foo', 'option')

    @mock.patch.object(config.BaseConfig, '_extend')
    @mock.patch.object(config.BaseConfig, 'lookup')
    def test_extend_shortlist(self, mock_lookup, mock_extend):
        opt = mock.Mock()

        class TestConfig(config.BaseConfig):
            _attrs = {'spam': opt}

        TestConfig.extend(['foo'], 'option')

        self.assertFalse(mock_lookup.called)
        mock_extend.assert_called_once_with('foo', 'foo', 'option')

    @mock.patch.object(config.BaseConfig, '_extend')
    @mock.patch.object(config.BaseConfig, 'lookup')
    def test_extend_descend(self, mock_lookup, mock_extend):
        opt = mock.Mock()

        class TestConfig(config.BaseConfig):
            _attrs = {}

        TestConfig.extend('//spam/a//b/c//', 'option')

        mock_lookup.assert_called_once_with(['spam', 'a', 'b'])
        mock_lookup.return_value._extend.assert_called_once_with(
            'c', 'c', 'option')
        self.assertFalse(mock_extend.called)

    @mock.patch.object(config.BaseConfig, '_extend')
    @mock.patch.object(config.BaseConfig, 'lookup')
    def test_extend_descend_list(self, mock_lookup, mock_extend):
        opt = mock.Mock()

        class TestConfig(config.BaseConfig):
            _attrs = {}

        TestConfig.extend(['', 'spam', 'a', '', 'b', 'c', ''], 'option')

        mock_lookup.assert_called_once_with(['spam', 'a', 'b'])
        mock_lookup.return_value._extend.assert_called_once_with(
            'c', 'c', 'option')
        self.assertFalse(mock_extend.called)

    @mock.patch.object(config.BaseConfig, '_extend')
    @mock.patch.object(config.BaseConfig, 'lookup')
    def test_extend_altkey(self, mock_lookup, mock_extend):
        opt = mock.Mock()

        class TestConfig(config.BaseConfig):
            _attrs = {'spam': opt}

        TestConfig.extend('foo', 'option', 'key')

        self.assertFalse(mock_lookup.called)
        mock_extend.assert_called_once_with('foo', 'key', 'option')

    @mock.patch.object(config.BaseConfig, '_extend')
    @mock.patch.object(config.BaseConfig, 'lookup')
    def test_extend_reservedattr(self, mock_lookup, mock_extend):
        opt = mock.Mock()

        class TestConfig(config.BaseConfig):
            _attrs = {'spam': opt}

        for attr in config.RESERVED:
            self.assertRaises(config.ConfigException, TestConfig.extend,
                              attr, 'option')

        self.assertFalse(mock_lookup.called)
        self.assertFalse(mock_extend.called)

    @mock.patch.object(config, '_schema_invalidate')
    def test_extend_dupattr(self, mock_schema_invalidate):
        opt = mock.Mock(spec=config.Option, _parents=set(), __key__='key')

        class TestConfig(config.BaseConfig):
            _attrs = {'spam': opt}
            _keys = {'key': opt}

        self.assertRaises(config.ConfigException, TestConfig._extend,
                          'spam', 'bar', 'option')
        self.assertFalse(mock_schema_invalidate.called)

    @mock.patch.object(config, '_schema_invalidate')
    def test_extend_dupkey(self, mock_schema_invalidate):
        opt = mock.Mock(spec=config.Option, _parents=set(), __key__='key')

        class TestConfig(config.BaseConfig):
            _attrs = {'spam': opt}
            _keys = {'key': opt}

        self.assertRaises(config.ConfigException, TestConfig._extend,
                          'foo', 'key', 'option')
        self.assertFalse(mock_schema_invalidate.called)

    @mock.patch.object(config, '_schema_invalidate')
    def test_extend(self, mock_schema_invalidate):
        opt = mock.Mock(spec=config.Option, _parents=set(), __key__='key')

        class TestConfig(config.BaseConfig):
            _attrs = {'spam': opt}
            _keys = {'key': opt}

        TestConfig._extend('foo', 'bar', 'option')

        foo = TestConfig.foo
        self.assertTrue(isinstance(foo, config.Binding))
        self.assertEqual(foo.__attr__, 'foo')
        self.assertEqual(foo.__key__, 'bar')
        self.assertEqual(foo.__option__, 'option')
        self.assertEqual(TestConfig._attrs, {
            'spam': opt,
            'foo': foo,
        })
        self.assertEqual(TestConfig._keys, {
            'key': opt,
            'bar': foo,
        })
        mock_schema_invalidate.assert_called_once_with(TestConfig)

    @mock.patch('jsonschema.validate')
    def test_validate(self, mock_validate):
        class TestConfig(config.BaseConfig):
            __schema__ = 'schema'

        TestConfig.validate('value')

        mock_validate.assert_called_once_with('value', 'schema')


class ConfigMetaTest(unittest.TestCase):
    def test_new_base(self):
        self.assertEqual(config.Config._attrs, {})
        self.assertEqual(config.Config._keys, {})
        self.assertEqual(config.Config._schema_raw, {'type': 'object'})
        self.assertEqual(config.Config._schema_cache, None)
        self.assertEqual(config.Config._parents, set())

    def test_new_schema_capture(self):
        class TestConfig(config.Config):
            __schema__ = {'a': 1}

        self.assertFalse('__schema__' in TestConfig.__dict__)
        self.assertEqual(TestConfig._attrs, {})
        self.assertEqual(TestConfig._keys, {})
        self.assertEqual(TestConfig._schema_raw, {'type': 'object', 'a': 1})
        self.assertEqual(TestConfig._schema_cache, None)
        self.assertEqual(TestConfig._parents, set())

    def test_new_passthrough_internal(self):
        opt = mock.Mock(spec=config.Option)

        class TestConfig(config.Config):
            _spam = opt

        self.assertTrue('_spam' in TestConfig.__dict__)
        self.assertEqual(TestConfig._attrs, {})
        self.assertEqual(TestConfig._keys, {})
        self.assertEqual(TestConfig._schema_raw, {'type': 'object'})
        self.assertEqual(TestConfig._schema_cache, None)
        self.assertEqual(TestConfig._parents, set())
        self.assertEqual(TestConfig._spam, opt)

    def test_new_passthrough_other(self):
        class TestConfig(config.Config):
            spam = 'value'

        self.assertTrue('spam' in TestConfig.__dict__)
        self.assertEqual(TestConfig._attrs, {})
        self.assertEqual(TestConfig._keys, {})
        self.assertEqual(TestConfig._schema_raw, {'type': 'object'})
        self.assertEqual(TestConfig._schema_cache, None)
        self.assertEqual(TestConfig._parents, set())
        self.assertEqual(TestConfig.spam, 'value')

    def test_new_option_nokey(self):
        opt = mock.Mock(spec=config.Option, _parents=set())

        class TestConfig(config.Config):
            spam = opt

        self.assertTrue('spam' in TestConfig.__dict__)
        spam = TestConfig.__dict__['spam']
        self.assertTrue(isinstance(spam, config.Binding))
        self.assertEqual(spam.__attr__, 'spam')
        self.assertEqual(spam.__key__, 'spam')
        self.assertEqual(spam.__option__, opt)
        self.assertEqual(spam.__option__._parents, set([TestConfig]))
        self.assertEqual(TestConfig._attrs, {'spam': spam})
        self.assertEqual(TestConfig._keys, {'spam': spam})
        self.assertEqual(TestConfig._schema_raw, {'type': 'object'})
        self.assertEqual(TestConfig._schema_cache, None)
        self.assertEqual(TestConfig._parents, set())

    def test_new_option_withkey(self):
        opt = mock.Mock(spec=config.Option, _parents=set(), __key__='key')

        class TestConfig(config.Config):
            spam = opt

        self.assertTrue('spam' in TestConfig.__dict__)
        spam = TestConfig.__dict__['spam']
        self.assertTrue(isinstance(spam, config.Binding))
        self.assertEqual(spam.__attr__, 'spam')
        self.assertEqual(spam.__key__, 'key')
        self.assertEqual(spam.__option__, opt)
        self.assertEqual(spam.__option__._parents, set([TestConfig]))
        self.assertEqual(TestConfig._attrs, {'spam': spam})
        self.assertEqual(TestConfig._keys, {'key': spam})
        self.assertEqual(TestConfig._schema_raw, {'type': 'object'})
        self.assertEqual(TestConfig._schema_cache, None)
        self.assertEqual(TestConfig._parents, set())

    def test_new_option_duplicatekey(self):
        opt1 = mock.Mock(spec=config.Option, _parents=set(), __key__='key')
        opt2 = mock.Mock(spec=config.Option, _parents=set(), __key__='key')
        namespace = {
            'spam1': opt1,
            'spam2': opt2,
        }

        self.assertRaises(config.ConfigException, config.ConfigMeta,
                          'TestConfig', (config.Config,), namespace)

    def test_new_class_nokey(self):
        class TestConfig(config.Config):
            class spam(config.Config):
                pass

        self.assertTrue('spam' in TestConfig.__dict__)
        spam = TestConfig.__dict__['spam']
        self.assertTrue(isinstance(spam, config.Binding))
        self.assertEqual(spam.__attr__, 'spam')
        self.assertEqual(spam.__key__, 'spam')
        self.assertTrue(issubclass(spam.__option__, config.Config))
        self.assertEqual(spam.__option__._parents, set([TestConfig]))
        self.assertEqual(TestConfig._attrs, {'spam': spam})
        self.assertEqual(TestConfig._keys, {'spam': spam})
        self.assertEqual(TestConfig._schema_raw, {'type': 'object'})
        self.assertEqual(TestConfig._schema_cache, None)
        self.assertEqual(TestConfig._parents, set())

    def test_new_class_withkey(self):
        class TestConfig(config.Config):
            class spam(config.Config):
                __key__ = 'key'

        self.assertTrue('spam' in TestConfig.__dict__)
        spam = TestConfig.__dict__['spam']
        self.assertTrue(isinstance(spam, config.Binding))
        self.assertEqual(spam.__attr__, 'spam')
        self.assertEqual(spam.__key__, 'key')
        self.assertTrue(issubclass(spam.__option__, config.Config))
        self.assertEqual(spam.__option__._parents, set([TestConfig]))
        self.assertEqual(TestConfig._attrs, {'spam': spam})
        self.assertEqual(TestConfig._keys, {'key': spam})
        self.assertEqual(TestConfig._schema_raw, {'type': 'object'})
        self.assertEqual(TestConfig._schema_cache, None)
        self.assertEqual(TestConfig._parents, set())

    def test_new_reservedattr(self):
        for attr in config.RESERVED:
            opt = mock.Mock(spec=config.Option, _parents=set())
            namespace = {attr: opt}

            self.assertRaises(config.ConfigException, config.ConfigMeta,
                              'TestConfig', (config.Config,), namespace)


class OptionTest(unittest.TestCase):
    def test_init_base(self):
        result = config.Option()

        self.assertEqual(result.__default__, config._unset)
        self.assertEqual(result.__doc__, '')
        self.assertEqual(getattr(result, '__key__', 'unset'), 'unset')
        self.assertEqual(result._schema_raw, {})
        self.assertEqual(result._parents, set())

    def test_init_alt(self):
        result = config.Option('default', 'help', {'type': 'int'},
                               [1, 2, 3, 5, 8], 'key')

        self.assertEqual(result.__default__, 'default')
        self.assertEqual(result.__doc__, 'help')
        self.assertEqual(getattr(result, '__key__', 'unset'), 'key')
        self.assertEqual(result._schema_raw, {
            'type': 'int',
            'default': 'default',
            'description': 'help',
            'enum': [1, 2, 3, 5, 8],
        })
        self.assertEqual(result._parents, set())

    def test_call(self):
        opt = config.Option()

        result = opt('spam')

        self.assertEqual(result, 'spam')

    def test_extend(self):
        opt = config.Option()

        self.assertRaises(config.ConfigException, opt._extend,
                          'attr', 'key', 'option')

    @mock.patch.object(config.Option, '__schema__', 'schema')
    @mock.patch('jsonschema.validate')
    def test_validate(self, mock_validate):
        opt = config.Option()

        opt.validate('value')

        mock_validate.assert_called_once_with('value', 'schema')

    def test_schema(self):
        opt = config.Option()
        opt._schema_raw = 'schema'

        self.assertEqual(opt.__schema__, 'schema')


class ListOptionTest(unittest.TestCase):
    def test_init_base(self):
        result = config.ListOption()

        self.assertEqual(result.__default__, config._unset)
        self.assertEqual(result.__doc__, '')
        self.assertEqual(getattr(result, '__key__', 'unset'), 'unset')
        self.assertEqual(result._schema_raw, {'type': 'array'})
        self.assertEqual(result._parents, set())
        self.assertEqual(result._mode, 'noxlate')
        self.assertEqual(result._items, None)
        self.assertEqual(result._attrs, {})
        self.assertEqual(result._schema_cache, None)

    def test_init_alt(self):
        result = config.ListOption('default', 'help', {'extra': 'data'},
                                   None, 'key')

        self.assertEqual(result.__default__, 'default')
        self.assertEqual(result.__doc__, 'help')
        self.assertEqual(getattr(result, '__key__', 'unset'), 'key')
        self.assertEqual(result._schema_raw, {
            'type': 'array',
            'default': 'default',
            'description': 'help',
            'extra': 'data',
        })
        self.assertEqual(result._parents, set())
        self.assertEqual(result._mode, 'noxlate')
        self.assertEqual(result._items, None)
        self.assertEqual(result._attrs, {})
        self.assertEqual(result._schema_cache, None)

    def test_init_list(self):
        items = mock.Mock(_parents=set())
        result = config.ListOption(items=items)

        self.assertEqual(result._mode, 'list')
        self.assertEqual(result._items, items)
        self.assertEqual(result._attrs, {'[]': items})
        self.assertEqual(items._parents, set([result]))

    def test_init_tuple(self):
        items = [mock.Mock(_parents=set()) for i in range(5)]
        items[2] = None
        result = config.ListOption(items=tuple(items))

        self.assertEqual(result._mode, 'tuple')
        self.assertEqual(result._items, items)
        self.assertEqual(result._attrs, {
            '[0]': items[0],
            '[1]': items[1],
            '[3]': items[3],
            '[4]': items[4],
        })
        for item in items:
            if item:
                self.assertEqual(item._parents, set([result]))

    def test_call_noxlate(self):
        opt = config.ListOption()

        result = opt([1, 2, 3])

        self.assertEqual(result, [1, 2, 3])

    def test_call_list(self):
        items = mock.Mock(_parents=set(), side_effect=lambda x: str(x))
        opt = config.ListOption(items=items)

        result = opt([1, 2, 3])

        self.assertEqual(result, ['1', '2', '3'])
        items.assert_has_calls([
            mock.call(1),
            mock.call(2),
            mock.call(3),
        ])
        self.assertEqual(items.call_count, 3)

    def test_call_tuple(self):
        items = [
            mock.Mock(_parents=set(), side_effect=lambda x: (x, 1)),
            mock.Mock(_parents=set(), side_effect=lambda x: (x, 2)),
            mock.Mock(_parents=set(), side_effect=lambda x: (x, 3)),
        ]
        opt = config.ListOption(items=items)

        result = opt([1, 2, 3, 4, 5])

        self.assertEqual(result, [(1, 1), (2, 2), (3, 3), 4, 5])
        for idx, item in enumerate(items):
            item.assert_called_once_with(idx + 1)

    def test_schema_cached(self):
        opt = config.ListOption()
        opt._schema_cache = 'cached'

        self.assertEqual(opt.__schema__, 'cached')
        self.assertEqual(opt._schema_cache, 'cached')

    def test_schema_noxlate(self):
        opt = config.ListOption()

        expected = {
            'type': 'array',
        }
        self.assertEqual(opt.__schema__, expected)
        self.assertEqual(opt._schema_cache, expected)

    def test_schema_list(self):
        items = mock.Mock(_parents=set(), __schema__='schema')
        opt = config.ListOption(items=items)

        expected = {
            'type': 'array',
            'items': 'schema',
        }
        self.assertEqual(opt.__schema__, expected)
        self.assertEqual(opt._schema_cache, expected)

    def test_schema_tuple(self):
        items = [mock.Mock(_parents=set(), __schema__='schema%d' % i)
                 for i in range(5)]
        items[2] = None
        opt = config.ListOption(items=items)

        expected = {
            'type': 'array',
            'items': ['schema0', 'schema1', {}, 'schema3', 'schema4'],
        }
        self.assertEqual(opt.__schema__, expected)
        self.assertEqual(opt._schema_cache, expected)
