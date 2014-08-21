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
import copy
import functools
import glob
import inspect
import os

import jsonschema
import six
import yaml


_unset = object()


class ConfigException(Exception):
    """
    Configuration-related exceptions.
    """

    pass


def _schema_invalidate(child):
    """
    Performs schema invalidation.  This is an iterative function that
    pushes a schema invalidation up to all the "parent" options.
    Invalidating the schema ensures that it will be recomputed as
    necessary.

    :param child: The ``Option`` instance or ``Config`` subclass for
                  which the schema will be invalidated.
    """

    seen = set([child])
    queue = [child]
    while queue:
        work = queue.pop(0)

        # Does it have a cached value?
        if getattr(work, '_schema_cache', None) is None:
            continue

        # Invalidate the cache
        work._schema_cache = None

        # Add its parents to the queue
        for parent in work._parents:
            # Skip ones we've already processed
            if parent in seen:
                continue

            # Add the parent to the work queue
            queue.append(parent)
            seen.add(parent)


class Schema(object):
    """
    Represent the special ``__schema__`` class attribute.  An object
    of this class is assigned to the ``__schema__`` class attribute of
    the ``Config`` subclasses.  When the value is requested, a
    JSON-Schema representation is created and cached.
    """

    def __get__(self, obj, cls):
        """
        Retrieve the schema corresponding to the given class.

        :param obj: An instance of a ``Config`` subclass.  Ignored.
        :param cls: The ``Config`` subclass.  The schema will be
                    computed and cached in the class.

        :returns: The JSON-Schema dictionary describing the ``Config``
                  subclass.
        """

        # Have we cached the schema yet?
        if cls._schema_cache is None:
            # Begin with a copy of the raw schema
            schema = copy.deepcopy(cls._schema_raw)

            # Add in the description, if any
            if cls.__doc__:
                schema['description'] = cls.__doc__

            # Assemble the property information
            properties = {}
            required = set()
            for key, binding in cls._keys.items():
                # Add the schema for the option
                properties[key] = binding.__schema__

                # Is it required?
                if binding.__default__ is _unset:
                    required.add(key)

            # Add that data to the schema
            schema['properties'] = properties
            schema['required'] = sorted(required)

            # Cache the final schema
            cls._schema_cache = schema

        return cls._schema_cache

    def __set__(self, obj, value):
        """
        Set the value of the schema.  This is prohibited, so an
        ``AttributeError`` is raised.

        :param obj: An instance of a ``Config`` subclass.
        :param value: The new value for the schema.
        """

        raise AttributeError("cannot set read-only attribute '__schema__'")

    def __delete__(self, obj):
        """
        Delete the value of the schema.  This is prohibited, so an
        ``AttributeError`` is raised.

        :param obj: An instance of a ``Config`` subclass.
        """

        raise AttributeError("cannot delete read-only attribute '__schema__'")


