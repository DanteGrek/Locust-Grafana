FROM python:2.7.12

ADD requirements.txt /

RUN apt-get update && \
    pip install -r requirements.txt

ADD . /src/app

EXPOSE 5000

WORKDIR /src/app

ENTRYPOINT ["/src/app/start.sh"]
