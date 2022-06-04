import datetime
import json
import os

from flask import Flask, url_for, request, redirect
from flask_sqlalchemy import SQLAlchemy
from configparser import ConfigParser
from requests import Session

from homethermostatetl.ecobee import EcobeeParser

config = ConfigParser()
if os.path.isfile("./config.ini"):
    config.read("./config.ini")
else:
    config.read("./default.ini")

webapp = Flask(__name__)
webapp.config.update({
    "app_key": os.getenv("ECOBEE_APP_KEY", default=config.get("ecobee", "app_key" )),
    "app_url": os.getenv("ECOBEE_APP_URL", default=config.get("ecobee", "app_url")),
    "app_cutoff": os.getenv("ECOBEE_APPCUTOFF", default=config.get("ecobee", "app_cutoff")),
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    "SQLALCHEMY_DATABASE_URI": os.getenv("ECOBEE_DB_URI", default=config.get("ecobee", "db_uri"))
})

sqla = SQLAlchemy(webapp)


class AuthModel(sqla.Model):
    __tablename__ = "auth_keys"
    id = sqla.Column(sqla.Integer, primary_key=True, autoincrement=True)
    token = sqla.Column(sqla.String(1024))
    refresh = sqla.Column(sqla.String(64))
    expires = sqla.Column(sqla.DateTime, default=datetime.datetime.now())


class EventModel(sqla.Model):
    __tablename__ = "event_data"
    id = sqla.Column(sqla.BigInteger, primary_key=True, autoincrement=True)
    thermostatIdentifier = sqla.Column(sqla.BigInteger, nullable=False)
    date = sqla.Column(sqla.DateTime, nullable=False)
    auxHeat1 = sqla.Column(sqla.Integer, nullable=False, default=0)
    auxHeat2 = sqla.Column(sqla.Integer, nullable=False, default=0)
    auxHeat3 = sqla.Column(sqla.Integer, nullable=False, default=0)
    compCool1 = sqla.Column(sqla.Integer, nullable=False, default=0)
    compCool2 = sqla.Column(sqla.Integer, nullable=False, default=0)
    compHeat1 = sqla.Column(sqla.Integer, nullable=False, default=0)
    compHeat2 = sqla.Column(sqla.Integer, nullable=False, default=0)
    dehumidifier = sqla.Column(sqla.Integer, nullable=False, default=0)
    dmOffset = sqla.Column(sqla.Float, nullable=False, default=0.0)
    economizer = sqla.Column(sqla.Integer, nullable=False, default=0)
    fan = sqla.Column(sqla.Integer, nullable=False, default=0)
    humidifier = sqla.Column(sqla.Integer, nullable=False, default=0)
    HVACmode = sqla.Column(sqla.String(32), nullable=True)
    outdoorHumidity = sqla.Column(sqla.Integer, nullable=False, default=0)
    outdoorTemp = sqla.Column(sqla.Float, nullable=False, default=0.0)
    sky = sqla.Column(sqla.Integer, nullable=False, default=0)
    ventilator = sqla.Column(sqla.Integer, nullable=False, default=0)
    wind = sqla.Column(sqla.Integer, nullable=False, default=0)
    zoneAveTemp = sqla.Column(sqla.Float, nullable=False, default=0.0)
    zoneCalendarEvent = sqla.Column(sqla.String(32), nullable=True)
    zoneClimate = sqla.Column(sqla.String(32), nullable=True)
    zoneCoolTemp = sqla.Column(sqla.Float, nullable=False, default=0.0)
    zoneHeatTemp = sqla.Column(sqla.Float, nullable=False, default=0.0)
    zoneHumidity = sqla.Column(sqla.Integer, nullable=False, default=0)
    zoneHumidityHigh = sqla.Column(sqla.Integer, nullable=False, default=0)
    zoneHumidityLow = sqla.Column(sqla.Integer, nullable=False, default=0)
    zoneHVACmode = sqla.Column(sqla.String(32), nullable=True, default=0)
    zoneOccupancy = sqla.Column(sqla.Integer, nullable=False, default=0)


class SensorModel(sqla.Model):
    __tablename__ = "sensor_data"
    id = sqla.Column(sqla.BigInteger, primary_key=True, autoincrement=True)
    date = sqla.Column(sqla.DateTime, nullable=False)
    sensorId = sqla.Column(sqla.String(32), nullable=True, default=0)
    sensorName = sqla.Column(sqla.String(32), nullable=True, default=0)
    sensorType = sqla.Column(sqla.String(32), nullable=True, default=0)
    sensorUsage = sqla.Column(sqla.String(32), nullable=True, default=0)
    thermostatIdentifier = sqla.Column(sqla.BigInteger, nullable=False)
    value = sqla.Column(sqla.Float, nullable=False, default=0.0)


