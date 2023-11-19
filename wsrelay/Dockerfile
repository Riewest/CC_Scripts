FROM python:3.11-alpine

RUN pip install websockets

ADD wsrelay.py wsrelay.py

EXPOSE 8765 

ENTRYPOINT ["python3", "wsrelay.py"]