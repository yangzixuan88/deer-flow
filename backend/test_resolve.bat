@echo off
set "DEERFLOW_HOST_PATH=E:\OpenClaw-Base\deerflow"
set "PYTHONPATH=."
python -c "import os; f=open(r'E:\temp_out.txt','w'); import sys; sys.path.insert(0, '.'); import yaml; d=yaml.safe_load(open('../config.yaml',encoding='utf-8')); hp=d['sandbox']['mounts'][0]['host_path']; f.write('hp='+repr(hp)+'\n'); f.write('env='+repr(os.environ.get('DEERFLOW_HOST_PATH'))+'\n'); import packages.harness.deerflow.config.app_config as ac; f.write('resolve='+repr(ac.AppConfig.resolve_env_variables(hp))+'\n'); f.close(); print('done')"
