#!/bin/bash

set -ex

# See https://github.com/python-trio/trio/issues/334
YAPF_VERSION=0.22.0

if [ "$TRAVIS_OS_NAME" = "osx" ]; then
    curl -Lo macpython.pkg https://www.python.org/ftp/python/${MACPYTHON}/python-${MACPYTHON}-macosx10.9.pkg
    sudo installer -pkg macpython.pkg -target /
    ls /Library/Frameworks/Python.framework/Versions/*/bin/
    PYTHON_EXE=/Library/Frameworks/Python.framework/Versions/*/bin/python3
    sudo $PYTHON_EXE -m pip install virtualenv
    $PYTHON_EXE -m virtualenv testenv
    source testenv/bin/activate
fi

pip install -U pip setuptools wheel pep517

if [ "$CHECK_FORMATTING" = "1" ]; then
    pip install yapf==${YAPF_VERSION}
    if ! yapf -rpd setup.py pytest_trio; then
        cat <<EOF
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

Formatting problems were found (listed above). To fix them, run

   pip install yapf==${YAPF_VERSION}
   yapf -rpi setup.py pytest_trio

in your local checkout.

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
EOF
        exit 1
    fi
    exit 0
fi

python -m pep517.build --source --out-dir dist/ .
python -m pip install dist/*.tar.gz

if [ "$CHECK_DOCS" = "1" ]; then
    pip install -Ur ci/rtd-requirements.txt
    cd docs
    # -n (nit-picky): warn on missing references
    # -W: turn warnings into errors
    sphinx-build -nW  -b html source build
else
    # Actual tests
    pip install -Ur test-requirements.txt

    mkdir empty
    cd empty

    # These environment variables ensure that the import of the pytest-trio plugin is covered
    # even if pytest-trio is loaded before pytest-cov. See https://pytest-cov.readthedocs.io/en/latest/plugins.html
    env COV_CORE_SOURCE=pytest_trio COV_CORE_CONFIG=.coveragerc COV_CORE_DATAFILE=.coverage pytest

    bash <(curl -s https://codecov.io/bash)
fi