class Binding(object):
    """
    Represent a binding between an attribute name, a key name, and an
    option descriptor.  Objects of this class are constructed by
    ``ConfigMeta``, and are only used internally.  A ``Binding`` is a
    Python descriptor, meaning it implements a ``__get__()`` method
    which performs the steps necessary to obtain a translated value
    from the raw configuration.
    """

    def __init__(self, attr, key, option):
        """
        Initialize a ``Binding`` object.

        :param attr: The name of the attribute the option is attached
                     to.
        :param key: The configuration dictionary key.  Under most
                    circumstances, this will be the same as ``attr``.
        :param option: A callable, either an instance of ``Option`` or
                       a subclass of ``Config``.  The callable will be
                       called with a value drawn from the
                       configuration, and must return the translated
                       value.  In addition, the callable must provide
                       some attributes, such as ``__default__`` and
                       ``__schema__``.
        """

        # Store the values
        self.__attr__ = attr
        self.__key__ = key
        self.__option__ = option

    def __call__(self, obj):
        """
        Retrieve the configuration value bound to the option descriptor.
        This performs memoization, for efficiency.

        :param obj: The object containing the raw configuration data
                    and the translation cache.

        :returns: The translated configuration data.
        """

        # Do we have a cached translation?
        if self.__attr__ not in obj._xlated:
            # Start with the default value
            value = self.__option__.__default__

            # See if we have a value in the configuration dictionary
            if self.__key__ in obj._raw:
                value = self.__option__(obj._raw[self.__key__])

            # If we didn't find a value, raise an error
            if value is _unset:
                raise AttributeError(
                    "missing required configuration value '%s' for "
                    "attribute '%s'" % (self.__key__, self.__attr__))

            # Cache the value
            obj._xlated[self.__attr__] = value

        return obj._xlated[self.__attr__]

    def __getattr__(self, name):
        """
        Delegate attribute retrieval to the option.  This allows the
        ``Binding`` object to be used as a proxy for the option
        descriptor.

        :param name: The name of the attribute to retrieve.

        :returns: The value of the named attribute.
        """

        return getattr(self.__option__, name)

    def __contains__(self, name):
        """
        Delegate item existence check to the option.  This allows the
        ``Binding`` object to be used as a proxy for the option
        descriptor.

        :param name: The name of the item to check the existance of.

        :returns: A ``True`` value if the item exists, ``False``
                  otherwise.
        """

        return name in self.__option__

    def __getitem__(self, name):
        """
        Delegate item retrieval to the option.  This allows the
        ``Binding`` object to be used as a proxy for the option
        descriptor.

        :param name: The name of the item to retrieve.

        :returns: The value of the named item.
        """

        return self.__option__[name]

    def __get__(self, obj, cls):
        """
        Retrieve the value of the configuration option.

        :param obj: The object containing the raw configuration data
                    and the translation cache.  If ``None``, the
                    ``Binding`` instance is returned; this will proxy
                    for the bound option.
        :param cls: The class the attribute is defined on.

        :returns: The translated configuration data.
        """

        # Return the binding if this was a class access
        if obj is None:
            return self

        # Instance access; return the translated configuration data
        return self(obj)

    def __set__(self, obj, value):
        """
        Set the value of the configuration option.  This is prohibited, so
        an ``AttributeError`` is raised.

        :param obj: The object containing the raw configuration data
                    and the translation cache.
        :param value: The new value for the attribute.
        """

        raise AttributeError("cannot set read-only attribute '%s'" %
                             self.__attr__)

    def __delete__(self, obj):
        """
        Delete the value of the configuration option.  This is prohibited,
        so an ``AttributeError`` is raised.

        :param obj: The object containing the raw configuration data
                    and the translation cache.
        """

        raise AttributeError("cannot delete read-only attribute '%s'" %
                             self.__attr__)