def get_api_key():
    with webapp.app_context():
        apikey = AuthModel.query.first()
        if apikey is not None and apikey.expires <= datetime.datetime.now():
            ses = Session()
            resp = ses.get("https://api.ecobee.com/token", params={
                "grant_type": "refresh_token",
                "refresh_token": apikey.refresh,
                "client_id": webapp.config.get("app_key"),
                "ecobee_type": "jwt"
            })
            resp_data = resp.json()
            apikey.token = resp_data.get("access_token")
            apikey.refresh = resp_data.get("refresh_token")
            apikey.expires = datetime.datetime.now() + datetime.timedelta(seconds=resp_data.get("expires_in"))
            sqla.session.commit()
            apikey = AuthModel.query.first()
        apikey = apikey.token if apikey is not None else None

    return apikey


@webapp.route("/")
def index():
    if get_api_key() is not None:
        return "api key already provided"
    app_key = webapp.config.get("app_key", "")
    redirect_url = webapp.config.get("app_url", "")
    url = f"https://api.ecobee.com/authorize?response_type=code&scope=smartRead&state=ecobeeetl"
    url = f"{url}&client_id={app_key}&redirect_uri={redirect_url}"
    return f"<a href=\"{url}\"> click here to get dicks </a>"


@webapp.route("/login")
def login():
    app_key = webapp.config.get("app_key", "")
    redirect_url = webapp.config.get("app_url", "")
    code = request.args.get("code")
    url = f"https://api.ecobee.com/token"
    api = Session()
    auth = api.get(url, params={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_url,
        "client_id": app_key,
        "ecobee_type": "jwt"
    })

    if auth.status_code != 200 or AuthModel.query.first() is not None:
        return redirect(url_for("index"))

    auth_data = auth.json()
    sqla.session.add(AuthModel(
        token=auth_data.get("access_token"),
        refresh=auth_data.get("refresh_token"),
        expires=datetime.datetime.now() + datetime.timedelta(seconds=auth_data.get("expires_in"))
    ))
    sqla.session.commit()
    return redirect(url_for("index"))


@webapp.route("/importdata")
def import_data():
    pass
    ses = Session()
    ses.headers.update({
        "Authorization": f"Bearer {get_api_key()}",
        "Content-Type": "application/json;charset-UTF-8"
    })

    therm_props = {
        "selection": {"selectionType": "registered", "selectionMatch": "", "includeEquipmentStatus": True}
    }
    therm_resp = ses.get("https://api.ecobee.com/1/thermostatSummary", params={"json": json.dumps(therm_props)})
    thermostats = therm_resp.json().get("statusList")
    thermostats = [x.replace(":", "") for x in thermostats]

    cutoff_date = webapp.config.get("app_cutoff")
    start_date = EventModel.query.order_by(EventModel.date.desc()).first()
    start_date = start_date.date + datetime.timedelta(days=1) if start_date is not None else cutoff_date
    end_date = start_date + datetime.timedelta(days=31)
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    if end_date > yesterday:
        end_date = yesterday
    start_date = start_date.strftime("%Y-%m-%d")
    end_date = end_date.strftime("%Y-%m-%d")

    report_props = {
        "selection": {"selectionType": "thermostats", "selectionMatch": ",".join(thermostats)},
        "columns": "auxHeat1,auxHeat2,auxHeat3,compCool1,compCool2,compHeat1,compHeat2,dehumidifier,dmOffset,"
                   "economizer,fan,humidifier,hvacMode,outdoorHumidity,outdoorTemp,sky,ventilator,wind,zoneAveTemp,"
                   "zoneCalendarEvent,zoneClimate,zoneCoolTemp,zoneHeatTemp,zoneHumidity,zoneHumidityHigh,"
                   "zoneHumidityLow,zoneHvacMode,zoneOccupancy",
        "includeSensors": True,
        "startDate": start_date,
        "endDate": end_date
    }
    report_resp = ses.get("https://api.ecobee.com/1/runtimeReport", params={"body": json.dumps(report_props)})

    ecobee_data = EcobeeParser(report_resp.json())
    for event in ecobee_data.events:
        sqla.session.add(EventModel(**event))
    for sensor in ecobee_data.sensors:
        sqla.session.add(SensorModel(**sensor))
    sqla.session.commit()
    return str(thermostats)


@webapp.before_first_request
def app_init():
    redirect_url = webapp.config.get("app_url", "").rstrip("/")
    redirect_url = f"{redirect_url}{url_for('login')}"

    app_cutoff = webapp.config.get("app_cutoff")
    app_cutoff = datetime.datetime.strptime(app_cutoff, "%Y/%m/%d")

    webapp.config.update({
        "app_url": redirect_url,
        "app_cutoff": app_cutoff
    })
    sqla.create_all()


webapp.run(host=config.get("web", "host", fallback=os.getenv("WEB_HOST")),
           port=config.getint("web", "port", fallback=os.getenv("WEB_PORT")))
