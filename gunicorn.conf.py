import os


def positive_int_from_environment(name, default):
    try:
        value = int(os.getenv(name, default))
    except ValueError:
        return default
    return max(1, value)


workers = positive_int_from_environment('WEB_CONCURRENCY', 2)
worker_class = 'gthread'
threads = positive_int_from_environment('GUNICORN_THREADS', 4)
timeout = positive_int_from_environment('GUNICORN_TIMEOUT', 30)
graceful_timeout = timeout
keepalive = 5