class COWDict(collections.MutableMapping):
    """
    A simple copy-on-write dictionary class, structured to keep track
    of a tree of dictionaries.  This is used to allow a dictionary
    tree to be modified arbitrarily, but for the changes to not be
    applied to the original dictionary until the last moment.
    """

    def __init__(self, orig, root=None):
        """
        Initialize a ``COWDict`` object.

        :param orig: The original dictionary.  This dictionary will
                     not be modified until and unless the ``apply()``
                     method is called.
        :param root: The root of a dictionary tree.  This is used
                     internally to track deeper dictionaries to which
                     changes must be applied.
        """

        # Set up basic value tracking
        self._orig = orig
        self._new = {}
        self._lookaside = {}  # tracks child COWDict objects

        # Keep track of root and children
        self._root = root
        self._children = []

        # Update the root's list of children
        if root is not None:
            root._children.append(self)

    def __getitem__(self, key):
        """
        Retrieve an item.

        :param key: The key to look up.

        :returns: The value of the key.
        """

        # Check if we've cached a COWDict for a dictionary value
        if key in self._lookaside:
            return self._lookaside[key]

        # OK, find the value
        value = self._new.get(key, self._orig.get(key, _unset))
        if value is _unset:
            raise KeyError(key)

        # If the value is a dictionary, create and cache a COWDict for
        # it
        if isinstance(value, dict):
            # We use the trinary here to prevent self-references
            self._lookaside[key] = self.__class__(
                value, self if self._root is None else self._root)
            return self._lookaside[key]

        # OK, return the value
        return value

    def __setitem__(self, key, value):
        """
        Set the value of an item.

        :param key: The key to set.
        :param value: The value to set.
        """

        # Clear out lookaside...
        self._lookaside.pop(key, None)

        # Check if we're resetting to the base value
        if key in self._orig and self._orig[key] == value:
            self._new.pop(key, None)
        else:
            self._new[key] = value

    def __delitem__(self, key):
        """
        Delete the value of an item.

        :param key: The key to delete.
        """

        # Clear out lookaside...
        self._lookaside.pop(key, None)

        # Do we need to mask the value?
        if key in self._orig:
            # Masking it
            self._new[key] = _unset
        else:
            self._new.pop(key, None)

    def __iter__(self):
        """
        Iterate over the keys in the dictionary.

        :returns: An iteration of the dictionary keys.
        """

        # Walk through the merged set of keys
        for key in self._keys():
            if self._new.get(key) is _unset:
                # Skip unset (deleted) keys
                continue

            yield key

    def __len__(self):
        """
        Calculate the number of elements in the dictionary.

        :returns: The number of elements in the dictionary.
        """

        # Count the merged set of keys, then subtract the number of
        # deleted keys
        return len(self._keys()) - list(self._new.values()).count(_unset)

    def _keys(self):
        """
        Returns an unfiltered set of keys available in the original
        dictionary and in our overrides.  This will include deleted
        keys, since they are represented as values of ``_unset``.

        :returns: A set of all keys in the original and overrides
                  dictionary.
        """

        return set(self._orig.keys()) | set(self._new.keys())

    def _apply(self):
        """
        Apply the changes represented by the overrides to the original
        dictionary.
        """

        # Apply the changes
        for key, value in self._new.items():
            if value is _unset:
                self._orig.pop(key, None)
            else:
                self._orig[key] = value

    def apply(self):
        """
        Apply the changes stored in the ``COWDict`` object to the original
        dictionary tree.
        """

        # Apply to ourself first...
        self._apply()

        # Now apply to the children...
        for child in self._children:
            child._apply()

        # Finally, clear out our stale data
        self._new.clear()
        self._lookaside.clear()
        self._children[:] = []


