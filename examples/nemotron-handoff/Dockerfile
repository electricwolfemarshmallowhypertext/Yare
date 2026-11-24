FROM python:3.12-slim
RUN mkdir -p /tmp/yare-task/nemotron-task && \
    chown -R 1000:1000 /tmp/yare-task
COPY workstate.py test_workstate.py /tmp/yare-task/nemotron-task/
RUN chown -R 1000:1000 /tmp/yare-task
WORKDIR /tmp/yare-task/nemotron-task
