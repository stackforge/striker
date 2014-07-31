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
import shlex
import shutil
import subprocess

import six

from striker.common import utils


class ExecResult(Exception):
    """
    Encapsulate the results of calling a command.  This class extends
    ``Exception`` so that it can be raised in the event of a command
    failure.  The command executed is available in both list (``cmd``)
    and plain text (``cmd_text``) forms.  If the command is executed
    with ``capture_output``, the standard output (``stdout``) and
    standard error (``stderr``) streams will also be available.  The
    command return code is available in the ``return_code`` attribute.
    """

    def __init__(self, cmd, stdout, stderr, return_code):
        """
        Initialize an ``ExecResult``.

        :param cmd: The command, in list format.
        :param stdout: The standard output from the command execution.
        :param stderr: The standard error from the command execution.
        :param return_code: The return code from executing the
                            command.
        """

        # Store all the data
        self.cmd = cmd
        self.stdout = stdout
        self.stderr = stderr
        self.return_code = return_code

        # Form the command text
        comps = []
        for comp in cmd:
            # Determine if the component needs quoting
            if ' ' in comp or '"' in comp or "'" in comp:
                # Escape any double-quotes
                parts = comp.split('"')
                comp = '"%s"' % '\\"'.join(parts)

            comps.append(comp)

        # Save the command text
        self.cmd_text = ' '.join(comps)

        # Formulate the message
        if return_code:
            msg = ("'%s' failed with return code %s" %
                   (self.cmd_text, return_code))
        elif stderr:
            msg = "'%s' said: %s" % (self.cmd_text, stderr)
        elif stdout:
            msg = "'%s' said: %s" % (self.cmd_text, stdout)
        else:
            msg = "'%s' succeeded" % (self.cmd_text,)

        # Initialize ourselves as an exception
        super(ExecResult, self).__init__(msg)

    def __nonzero__(self):
        """
        Allows conversion of an ``ExecResult`` to boolean, based on
        the command return code.  If the return code was 0, the object
        will be considered ``True``; otherwise, the object will be
        considered ``False``.

        :returns: ``True`` if the command succeeded, ``False``
                  otherwise.
        """

        return not bool(self.return_code)
    __bool__ = __nonzero__


class Environment(dict):
    """
    Describes an environment that can be used for execution of
    subprocesses.  Virtual environments can be created by calling the
    ``create_venv()`` method, which returns an independent instance of
    ``Environment``.
    """

    def __init__(self, logger, environ=None, cwd=None, venv_home=None):
        """
        Initialize a new ``Environment``.

        :param logger: An object compatible with ``logging.Logger``.
                       This will be used to emit logging information.
        :param environ: A dictionary containing the environment
                        variables.  If not given, ``os.environ`` will
                        be used.
        :param cwd: The working directory to use.  If relative, will
                    be interpreted relative to the current working
                    directory.  If not given, the current working
                    directory will be used.
        :param venv_home: The home directory for the virtual
                          environment.
        """

        super(Environment, self).__init__(environ or os.environ)

        # Save the logger
        self.logger = logger

        # Change to the desired working directory, then save the full
        # path to it
        self.cwd = os.getcwd()
        if cwd:
            self.chdir(cwd)

        # Save the virtual environment home
        self.venv_home = venv_home

    def __call__(self, cmd, capture_output=False, cwd=None, do_raise=True,
                 retry=None, max_tries=5):
        """
        Execute a command in the context of this environment.

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

        # Sanity-check arguments
        if not retry or max_tries < 1:
            max_tries = 1

        # Determine the working directory to use
        cwd = utils.canonicalize_path(self.cwd, cwd) if cwd else self.cwd

        # Turn simple strings into lists of tokens
        if isinstance(cmd, six.string_types):
            self.logger.debug("Notice: splitting command string '%s'" %
                              cmd)
            cmd = shlex.split(cmd)

        self.logger.debug("Executing command: %r (cwd %s)" % (cmd, cwd))

        # Prepare the keyword arguments for the Popen call
        kwargs = {
            'env': self,
            'cwd': cwd,
            'close_fds': True,
        }

        # Set up stdout and stderr
        if capture_output or (retry and max_tries > 1):
            kwargs.update({
                'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE,
            })

        # Perform the tries in a loop
        for trial in utils.backoff(max_tries):
            if trial:
                self.logger.warn("Failure caught; retrying command "
                                 "(try #%d)" % (trial + 1))

            # Call the command
            child = subprocess.Popen(cmd, **kwargs)
            stdout, stderr = child.communicate()
            result = ExecResult(cmd, stdout, stderr, child.returncode)

            # Check if we need to retry
            if retry and not result and retry(result):
                continue

            break
        else:
            # Just log a warning that we couldn't retry
            self.logger.warn("Unable to retry: too many attempts")

        # Raise an exception if requested
        if not result and do_raise:
            raise result

        return result

    def chdir(self, path):
        """
        Change the working directory.

        :param path: The path to change to.  If relative, will be
                     interpreted relative to the current working
                     directory.

        :returns: The new working directory.
        """

        self.cwd = utils.canonicalize_path(self.cwd, path)

        return self.cwd

    def create_venv(self, path, rebuild=False, **kwargs):
        """
        Create a new, bare virtual environment rooted at the given
        directory.  No packages will be installed, except what
        ``virtualenv`` installs.  Returns a new ``Environment`` set up
        for the new virtual environment, with the working directory
        set to be the same as the virtual environment directory.  Any
        keyword arguments will override system environment variables
        in the new ``Environment`` object.

        :param path: The path to create the virtual environment in.
                     If relative, will be interpreted relative to the
                     current working directory.
        :param rebuild: If ``True``, the virtual environment will be
                        rebuilt even if it already exists.  If
                        ``False`` (the default), the virtual
                        environment will only be rebuilt if it doesn't
                        already exist.
        :returns: A new ``Environment`` object.
        """

        # Determine the new virtual environment path
        path = utils.canonicalize_path(self.cwd, path)

        self.logger.debug("Preparing virtual environment %s" % path)

        # Check if we need to rebuild the virtual environment
        if os.path.exists(path):
            if rebuild:
                # Blow away the old tree
                self.logger.info("Destroying old virtual environment %s" %
                                 path)
                shutil.rmtree(path)
            else:
                self.logger.info("Using existing virtual environment %s" %
                                 path)
        else:
            # We'll need to create it
            rebuild = True

        # Create the new virtual environment
        if rebuild:
            self.logger.info("Creating virtual environment %s" % path)
            self(['virtualenv', path])

        # Set up the environment variables that are needed
        kwargs.setdefault('VIRTUAL_ENV', path)
        bindir = os.path.join(path, 'bin')
        kwargs.setdefault('PATH', '%s%s%s' %
                          (bindir, os.pathsep, self['PATH']))

        # Set up and return the new Environment
        new_env = self.__class__(self.logger, environ=self, cwd=path,
                                 venv_home=path)
        new_env.update(kwargs)
        return new_env
