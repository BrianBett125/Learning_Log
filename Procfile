web: gunicorn ll_project.wsgi --log-file -
worker: celery -A ll_project worker --loglevel=INFO
beat: celery -A ll_project beat --loglevel=INFO
postdeploy: bash bin/post_deploy.sh
