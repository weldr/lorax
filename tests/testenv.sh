#!/bin/sh

top_srcdir="${top_srcdir:-}"
top_buildir="${top_builddir:-}"
PYTHONPATH="${PYTHONPATH:-}"

if [ -z "$top_srcdir" ]; then
    echo "*** top_srcdir must be set"
    exit 1
fi

# If no top_builddir is set, use top_srcdir
: "${top_builddir:=$top_srcdir}"

if [ -z "$PYTHONPATH" ]; then
    PYTHONPATH="${top_builddir}/src/:${top_srcdir}/tests/lib"
else
    PYTHONPATH="${PYTHONPATH}:${top_srcdir}/src/:${top_srcdir}:${top_srcdir}/tests/lib"
fi

export PYTHONPATH
export top_srcdir
export top_builddir
