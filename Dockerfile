FROM python:3.10-slim

ENV ECOBEE_APP_KEY theapikey
ENV ECOBEE_APP_URL theurl
ENV ECOBEE_APPCUTOFF dateofsomekind
ENV ECOBEE_DB_URI dburi
ENV WEB_HOST 0.0.0.0
ENV WEB_PORT 4567

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py .
COPY homethermostatetl ./homethemostatetl
COPY default.ini .

EXPOSE 4567/tcp

CMD ["python3", "main.py"]