class Load(object):
    """
    A special Python descriptor class that allows the
    ``BaseConfig.load()`` method to have two different behaviors,
    depending on whether it is called as a class method or an instance
    method.  When called as a class method, ``load()`` will load files
    and return a new instance of the class; when called as an instance
    method, it will load files and merge them into the configuration
    instance.
    """

    def __get__(self, obj, cls):
        """
        Retrieve the appropriate method to use based on how it is
        accessed.  If the attribute is accessed via class access,
        returns the ``class_load()`` method; if accessed via instance
        access, returns the ``inst_load()`` method.

        :param obj: An instance of a ``Config`` subclass.
        :param cls: The ``Config`` subclass.

        :returns: The appropriate ``load()`` method to call.
        """

        # Is it class access?
        if obj is None:
            return functools.partial(self.class_load, cls)

        # OK, instance access
        return functools.partial(self.inst_load, obj)

    @staticmethod
    def _iter_files(files):
        """
        A generator which iterates over a list of existing files, given a
        description of the desired files.

        :param files: A list of filenames.  (If a single string is
                      given, it will be turned into a list of one
                      element.)  For each filename in the list,
                      entries which name a single file are yielded
                      directly; entries which name a directory result
                      in each file in that directory being yielded (no
                      recursing down subdirectories); and remaining
                      entries are treated as globs and any matching
                      files are yielded.

        :returns: An iterator over a sequence of existing file names.
                  Note that no attempt is made to avoid races.
        """

        # If files is not a list, wrap it in one
        if isinstance(files, six.string_types):
            files = [files]

        # Walk through all the files...
        for fname in files:
            # If it's a file, just yield it
            if os.path.isfile(fname):
                yield fname

            # If it's a directory, return all the files in the
            # directory (sorted)
            elif os.path.isdir(fname):
                for entry in sorted(os.listdir(fname)):
                    path = os.path.join(fname, entry)
                    if os.path.isfile(path):
                        yield path

            # OK, treat it as a glob
            else:
                for entry in sorted(glob.glob(fname)):
                    if os.path.isfile(entry):
                        yield entry

    @staticmethod
    def _merge_dict(lhs, rhs):
        """
        Merges two dictionary trees into a single dictionary.

        :param lhs: The first dictionary to be merged.  This
                    dictionary will be updated to contain the contents
                    of ``rhs``.
        :param rhs: The second dictionary to be merged.  This
                    dictionary will not be modified, but its contents
                    will become contents of ``lhs``.
        """

        # YAML files can create loops
        seen = set([(id(lhs), id(rhs))])
        queue = [(lhs, rhs, [])]
        work = []
        while queue:
            # Get a work item
            lhs, rhs, path = queue.pop(0)

            # Walk through all keys on rhs
            for key, rh_value in rhs.items():
                if key not in lhs:
                    # OK, this is simple enough
                    lhs[key] = rh_value
                    continue

                # Get the lhs value
                lh_value = lhs[key]

                # Is either value a dictionary?  Coerce to int so we
                # can use ^ on it
                lh_dict = int(isinstance(lh_value, dict))
                rh_dict = int(isinstance(rh_value, dict))

                # Need the key path
                key_path = path + [key]

                # Check if the values are compatible
                if (lh_dict ^ rh_dict) == 1:
                    raise ConfigException(
                        "/%s: type mismatch" % '/'.join(key_path))

                # OK, if they're not dictionaries, apply the change
                if lh_dict == 0:
                    lhs[key] = rh_value
                else:
                    # Add another queue item
                    queue_id = (id(lh_value), id(rh_value))
                    if queue_id not in seen:
                        queue.append((lh_value, rh_value, key_path))
                        seen.add(queue_id)

    def _load(self, files, startwith=None):
        """
        Load a list of YAML files.

        :param files: A list of filenames.  (If a single string is
                      given, it will be turned into a list of one
                      element.)  For each filename in the list,
                      entries which name a single file are loaded
                      directly; entries which name a directory result
                      in each file in that directory being loaded (no
                      recursing down subdirectories); and remaining
                      entries are treated as globs and any matching
                      files are loaded.
        :param startwith: An optional starting dictionary.

        :returns: The final dictionary; if ``startswith`` is provided,
                  it will be that dictionary.
        """

        # Initialize the variables
        final = startwith or {}

        # Iterate over the files
        for fname in self._iter_files(files):
            # Load the YAML file
            with open(fname) as f:
                raw = yaml.safe_load(f)

            # Merge its contents with what we've loaded so far
            self._merge_dict(final, raw)

        return final

    def class_load(self, cls, files, validate=True):
        """
        Loads one or more YAML files and returns an initialized instance
        of the ``Config`` subclass.

        :param files: A list of filenames.  (If a single string is
                      given, it will be turned into a list of one
                      element.)  For each filename in the list,
                      entries which name a single file are loaded
                      directly; entries which name a directory result
                      in each file in that directory being loaded (no
                      recursing down subdirectories); and remaining
                      entries are treated as globs and any matching
                      files are loaded.
        :param validate: If ``True`` (the default), the dictionary
                         value loaded from ``files`` will be
                         validated.

        :returns: An instance of the ``Config`` subclass containing
                  the loaded configuration.
        """

        # Begin by loading the files
        raw = self._load(files)

        # Validate the value
        if validate:
            cls.validate(raw)

        # OK, instantiate the class and return it
        return cls(raw)

    def inst_load(self, inst, files, validate=True):
        """
        Loads one or more YAML files and updates the configuration stored
        in the instance of the ``Config`` subclass.

        :param files: A list of filenames.  (If a single string is
                      given, it will be turned into a list of one
                      element.)  For each filename in the list,
                      entries which name a single file are loaded
                      directly; entries which name a directory result
                      in each file in that directory being loaded (no
                      recursing down subdirectories); and remaining
                      entries are treated as globs and any matching
                      files are loaded.
        :param validate: If ``True`` (the default), the dictionary
                         value loaded from ``files`` will be
                         validated.

        :returns: Returns the instance that was updated, for
                  convenience.
        """

        # Begin by loading the files, using a COWDict
        cow = self._load(files, COWDict(inst._raw))

        # Validate the value
        if validate:
            inst.validate(cow)

        # Apply the changes
        cow.apply()

        # Invalidate cached values
        inst._xlated.clear()

        # Return the instance, for convenience
        return inst


