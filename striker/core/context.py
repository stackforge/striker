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

from striker.core import environment


class Context(object):
    """
    Execution context.  Objects of this class contain all the basic
    configuration data needed to perform a task.
    """

    def __init__(self, workspace, config, logger,
                 debug=False, dry_run=False, **extras):
        """
        Initialize a ``Context`` object.

        :param workspace: The name of a temporary working directory.
                          The directory must exist.
        :param config: An object containing configuration data.  The
                       object should support read-only attribute-style
                       access to the configuration settings.
        :param logger: An object compatible with ``logging.Logger``.
                       This will be used by all consumers of the
                       ``Context`` to emit logging information.
        :param debug: A boolean, defaulting to ``False``, indicating
                      whether debugging mode is active.
        :param dry_run: A boolean, defaulting to ``False``, indicating
                        whether permanent changes should be effected.
                        This should be used to control whether files
                        are uploaded, for instance.
        :param extras: Keyword arguments specifying additional data to
                       be stored in the context.  This could be, for
                       instance, account data.
        """

        # Store basic context data
        self.workspace = workspace
        self.config = config
        self.logger = logger
        self.debug = debug
        self.dry_run = dry_run

        # Extra data--things like accounts
        self._extras = extras

        # Environment
        self._environ = None

    def __getattr__(self, name):
        """
        Provides access to the extra data specified to the constructor.

        :param name: The name of the extra datum to retrieve.

        :returns: The value of the extra datum.
        """

        if name not in self._extras:
            raise AttributeError("'%s' object has no attribute '%s'" %
                                 (self.__class__.__name__, name))

        return self._extras[name]

    @property
    def environ(self):
        """
        Access the environment.  The environment is a dictionary of
        environment variables, but it is also a callable that can be
        used to invoke shell commands.

        :param cmd: The command to execute, as either a bare string or
                    a list of arguments.  If a string, it will be
                    split into a list using ``shlex.split()``.  Note
                    that use of bare strings for this argument is
                    discouraged.
        :param capture_output: If ``True``, standard input and output
                               will be captured, and will be available
                               in the result.  Defaults to ``False``.
                               Note that this is treated as implicitly
                               ``True`` if the ``retry`` parameter is
                               provided.
        :param cwd: Gives an alternate working directory from which to
                    run the command.
        :param do_raise: If ``True`` (the default), an execution
                         failure will raise an exception.
        :param retry: If provided, must be a callable taking one
                      argument.  Will be called with an instance of
                      ``ExecResult``, and can return ``True`` to
                      indicate that the call should be retried.
                      Retries are performed with an exponential
                      backoff controlled by ``max_tries``.
        :param max_tries: The maximum number of tries to perform
                          before giving up, if ``retry`` is specified.
                          Retries are performed with an exponential
                          backoff: the first try is performed
                          immediately, and subsequent tries occur
                          after a sleep time that starts at one second
                          and is doubled for each try.

        :returns: An ``ExecResult`` object containing the results of
                  the execution.  If the return code was non-zero and
                  ``do_raise`` is ``True``, this is the object that
                  will be raised.
        """

        # Construct the environment if necessary
        if self._environ is None:
            self._environ = environment.Environment(self.logger)

        return self._environ
