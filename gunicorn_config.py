command = '/usr/bin/gunicorn'
pythonpath = './netbox/'
timeout = 30
workers = 3
errorlog = '-'
accesslog = '-'
capture_output = False
log_level = 'debug'