class BaseConfig(object):
    """
    Base class for ``Config``.  This introduces several reserved
    attribute names into the ``Config`` class that are protected by
    ``ConfigMeta``.
    """

    def __init__(self, value):
        """
        Initialize a ``Config`` subclass.

        :param value: A dictionary containing the configuration.
        """

        # The raw configuration dictionary
        self._raw = value

        # A cache containing translated values
        self._xlated = {}

    @classmethod
    def lookup(cls, name):
        """
        Look up a ``Binding`` subclass given a name or path.

        :param name: The name of the desired ``Binding``, or a path.
                     If ``name`` is a simple name (i.e., not preceded
                     by "/"), the named attribute on this ``Config``
                     subclass is returned.  If ``name`` is a path
                     (preceded by "/", with elements separated by
                     "/"), the tree of options rooted at this
                     ``Config`` subclass is returned.  Finally,
                     ``name`` may also be a list of path elements,
                     which will also result in a traversal of the tree
                     of options.

        :returns: An instance of ``Binding`` corresponding to the
                  value of ``name``.
        """

        # Do the simple tests first
        if not name:
            raise KeyError(name)
        elif not isinstance(name, six.string_types):
            # If it's just one element, look it up
            if len(name) == 1:
                return cls._attrs[name[0]]

            # OK, clean out any empty pieces
            path = [p for p in name if p]
        elif name[0] != '/':
            return cls._attrs[name]
        else:
            # OK, split the name up
            path = [p for p in name.split('/') if p]

        # Iterate down through the config tree
        item = cls
        for elem in path:
            item = getattr(item, '_attrs', {})[elem]

        # Return the final item
        return item

    @classmethod
    def extend(cls, attr, option, key=None):
        """
        Register a new option on the ``Config`` subclass.

        :param attr: The name of the new option.  This has the same
                     form as the ``name`` parameter to the
                     ``lookup()`` method, with the restriction that
                     the last element of the path must not already be
                     defined.
        :param option: A callable, either an instance of ``Option`` or
                       a subclass of ``Config``.  The callable will be
                       called with a value drawn from the
                       configuration, and must return the translated
                       value.  In addition, the callable must provide
                       some attributes, such as ``__default__`` and
                       ``__schema__``.
        :param key: The configuration key from which the value will be
                    drawn.  If not provided, will be the same as the
                    attribute name.
        """

        # Interpret attr
        if not attr:
            raise ConfigException('invalid attribute name')
        elif not isinstance(attr, six.string_types):
            # Clean out the path and pop off the last element as the
            # final attribute name
            path = [p for p in attr if p]
            attr = path.pop()
        elif attr[0] != '/':
            path = []
        else:
            # OK, split the name up
            path = [p for p in attr.split('/') if p]
            attr = path.pop()

        # Beware of the reserved attributes
        if attr in RESERVED:
            raise ConfigException("attribute '%s' is reserved; choose an "
                                  "alternate name and use a key" % attr)

        # Determine the key name
        if not key:
            key = attr

        # Extend the desired option
        if path:
            ext_opt = cls.lookup(path)
            ext_opt._extend(attr, key, option)
        else:
            cls._extend(attr, key, option)

    @classmethod
    def _extend(cls, attr, key, option):
        """
        Register a new option on the ``Config`` subclass.

        :param attr: The name of the attribute the option will be
                     available under.
        :param key: The configuration key from which the value will be
                    drawn.
        :param option: A callable, either an instance of ``Option`` or
                       a subclass of ``Config``.  The callable will be
                       called with a value drawn from the
                       configuration, and must return the translated
                       value.  In addition, the callable must provide
                       some attributes, such as ``__default__`` and
                       ``__schema__``.
        """

        # First, sanity-check that there's no overlaps
        if attr in cls._attrs:
            raise ConfigException("multiple definitions for attribute '%s'" %
                                  attr)
        elif key in cls._keys:
            raise ConfigException("multiple definitions for configuration "
                                  "key '%s'" % key)

        # Create a binding
        binding = Binding(attr, key, option)

        # Put it in the trackers...
        cls._attrs[attr] = binding
        cls._keys[key] = binding

        # Add it to the class
        setattr(cls, attr, binding)

        # Invalidate cached schemas
        _schema_invalidate(cls)

    @classmethod
    def validate(cls, value):
        """
        Validates a configuration dictionary against this ``Config``
        subclass using JSON-Schema.  Raises a
        ``jsonschema.ValidationError`` if the configuration dictionary
        is not valid.

        :param value: The configuration dictionary.
        """

        # Perform the validation
        jsonschema.validate(value, cls.__schema__)

    load = Load()

    __schema__ = Schema()


