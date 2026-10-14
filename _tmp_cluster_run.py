import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
exec(open('scripts/_cluster_cron_run.py', encoding='utf-8').read(), {'__name__': '__main__', '__file__': 'scripts/_cluster_cron_run.py'})
