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
import time


def canonicalize_path(cwd, path):
    """
    Canonicalizes a path relative to a given working directory.

    :param cwd: The working directory to interpret ``path`` relative
                to.
    :param path: The path to canonicalize.  If relative, it will be
                 interpreted relative to ``cwd``.

    :returns: The absolute path.
    """

    if not os.path.isabs(path):
        path = os.path.join(cwd, path)

    return os.path.abspath(path)


def backoff(max_tries):
    """
    A generator to perform simplified exponential backoff.  Yields up
    to the specified number of times, performing a ``time.sleep()``
    with an exponentially increasing sleep time (starting at 1 second)
    between each trial.  Yields the (0-based) trial number.

    :param max_tries: The maximum number of tries to attempt.
    """

    # How much time will we sleep next time?
    sleep = 1

    for i in range(max_tries):
        # Yield the trial number
        yield i

        # We've re-entered the loop; sleep, then increment the sleep
        # time
        time.sleep(sleep)
        sleep <<= 1