# Configuration attributes that are reserved
RESERVED = frozenset(attr for attr in dir(BaseConfig)
                     if not attr.startswith('__'))


class ConfigMeta(type):
    """
    Metaclass for ``Config``.  This wraps ``Option`` instances and
    ``Config`` subclasses in the class configuration into ``Binding``
    instances, and maintains mappings from attributes and
    configuration value keys to those ``Binding`` instances.  It also
    initializes schema-related class attributes, such as
    ``_schema_raw``, ``_schema_cache``, and ``_parents``.
    """

    def __new__(mcs, name, bases, namespace):
        """
        Construct a ``Config`` subclass.

        :param name: The name of the ``Config`` subclass to construct.
        :param bases: A tuple of base classes.
        :param namespace: A dictionary containing the class
                          definition.

        :returns: A newly constructed ``Config`` subclass.
        """

        # The dictionaries mapping attributes and keys to options
        attrs = {}
        keys = {}
        children = set()

        # Prepare the filtered namespace
        filtered = {
            '_attrs': attrs,
            '_keys': keys,
            '_schema_raw': {'type': 'object'},
            '_schema_cache': None,
            '_parents': set(),
        }
        for attr, value in namespace.items():
            # Beware of the reserved attributes
            if attr in RESERVED:
                raise ConfigException("attribute '%s' is reserved; choose an "
                                      "alternate name and use a key" % attr)

            # Treat the __schema__ attribute specially
            if attr == '__schema__':
                value['type'] = 'object'
                filtered['_schema_raw'] = value
                continue

            # Special handling for Option instances and Config
            # subclasses.  Note that Config cannot have any inner
            # classes, as this test would blow up with a NameError
            if (attr[0] != '_' and
                    (isinstance(value, Option) or
                     (inspect.isclass(value) and issubclass(value, Config)))):
                # Need to update the _parents attribute later
                children.add(value)

                # Derive the key
                key = getattr(value, '__key__', None) or attr

                # Make sure key is valid and that there are no
                # collisions
                if key in keys:
                    raise ConfigException("multiple definitions for "
                                          "configuration key '%s'" % key)

                # Wrap the value in a Binding
                value = Binding(attr, key, value)

                # Save it in the attrs and keys dictionaries
                attrs[attr] = value
                keys[key] = value

            # Copy the value over into the filtered namespace
            filtered[attr] = value

        # Construct the class
        cls = super(ConfigMeta, mcs).__new__(mcs, name, bases, filtered)

        # Update the _parents attribute of all the child configs
        for child in children:
            child._parents.add(cls)

        # Return the constructed class
        return cls


