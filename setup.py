import os
import sys

from setuptools import setup, find_packages

# Utility function to read the README fule
def readfile(filename):
    with open(filename) as f:
        return f.read()


# Utility function to read the requirement file
def readreq(filename):
    result = []
    with open(filename) as f:
        for eachreq in f:
            eachreq = eachreq.strip()
            if (eachreq.startswith('-e') or eachreq.startswith('http')
                    or eachreq.startswith('git')):
                index = eachreq.find('#egg=')
                if index >= 0:
                    eachreq = eachreq[index + 5:].partition('#')[0].strip()
                else:
                    eachreq = eachreq.partition('#')[0].strip()

            # Check if any requirement file is specified
            elif eachreq.startswith('-r'):
                eachreq = eachreq[2:].partition(' ')[2].strip()
                result = result + readreq(eachreq)
                continue

            # If requirement is empty
            elif not eachreq:
                continue

            result.append(eachreq)
    return result

# The setup script
setup(
    name='striker',
    version='0.1.0',
    author='Kevin L. Mitchell',
    author_email='kevin.mitchell@rackspace.com',
    url='https://github.rackspace.com/O3Eng-infra/striker',
    description='Job management software',
    long_description=readfile('README.rst'),
    entry_points={
        'console_scripts': [
            'striker = striker.bootstrap_setup:bootstrap.console',
        ],
        'striker.accounts': [
            'literal = striker.account:AccountLiteral',
            'env = striker.account:AccountEnvironment',
        ],
        'striker.artifactstores': [
            'ssh = striker.artifactstore:SSHStore',
            'http = striker.artifactstore:HTTPStore',
            'cloudfiles = striker.artifactstore:CloudFilesStore',
        ],
    },
    packages=find_packages(exclude=['tests', 'tests.*']),
    install_requires=readreq('requirements.txt'),
    tests_require=readreq('test-requirements.txt'),
)
