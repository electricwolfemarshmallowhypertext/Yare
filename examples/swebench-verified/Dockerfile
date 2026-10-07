FROM python:3.10-slim

COPY . /opt/public-original/pytest/
RUN mkdir -p /tmp/yare-task && \
    cp -a /opt/public-original/pytest /tmp/yare-task/pytest && \
    SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PYTEST=7.2.0 \
      pip install --no-cache-dir -e /tmp/yare-task/pytest && \
    chown -R 1000:1000 /tmp/yare-task && \
    chmod -R a+rX /opt/public-original/pytest
WORKDIR /tmp/yare-task/pytest