@six.add_metaclass(ConfigMeta)
class Config(BaseConfig):
    """
    Configuration class.  To declare a configuration, begin by
    subclassing this class.  Scalar options (e.g., integers, strings,
    etc.) may be defined by assigning an instance of ``Option`` to an
    appropriate class attribute.  For dictionary options, declare an
    inner class that also extends ``Config``, or create such a class
    and assign it to an appropriate class attribute.  (Note: for
    ``Config`` subclasses, that assignment should be the class itself,
    not an instance of the class.)  Note that class attributes
    beginning with an underscore ("_") are treated specially and
    should be avoided.  Also note that there are a handful of special
    class methods that are not available via class instances.

    Special class attributes

    * ``__key__``
        If set on an inner class, this class attribute may be used to
        override the default configuration key selection.  By default,
        the key associated with an inner class will be the class name;
        this option allows any arbitrary key to be used.  The value
        will still be accessible via the normal means of accessing the
        instance attribute having the name of the inner class.

    * ``__schema__``
        A dictionary containing a partial JSON-Schema dictionary.  The
        "type", "description", "properties", and "required" keys in
        this dictionary are ignored and replaced with computed data,
        with the "description" taken from the subclass docstring.  Any
        other values are preserved, and the constructed class will
        have a ``__schema__`` property containing a complete
        JSON-Schema dictionary which may be used to validate values.
        Note that *instances* of the class will *not* have a
        ``__schema__`` attribute or property; only the class itself
        will have the final schema.

    Special class methods

    * lookup()
        Given the name of an attribute or a path to a deeply nested
        attribute, this method resolves that name to an instance of a
        special private ``Binding`` class.  The ``Binding`` class acts
        as a proxy to the underlying ``Config`` subclass or ``Option``
        instance, but also includes the ``__key__`` and ``__attr__``
        attributes, which contain the configuration dictionary key and
        the class attribute name, respectively.

    * extend()
        Given the name of an attribute or a path to a deeply nested
        attribute, this method installs a new ``Option`` instance or
        ``Config`` subclass, giving it that name.  This allows dynamic
        extension of the configuration to support dynamically loaded
        modules, such as command interpreters.  It also dynamically
        updates the ``__schema__`` class attribute.

    * validate()
        Given a dictionary read from a file (typically via
        ``yaml.load()``), this routine uses the ``jsonschema`` package
        to validate that the dictionary conforms to the declared
        configuration schema.  The schema used for validation is drawn
        from the ``__schema__`` class attribute.
    """

    pass


class Option(object):
    """
    Describe a configuration option.  This class is used to represent
    all scalar configuration options, such as integers.
    """

    def __init__(self, default=_unset, help='', schema=None,
                 enum=None, key=None):
        """
        Initialize an ``Option`` instance.

        :param default: The default value of the option.  If none is
                        provided, the option will be required.
        :param help: Help text describing the purpose of the option
                     and any other information required by the user.
                     Optional.
        :param schema: A dictionary containing a partial JSON-Schema
                       dictionary.  The "description", "default", and
                       "enum" keys in this dictionary are ignored and
                       replaced with computed data, with "description"
                       taken from the ``help`` parameter.  Any other
                       values are preserved, and the final ``Option``
                       instance will have a ``__schema__`` instance
                       attribute containing a complete JSON-Schema
                       dictionary which may be used to validate
                       values.  Optional.
        :param enum: A list of legal values for the option to take.
                     If not provided, the values that may be given are
                     only constrained by the declared ``schema`` for
                     the option.
        :param key: The name of the configuration dictionary key
                    corresponding to the option.  By default, this is
                    the name of the attribute to which the ``Option``
                    instance is assigned.
        """

        self.__default__ = default
        self.__doc__ = help

        if key:
            # Only set __key__ if one is given
            self.__key__ = key

        # Compute the schema
        self._schema_raw = schema or {}

        # Set up default and description
        if default is not _unset:
            self._schema_raw['default'] = default
        if help:
            self._schema_raw['description'] = help

        # Include enumerated values, if specified
        if enum:
            self._schema_raw['enum'] = enum

        # Initialize the parents set
        self._parents = set()

    def __call__(self, value):
        """
        Translate the raw configuration value into the internal
        representation.  For scalar options described by an
        ``Option``, this internal representation will be identical to
        the raw configuration value.

        :param value: The raw configuration value.

        :returns: The internal representation.
        """

        return value

    def _extend(self, attr, key, option):
        """
        For the ``Config`` subclasses, the ``_extend()`` method is a class
        method that registers a new option.  This is meaningless for
        ``Option`` instances, so this implementation raises a
        ``ConfigException`` to highlight those cases.

        :param attr: The name of the attribute the option will be
                     available under.
        :param key: The configuration key from which the value will be
                    drawn.
        :param option: A callable, either an instance of ``Option`` or
                       a subclass of ``Config``.  The callable will be
                       called with a value drawn from the
                       configuration, and must return the translated
                       value.  In addition, the callable must provide
                       some attributes, such as ``__default__`` and
                       ``__schema__``.
        """

        raise ConfigException("options cannot be extended")

    def validate(self, value):
        """
        Validates a configuration dictionary against this ``Option``
        instance using JSON-Schema.  Raises a
        ``jsonschema.ValidationError`` if the configuration dictionary
        is not valid.

        :param value: The configuration dictionary.
        """

        # Perform the validation
        jsonschema.validate(value, self.__schema__)

    @property
    def __schema__(self):
        """
        Retrieve the schema for the option.
        """

        return self._schema_raw


