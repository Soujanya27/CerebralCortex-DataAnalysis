# Copyright (c) 2018, MD2K Center of Excellence
# - Alina Zaman <azaman@memphis.edu>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from cerebralcortex.core.data_manager.raw.stream_handler import DataSet
from cerebralcortex.cerebralcortex import CerebralCortex
from cerebralcortex.core.datatypes.datastream import DataStream
from cerebralcortex.core.datatypes.datastream import DataPoint
from datetime import datetime, timedelta
from core.computefeature import ComputeFeatureBase

import pprint as pp
import numpy as np
import pdb
import pickle
import uuid
import json
import traceback
import math

feature_class_name = 'StayingTimes'
Working_Days_STREAM = "org.md2k.data_analysis.feature.working_days"
MEDIAN_ABSOLUTE_DEVIATION_MULTIPLIER = 1.4826
OUTLIER_DETECTION_MULTIPLIER = 3

class StayingTimes(ComputeFeatureBase):
    """
    Produce feature from the days when a participant was in office from stream
    "org.md2k.data_analysis.feature.working_days". The time extent between arrival time
    and leaving time is taken as staying time. Usual staying time is calculated from these
    data. And here usual staying time is a range of time. each day's staying_time is marked
    as usual_staying_time or more_than_usual or less_than_usual """

    def listing_all_staying_times(self, user_id, all_days):
        """
        Produce and save the list of work_day's staying_time at office from
        "org.md2k.data_analysis.feature.working_days" stream and marked each day's
        staying_time as Usual_staying_time or More_than_usual or Less_than_usual. Staying time is
        saved in minute
        """

        self.CC.logging.log('%s started processing for user_id %s' %
                            (self.__class__.__name__, str(user_id)))

        stream_ids = self.CC.get_stream_id(user_id,
                                           Working_Days_STREAM)
        staying_time_data = []
        office_staying_times = list()
        for stream_id in stream_ids:
            for day in all_days:
                work_data_stream = \
                    self.CC.get_stream(stream_id["identifier"], user_id, day)

                for data in work_data_stream.data:
                    arrival_time = data.start_time.hour*60+data.start_time.minute
                    leave_time = data.end_time.hour*60 + data.end_time.minute
                    staying_time = leave_time - arrival_time
                    office_staying_times.append(staying_time)
                    sample = []
                    temp = DataPoint(data.start_time, data.end_time, data.offset, sample)
                    temp.sample.append(staying_time)
                    staying_time_data.append(temp)
        if not len(office_staying_times):
            return
        median = np.median(office_staying_times)
        mad_office_staying_times = []
        for staying_time in office_staying_times:
            # mad = median absolute deviation
            mad_office_staying_times.append(abs(staying_time - median))
        median2 = np.median(mad_office_staying_times)
        mad_value = median2 * MEDIAN_ABSOLUTE_DEVIATION_MULTIPLIER
        outlier_border = mad_value * OUTLIER_DETECTION_MULTIPLIER
        outlier_removed_office_staying_times = []
        for staying_time in office_staying_times:
            if staying_time > (median - outlier_border) and staying_time < (median + outlier_border):
                outlier_removed_office_staying_times.append(staying_time)
        if not len(outlier_removed_office_staying_times):
            outlier_removed_office_staying_times = office_staying_times
        mean = np.mean(outlier_removed_office_staying_times)
        standard_deviation = np.std(outlier_removed_office_staying_times)
        for data in staying_time_data:
            staying_time = data.sample[0]
            if staying_time > mean + standard_deviation:
                data.sample.append("more_than_usual")
                data.sample.append(math.ceil(staying_time-(mean+standard_deviation)))
            elif staying_time < mean-standard_deviation:
                data.sample.append("less_than_usual")
                data.sample.append(math.ceil(mean-standard_deviation-staying_time))
            else:
                data.sample.append("usual_staying_time")
                data.sample.append(0)
        #print(staying_time_data)
        try:
            if len(staying_time_data):
                streams = self.CC.get_user_streams(user_id)
                for stream_name, stream_metadata in streams.items():
                    if stream_name == Working_Days_STREAM:
                        # print(stream_metadata)
                        print("Going to pickle the file: ",staying_time_data)

                        self.store_stream(filepath="staying_time.json",
                                          input_streams=[stream_metadata],
                                          user_id=user_id,
                                          data=staying_time_data)
                        break
        except Exception as e:
            print("Exception:", str(e))
            print(traceback.format_exc())
        self.CC.logging.log('%s finished processing for user_id %s saved %d '
                            'data points' %
                            (self.__class__.__name__, str(user_id),
                             len(staying_time_data)))
    def process(self, user_id, all_days):
        if self.CC is not None:
            self.CC.logging.log("Processing Staying Times")
            self.listing_all_staying_times(user_id, all_days)