import datetime


class EcobeeParser:
    events: list = []
    sensors: list = []

    def __init__(self, data: dict = None, process_events: bool = True, process_sensors: bool = True):
        if data is not None:
            self.process(data, process_events, process_sensors)

    def process(self, data: dict, process_events: bool = True, process_sensors: bool = True):
        self.events = self._process_events(data) if process_events else self.events
        self.sensors = self._process_sensors(data) if process_sensors else self.sensors

    @staticmethod
    def _process_events(data: dict):
        d_fmt = "%Y-%m-%d %H:%M:%S"
        entries = []
        columns = ['date', 'time']
        columns.extend(data.get("columns", "").split(","))
        for thermostat in data.get("reportList", []):
            rows = thermostat.get("rowList")
            thermostat_id = thermostat.get("thermostatIdentifier")
            for row in rows:
                row = row.replace(",", "','")
                row = f"'{row}'"
                row = row.split(",")
                row = [x.strip("'") for x in row]
                row = [x if len(x) > 0 else None for x in row]
                row_data = {"thermostatIdentifier": thermostat_id}
                row_data.update(dict(zip(columns, row)))
                row_data.update({"date": datetime.datetime.strptime(
                    f"{row_data.get('date')} {row_data.get('time')}",
                    d_fmt)})
                del row_data['time']
                entries.append(row_data)
        return entries

    @staticmethod
    def _process_sensors(data: dict):
        d_fmt = "%Y-%m-%d %H:%M:%S"
        entries = []
        data = data.get("sensorList", [])
        for thermostat in data:
            thermostat_id = thermostat.get("thermostatIdentifier")
            columns = thermostat.get("columns")
            sensors = {x["sensorId"]: x for x in thermostat.get("sensors")}
            for row in thermostat.get("data"):
                row = row.replace(",", "','")
                row = f"'{row}'"
                row = row.split(",")
                row = [x.replace("'", "") for x in row]
                row = [x if len(x) > 0 else None for x in row]
                row = dict(zip(columns, row))
                row.update({"thermostatIdentifier": thermostat_id})
                row.update({"date": datetime.datetime.strptime(f"{row.get('date')} {row.get('time')}", d_fmt)})
                del row['time']
                sensor_rows = []
                for sensor, fields in sensors.items():
                    sensor_row: dict = fields.copy()
                    sensor_row.update({k: v for k, v in row.items() if k in ["thermostatIdentifier", "date", "time"]})
                    sensor_row.update({"value": row[sensor]})
                    sensor_rows.append(sensor_row)
                entries.extend(sensor_rows)
            return entries
