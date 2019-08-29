#!/usr/bin/sh
for f in ./share/lifted/providers/*/playbook.yaml; do
    echo "linting $f"
    yamllint -c ./tests/yamllint.conf "$f"
done
