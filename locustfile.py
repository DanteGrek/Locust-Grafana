from requests.exceptions import ConnectionError

from locust import HttpLocust, TaskSet, task
from statsd import TCPStatsClient, StatsClient
import requests
import time
import json
import os

statsd = StatsClient(host=os.environ.get('STATSD_HOST', 'statsd'),
                     port=os.environ.get('STATSD_PORT', 8125), 
                     prefix=os.environ.get('STATSD_PREFIX', 'locust'))


def post_with_retries(session, url, payload, headers):
    backoff = 0
    retries = 10
    while retries > 0:
        try:
            response = session.post(url, data=json.dumps(payload), headers=headers)
            print response.text
            return response
            break
        except ConnectionError, e:
            print "Retrying in %s seconds" % 2**backoff
            time.sleep(2**backoff)
            backoff += 1 

        retries -= - 1
    
    if retries == 0:
        raise e
    

def init_influxdb_():
    influxdb_url = os.environ.get('INFLUXDB_HOST', 'influxdb:8083')

    session = requests.Session()

    http_status = [200, 400, 403, 404, 500, 503]

    prefix = os.environ.get('STATSD_PREFIX', 'locust')
    influxdb_user = os.environ.get('INFLUXDB_USER', 'root')
    influxdb_password = os.environ.get('INFLUXDB_PASSWORD', 'root')
    post_url = '%s/db/statsd/series?u=%s&p=%s' % (influxdb_url, influxdb_user, influxdb_password)

    for status in http_status:
        print "adding counter for %s" % status
        payload = [{
                    "name" : "%s.requests_%s.counter" % (prefix, status),
                    "columns" : ["value"],
                    "points" : [[0]]
                   }]
        post_with_retries(session, post_url, payload, {'Content-Type': 'application/json'})

def init_grafana_dashboard():
   grafana_url = os.environ.get('GRAFANA_URL', 'grafana:3000')

   grafana_user = os.environ.get('GRAFANA_USER', 'admin')
   grafana_password = os.environ.get('GRAFANA_PASSWORD', 'admin')

   payload = {"user":grafana_user,"email":"","password":grafana_password} 
   headers = {'Content-Type': 'application/json'}

   session = requests.Session()

   response = post_with_retries(session, "%s/login"% grafana_url , payload, headers)
   data = response.json()

   print data

   if 'logged in' == data['message'].lower():
       # Create data source
       payload = {"access": "direct", 
                   "database": "statsd",
                   "isDefault": True,
                   "name": "statsd",
                   "password": "root",
                   "type": "influxdb_08",
                   "url": os.environ.get('INFLUXDB_HOST', "influxdb:8083"),
                   "user": "root"
                 } 

       response = session.put("%s/api/datasources" % grafana_url, data=json.dumps(payload), headers=headers)
       print response.json()

       dashboard_json = open('dashboard.json').read()
       response = session.post('%s/api/dashboards/db/' % grafana_url, data=dashboard_json, headers=headers)
       print response.json()

init_influxdb_()
init_grafana_dashboard()


class UserBehavior(TaskSet):
    min_wait = 100
    max_wait = 5000

    def on_start(self):
        self.index()

    def index(self):
        self.client.get("/")
        statsd.incr('index')

    @task(10)
    def packages(self):
        with statsd.timer('request_time'):
            response = self.client.get("/packages")
            statsd.incr('requests_%s' % response.status_code)
        statsd.incr('requests')

    @task(10)
    def download(self):
        with statsd.timer('request_time'):
            response = self.client.get("/download")
            statsd.incr('requests_%s' % response.status_code)
        statsd.incr('requests')

    # @task(1)
    # def stop(self):
    #     self.interrupt()


class WebsiteUser(HttpLocust):
    host = "http://archlinux.org"
    task_set = UserBehavior
    min_wait = 500
    max_wait = 1000
