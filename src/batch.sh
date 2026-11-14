#!/bin/bash
while read -r u; do [ -z "$u" ] && continue; python3 probe.py "$u" 2>&1 | cut -c1-520 | head -9; done