class ListOption(Option):
    """
    Describe a configuration option taking a list value.  This may be
    used with "list"-style values, where each item has the same
    schema, or it may be used with "tuple"-style values, where each
    item has a distinct schema that applies only to it.
    """

    def __init__(self, default=_unset, help='', schema=None,
                 items=None, key=None):
        """
        Initialize a ``ListOption`` instance.

        :param default: The default value of the option.  If none is
                        provided, the option will be required.
        :param help: Help text describing the purpose of the option
                     and any other information required by the user.
                     Optional.
        :param schema: A dictionary containing a partial JSON-Schema
                       dictionary.  The "type", "description",
                       "default", and "items" keys in this dictionary
                       are ignored and replaced with computed data,
                       with "description" taken from the ``help``
                       parameter and "items" taken from the ``items``
                       parameter.  Any other values are preserved, and
                       the final ``Option`` instance will have a
                       ``__schema__`` instance attribute containing a
                       complete JSON-Schema dictionary which may be
                       used to validate values.  Optional.
        :param items: May be either a single option description or a
                      sequence of such descriptions.  (Here an "option
                      description" consists of either an ``Option``
                      instance or a ``Config`` subclass.)  If this is
                      a single option description, the option
                      description is applied to all elements of the
                      list in the configuration; if it is a sequence,
                      the elements in the sequence will be applied to
                      the corresponding element of the list in the
                      configuration.  (The first is described as
                      "list" mode, and the second is described as
                      "tuple" mode.)
        :param key: The name of the configuration dictionary key
                    corresponding to the option.  By default, this is
                    the name of the attribute to which the ``Option``
                    instance is assigned.
        """

        # Initialize the superclass
        super(ListOption, self).__init__(
            default=default, help=help, schema=schema, key=key)

        # Update the schema type
        self._schema_raw['type'] = 'array'

        # Determine the interface mode, normalize the items, update
        # parent sets, and create an appropriate _attrs dictionary for
        # the lookup() algorithm
        if items is None:
            self._mode = 'noxlate'
            self._items = None
            self._attrs = {}
        else:
            if isinstance(items, collections.Sequence):
                # Keep track of the mode, too
                self._mode = 'tuple'
                self._items = []
                self._attrs = {}
                for idx, item in enumerate(items):
                    if item:
                        item._parents.add(self)
                        self._attrs['[%d]' % idx] = item
                    self._items.append(item or None)
            else:
                # We're a simple list
                self._mode = 'list'
                self._items = items
                self._attrs = {'[]': items}
                items._parents.add(self)

        # Prepare a schema cache
        self._schema_cache = None

    def __call__(self, value):
        """
        Translate the raw configuration value into the internal
        representation.  For list options, the option descriptions
        passed to the ``items`` tuple will control the translation of
        list items.

        :param value: The raw configuration value.

        :returns: The internal representation.
        """

        if self._mode == 'noxlate':
            # Return the value unchanged
            return value
        elif self._mode == 'list':
            # For a simple list, convert each value
            return [self._items(v) for v in value]
        else:
            # For a tuple, convert all the items for which we have a
            # value
            result = []
            for idx, val in enumerate(value):
                result.append(self._items[idx](val) if idx < len(self._items)
                              else val)
            return result

    @property
    def __schema__(self):
        """
        Retrieve the schema for the option.
        """

        # Have we cached the schema yet?
        if self._schema_cache is None:
            # Begin with a copy of the raw schema
            schema = copy.deepcopy(self._schema_raw)

            # Most of the schema has been initialized; we just need to
            # assemble the property information
            if self._mode == 'list':
                schema['items'] = self._items.__schema__
            elif self._mode == 'tuple':
                schema['items'] = [item.__schema__ if item else {}
                                   for item in self._items]
            # In the noxlate case, we don't set 'items'

            # Cache the final schema
            self._schema_cache = schema

        return self._schema_cache
