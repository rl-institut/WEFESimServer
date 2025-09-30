FROM python:3.8-slim

ARG SIMULATION_VERSION
ARG SIMULATION_PACKAGE

ENV CELERY_BROKER_URL redis://redis:6379/0
ENV CELERY_RESULT_BACKEND redis://redis:6379/0

RUN apt-get update && \
    apt-get install -y git && \
    apt-get install coinor-cbc -y && \
    apt-get install graphviz -y

COPY task_queue/requirements.txt /tmp/

RUN python -m pip install --upgrade pip
RUN pip install -r /tmp/requirements.txt
RUN echo SIMULATION_PACKAGE
RUN pip install "oemof-tabular-plugins $SIMULATION_VERSION" gunicorn

run echo $(pip freeze)
COPY task_queue/ /queue

# avoid running as root user
RUN useradd --create-home appuser
RUN chown -R appuser /queue
USER appuser

WORKDIR /queue

ENTRYPOINT celery -A tasks worker --loglevel=info --queues=$CELERY_TASK_NAME