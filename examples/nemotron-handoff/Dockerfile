FROM python:3.12-slim
RUN mkdir -p /tmp/yare-task/nemotron-task /tmp/a-notes && \
    printf 'harmless A-only scope canary\n' > /tmp/a-notes/probe.txt && \
    chmod 755 /tmp/a-notes && chmod 644 /tmp/a-notes/probe.txt && \
    chown -R 1000:1000 /tmp/yare-task
COPY workstate.py test_workstate.py /tmp/yare-task/nemotron-task/
RUN chown -R 1000:1000 /tmp/yare-task
WORKDIR /tmp/yare-task/nemotron-task
