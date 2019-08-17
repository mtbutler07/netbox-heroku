command = '/usr/bin/gunicorn'
pythonpath = './netbox/'
bind = '0.0.0.0:8001'
workers = 3
errorlog = '-'
accesslog = '-'
capture_output = False