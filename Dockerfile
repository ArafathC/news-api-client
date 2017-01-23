FROM python:3.6-alpine
WORKDIR /opt

COPY requirements.txt /opt/requirements.txt

RUN pip install -r requirements.txt

