from cerebralcortex.core.data_manager.raw.stream_handler import DataSet
from cerebralcortex.cerebralcortex import CerebralCortex
from cerebralcortex.core.datatypes.datastream import DataStream
from cerebralcortex.core.datatypes.datastream import DataPoint
import datetime
import traceback
from core.computefeature import ComputeFeatureBase


feature_class_name = 'PhoneDataYield'

class PhoneDataYield(ComputeFeatureBase):

    def get_filtered_data(self, data, admission_control=None):
        """
        Helper method to get filtered data after applying admission control
        :param data:
        :param admission_control:
        :return:
        """
        if admission_control is None:
            return data
        return [d for d in data if admission_control(d.sample)]

    def get_data_by_stream_name(self, stream_name, user_id, day, localtime=True):
        """
        method to get combined data from CerebralCortex as there can be multiple stream id for same stream
        :param stream_name: Name of the stream corresponding to the datastream
        :param user_id:
        :param day:
        :return: combined data if there are multiple stream id
        """

        stream_ids = self.CC.get_stream_id(user_id, stream_name)
        data = []
        for stream in stream_ids:
            if stream is not None:
                ds = self.CC.get_stream(stream['identifier'], user_id=user_id, day=day, localtime=localtime)
                if ds is not None:
                    if ds.data is not None:
                        data += ds.data
        if len(stream_ids)>1:
            data = sorted(data, key=lambda x: x.start_time)
        return data

    def get_end_time(self, p: DataPoint):
        """
        helper method to get the actual end time of a data point.
        :param p:
        :return:
        """
        if p.end_time:
            s = p.end_time
        else:
            s = p.start_time
        return s

    def get_data_yield(self, data, max_data_gap_threshold_seconds=60):
        """
        This method produces series of data points containing interval of data present or not. In the sample
        a 0 means data is not present in this interval, 1 means data is there. Also it returns another data points
        with total hour of data is present in the data stream for a the whole day.
        :param data: list of data points
        :param max_data_gap_threshold_seconds: maximum allowed gap in seconds between two consecutive data points
        :return:
        """
        if not data:
            return None, None

        start_time = datetime.datetime.combine(data[0].start_time.date(), datetime.time.min)
        start_time = start_time.replace(tzinfo = data[0].start_time.tzinfo)
        end_time = datetime.datetime.combine(data[0].start_time.date(), datetime.time.max)
        end_time = end_time.replace(tzinfo = data[0].start_time.tzinfo)
        L = len(data)
        last = start_time
        yield_data = []
        data_duration = datetime.timedelta()

        if (data[0].start_time - start_time).total_seconds() > max_data_gap_threshold_seconds:
            yield_data.append(DataPoint(start_time, data[0].start_time, data[0].offset, 0))
            last = self.get_end_time(data[0])

        i = 1
        s = None
        t = None
        while i < L:
            s = self.get_end_time(data[i - 1])
            t = self.get_end_time(data[i])

            while i < L and (t - s).total_seconds() <= max_data_gap_threshold_seconds:
                i += 1
                if i < L:
                    s = t
                    t = self.get_end_time(data[i])

            if i < len(data):
                yield_data.append(DataPoint(last, s, data[0].offset, 1))
                yield_data.append(DataPoint(s, t, data[0].offset, 0))
                data_duration += (s - last)
                last = data[i].start_time
                i += 1

        if t and (end_time - t).total_seconds() > max_data_gap_threshold_seconds:
            yield_data.append(DataPoint(last, t, data[0].offset, 1))
            yield_data.append(DataPoint(t, end_time, data[0].offset, 0))
            data_duration += (t - last)
        else:
            yield_data.append(DataPoint(last, end_time, data[0].offset, 1))
            data_duration += (end_time - last)

        total_duration_data = [DataPoint(start_time, end_time, data[0].offset, round(data_duration.total_seconds()/(60*60), 2) )]
        return yield_data, total_duration_data

    def process_stream_day_data(self, user_id, lightdata, input_lightstream, filenames):
        try:
            data1, data2 = self.get_data_yield(lightdata)
            if data1:
                self.store_stream(filepath=filenames[0],
                                  input_streams=[input_lightstream],
                                  user_id=user_id, data=data1, localtime=False)

            if data2:
                self.store_stream(filepath=filenames[1],
                                  input_streams=[input_lightstream],
                                  user_id=user_id, data=data2, localtime=False)

        except Exception as e:
            self.CC.logging.log("Exception:", str(e))
            self.CC.logging.log(str(traceback.format_exc()))

    def process_day_data(self, user_id, all_days):
        streams = self.CC.get_user_streams(user_id)
        if not streams or not len(streams):
            self.CC.logging.log('No streams found for user %s for feature %s'
                                % (str(user_id), self.__class__.__name__))
            return

        input_lightstream = None
        input_batterystream = None
        input_pressurestream = None
        input_gyroscopestream = None
        input_accelerometerstream = None

        light_stream_name = 'AMBIENT_LIGHT--org.md2k.phonesensor--PHONE'
        battery_stream_name = 'BATTERY--org.md2k.phonesensor--PHONE'
        gyroscope_stream_name = 'GYROSCOPE--org.md2k.phonesensor--PHONE'
        pressure_stream_name = 'PRESSURE--org.md2k.phonesensor--PHONE'
        accelerometer_stream_name = 'ACCELEROMETER--org.md2k.phonesensor--PHONE'

        for stream_name, stream_metadata in streams.items():
            if stream_name == light_stream_name:
                input_lightstream = stream_metadata
            elif stream_name == battery_stream_name:
                input_batterystream = stream_metadata
            elif stream_name == pressure_stream_name:
                input_pressurestream = stream_metadata
            elif stream_name == gyroscope_stream_name:
                input_gyroscopestream = stream_metadata
            elif stream_name == accelerometer_stream_name:
                input_accelerometerstream = stream_metadata

        if not input_lightstream:
            self.CC.logging.log("No input stream found FEATURE %s STREAM %s "
                                "USERID %s" %
                                (self.__class__.__name__, light_stream_name,
                                 str(user_id)))
        else:
            for day in all_days:
                lightstream = self.get_data_by_stream_name(light_stream_name, user_id, day, localtime=False)
                lightstream = self.get_filtered_data(lightstream, lambda x: (type(x) is float and x>=0))
                self.process_stream_day_data(user_id, lightstream, input_lightstream, ["light_data_yield.json",
                                                                                       "light_data_yield_total.json"])

        if not input_batterystream:
            self.CC.logging.log("No input stream found FEATURE %s STREAM %s "
                                "USERID %s" %
                                (self.__class__.__name__, battery_stream_name,
                                 str(user_id)))
        else:
            for day in all_days:
                batterystream = self.get_data_by_stream_name(battery_stream_name, user_id, day, localtime=False)
                batterystream = self.get_filtered_data(batterystream, lambda x: (type(x) is list and len(x)==3))
                self.process_stream_day_data(user_id, batterystream, input_batterystream,
                                             ["phone_battery_data_yield.json", "phone_battery_data_yield_total.json"])

        if not input_pressurestream:
            self.CC.logging.log("No input stream found FEATURE %s STREAM %s "
                                "USERID %s" %
                                (self.__class__.__name__, battery_stream_name,
                                 str(user_id)))
        else:
            for day in all_days:
                pressurestream = self.get_data_by_stream_name(pressure_stream_name, user_id, day, localtime=False)
                pressurestream = self.get_filtered_data(pressurestream, lambda x: (type(x) is float))
                self.process_stream_day_data(user_id, pressurestream, input_pressurestream,
                                             ["pressure_data_yield.json", "pressure_data_yield_total.json"])

        if not input_gyroscopestream:
            self.CC.logging.log("No input stream found FEATURE %s STREAM %s "
                                "USERID %s" %
                                (self.__class__.__name__, gyroscope_stream_name,
                                 str(user_id)))
        else:
            for day in all_days:
                gyroscopestream = self.get_data_by_stream_name(gyroscope_stream_name, user_id, day, localtime=False)
                gyroscopestream = self.get_filtered_data(gyroscopestream, lambda x: (type(x) is list and len(x)==3))
                self.process_stream_day_data(user_id, gyroscopestream, input_gyroscopestream,
                                             ["phone_gyroscope_data_yield.json", "phone_gyroscope_data_yield_total.json"])

        if not input_accelerometerstream:
            self.CC.logging.log("No input stream found FEATURE %s STREAM %s "
                                "USERID %s" %
                                (self.__class__.__name__, accelerometer_stream_name,
                                 str(user_id)))
        else:
            for day in all_days:
                accelerometerstream = self.get_data_by_stream_name(accelerometer_stream_name, user_id,
                                                                   day, localtime=False)
                accelerometerstream = self.get_filtered_data(accelerometerstream,
                                                             lambda x: (type(x) is list and len(x)==3))
                self.process_stream_day_data(user_id, accelerometerstream, input_accelerometerstream,
                                             ["phone_accelerometer_data_yield.json", "phone_accelerometer_data_yield_total.json"])

    def process(self, user_id, all_days):
        if self.CC is not None:
            self.CC.logging.log("Processing Phone Data Yield")
            self.process_day_data(user_id, all_days)
