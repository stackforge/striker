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

import six


def fake_join(a, *p):
    """
    Lifted from the POSIX implementation of os.path, for testing
    purposes.
    """

    path = a
    for b in p:
        if b.startswith('/'):
            path = b
        elif path == '' or path.endswith('/'):
            path += b
        else:
            path += '/' + b
    return path


def fake_isabs(s):
    """
    Lifted from the POSIX implementation of os.path, for testing
    purposes.
    """

    return s.startswith('/')


def fake_abspath(path):
    """
    Lifted from the POSIX implementation of os.path, for testing
    purposes.
    """

    if not fake_isabs(path):
        if six.PY2 and isinstance(path, unicode):
            cwd = os.getcwdu()
        elif six.PY3 and isinstance(path, bytes):
            cwd = os.getcwdb()
        else:
            cwd = os.getcwd()
        path = fake_join(cwd, path)
    return fake_normpath(path)


def fake_normpath(path):
    """
    Lifted from the POSIX implementation of os.path, for testing
    purposes.
    """

    if six.PY2 and isinstance(path, unicode):
        sep = u'/'
        empty = u''
        dot = u'.'
        dotdot = u'..'
    elif six.PY3 and isinstance(path, bytes):
        sep = b'/'
        empty = b''
        dot = b'.'
        dotdot = b'..'
    else:
        sep = '/'
        empty = ''
        dot = '.'
        dotdot = '..'

    if path == empty:
        return dot

    initial_slashes = path.startswith(sep)

    # POSIX allows one or two initial slashes, but treats three or more
    # as single slash.
    if (initial_slashes and
            path.startswith(sep * 2) and not path.startswith(sep * 3)):
        initial_slashes = 2

    comps = path.split(sep)
    new_comps = []
    for comp in comps:
        if comp in (empty, dot):
            continue

        if (comp != dotdot or (not initial_slashes and not new_comps) or
                (new_comps and new_comps[-1] == dotdot)):
            new_comps.append(comp)
        elif new_comps:
            new_comps.pop()

    comps = new_comps
    path = sep.join(comps)

    if initial_slashes:
        path = sep * initial_slashes + path

    return path or dot
