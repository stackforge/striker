#!/bin/sh

########################## Various utility functions ##########################

# Canonicalize a directory name
canon_dir () {
    (cd "$1" && pwd -P)
}

# Extract the argument from "--foo=..." style arguments
get_arg () {
    echo "$1" | sed 's/[^=]*=//'
}

# Add a parameter to the set of parameters with which to invoke
# nosetests
add_params () {
    if [ x"${params}" = x ]; then
	params="$*"
    else
	params="${params} $*"
    fi
}

# An alias for the Python interpreter from the virtual environment
python () {
    ${venv_path}/bin/python "$@"
}

# An alias for pip from the virtual environment
pip () {
    # Invoke using the python from the virtual environment; this works
    # around spaces being present in the "#!" line
    python ${venv_path}/bin/pip "$@"
}

# An alias for pep8, using the virtual environment if requested
run_pep8 () {
    if [ ${venv} = yes ]; then
	# Invoke using the python from the virtual environment; this
	# works around spaces being present in the "#!" line
	python ${venv_path}/bin/pep8 "$@"
    else
	pep8 "$@"
    fi
}

# An alias for nosetests, using the virtual environment if requested
run_nosetests () {
    if [ ${venv} = yes ]; then
	# Invoke using the python from the virtual environment; this
	# works around spaces being present in the "#!" line
	python ${venv_path}/bin/nosetests "$@"
    else
	nosetests "$@"
    fi
}

# Output a usage message
usage () {
    cat >&2 <<EOF
Usage: ${prog} [options] [<TESTS>]

Execute the Striker test suite.

Options:
    -h
    --help     Outputs this help text.

    -V
    --virtual-env
               Set up and use a virtual environment for testing.

    -N
    --no-virtual-env
               Do not set up or use a virtual environment for testing.

    -r
    --reset    Resets the virtual environment prior to building it.

    -p
    --pep8     Execute only the PEP8 compliance check.

    -P
    --no-pep8  Do not execute the PEP8 compliance check.

    -c
    --coverage Generate a coverage report

    -H <DIR>
    --coverage-html=<DIR>
               Specify the directory to contain the HTML coverage
               report.

    <TESTS>    A list of test specifications for nosetests.
EOF

    exit ${1:-1}
}

################################ Initialization ###############################

prog=`basename $0`
dir=`dirname $0`
dir=`canon_dir "${dir}"`

# Initialize parameters for invoking nosetests
params=

# Initialize other variables
venv=ask
reset=false
pep8=yes
coverage=no
cov_html=cov_html

############################## Process arguments ##############################

while [ $# -gt 0 ]; do
    case "$1" in
	-h|--help)
	    usage 0 2>&1
	    ;;
	-V|--virtual-env)
	    venv=yes
	    ;;
	-N|--no-virtual-env)
	    venv=no
	    ;;
	-r|--reset)
	    reset=true
	    ;;
	-p|--pep8)
	    pep8=only
	    ;;
	-P|--no-pep8)
	    pep8=no
	    ;;
	-c|--coverage)
	    coverage=yes
	    ;;
	-H|--coverage-html)
	    shift
	    cov_html="$1"
	    ;;
	--coverage-html=*)
	    cov_html=`get_arg "$1"`
	    ;;
	--*)
	    echo "Unrecognized option \"$1\"" >&2
	    usage
	    ;;
	*)
	    add_params "$1"
	    ;;
    esac

    shift
done

############################ Set up the environment ###########################

# Ask if we should use a virtual environment
venv_path="${dir}/.venv"
if [ ${venv} = ask ]; then
    if [ -d ${venv_path} ]; then
	venv=yes
    else
	echo -n "No virtual environment found; create one? (Y/n) "
	read use_venv
	if [ "x${use_venv}" = "xY" -o "x${use_venv}" = "xy" -o \
	     "x${use_venv}" = "x" ]; then
	    venv=yes
	else
	    venv=no
	fi
    fi
fi

# Set up the virtual environment if requested
if [ ${venv} = yes ]; then
    # Reset the virtual environment if requested
    if [ ${reset} = true -a -d ${venv_path} ]; then
	echo "Forced reset of virtual environment"
	rm -rf ${venv_path}
    fi

    # Now create the virtual environment
    if [ ! -d ${venv_path} ]; then
	echo "Creating virtual environment"
	virtualenv ${venv_path}
	if [ $? -ne 0 ]; then
	    echo "Failed to create virtual environment" >&2
	    exit 1
	fi
    fi

    echo "Installing/updating requirements in virtual environment"
    pip install -U -r ${dir}/requirements.txt -r ${dir}/test-requirements.txt
    if [ $? -ne 0 ]; then
	echo "Failed to install/update requirements in virtual environment" >&2
	exit 1
    fi

    echo "Installing striker setup in the virtual environment"
    python ${dir}/setup.py install
    if [ $? -ne 0 ]; then
        echo "Failed to install striker setup in virtual environment" >&2
        exit 1
    fi

    export VIRTUAL_ENV=${venv_path}
fi

export BASE_DIR=${dir}

################################ Run the tests ################################

errors=0
if [ ${pep8} != only ]; then
    # Set up the options for nosetests
    options="-v"
    if [ ${coverage} = yes ]; then
	options="${options} --with-coverage --cover-branches"
	options="${options} --cover-package=striker"
	options="${options} --cover-html --cover-html-dir=${cov_html}"
    fi

    # Need to restrict tests to just the test directory
    if [ x"${params}" = x ]; then
	params=tests
    fi

    # Run nosetests
    echo
    echo "Testing Python code:"
    echo
    run_nosetests ${options} ${params}
    if [ $? -ne 0 ]; then
	echo "Tests on Striker failed" >&2
	errors=`expr ${errors} + 1`
    fi
fi

# Run pep8
if [ ${pep8} != no ]; then
    echo
    echo "Running PEP8 tests:"
    echo
    run_pep8 ${dir}/striker ${dir}/tests
    if [ $? -ne 0 ]; then
	echo "Pep8 compliance test failed" >&2
	errors=`expr ${errors} + 1`
    fi
fi

if [ ${errors} -gt 0 ]; then
    echo
    echo "Test failures encountered!" >&2
else
    echo
    echo "Test suite successful!" >&2
fi

exit ${errors}
