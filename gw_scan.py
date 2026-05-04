#!/usr/bin/env python3
import os, re

routers_dir = 'backend/app/gateway/routers'
for fname in sorted(os.listdir(routers_dir)):
    if not fname.endswith('.py') or fname == '__init__.py':
        continue
    path = os.path.join(routers_dir, fname)
    content = open(path, encoding='utf-8').read()
    print(f'=== {fname} ===')
    # Find all router.XXX("path") or router.XXX("/path") patterns
    for match in re.finditer(r'@router\.(\w+)\([\'"]([^\'")]+)[\'"]', content):
        method = match.group(1).upper()
        path = match.group(2)
        print(f'  {method:6} {path}')
    print()