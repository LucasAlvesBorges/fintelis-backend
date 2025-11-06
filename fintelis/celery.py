import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fintelis.settings')

app = Celery('fintelis')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    self.logger.info('Running debug task for request: %s', self.request)  # pragma: no cover
