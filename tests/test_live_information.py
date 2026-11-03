from datetime import datetime,timedelta,timezone
from email.utils import format_datetime
import io
import json
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs,urlparse
import desktop
from live_information import LiveInformation


def weather_data():
    now=datetime.now(timezone.utc)+timedelta(seconds=19800)
    return {'utc_offset_seconds':19800,'current':{'temperature_2m':29.5,'apparent_temperature':31,'weather_code':2,'time':now.replace(tzinfo=None).isoformat(timespec='minutes')},'daily':{'time':[now.date().isoformat(),(now+timedelta(days=1)).date().isoformat()],'temperature_2m_max':[32,33],'temperature_2m_min':[23,24],'weather_code':[2,61],'precipitation_probability_max':[10,60]}}


class LiveTests(unittest.TestCase):
    def test_hyderabad_default_and_metric_reading_are_from_api(self):
        info=LiveInformation()
        geo={'results':[{'name':'Hyderabad','country':'India','latitude':17.38,'longitude':78.48}]}
        with patch('live_information.fetch',side_effect=[geo,weather_data()]) as fetch:
            answer=info.answer('What is the weather like today?')
        self.assertIn('Hyderabad, India',answer)
        self.assertIn('30 degrees Celsius',answer)
        self.assertIn('Open-Meteo',answer)
        self.assertEqual(parse_qs(urlparse(fetch.call_args_list[0].args[0]).query)['name'],['Hyderabad, India'])
        self.assertTrue(info.sources)

    def test_city_and_tomorrow_forecast(self):
        geo={'results':[{'name':'London','country':'United Kingdom','latitude':51.5,'longitude':-.12}]}
        with patch('live_information.fetch',side_effect=[geo,weather_data()]) as fetch:
            answer=LiveInformation().answer('Will it rain in London tomorrow?')
        self.assertIn('Tomorrow in London',answer)
        self.assertIn('60 percent',answer)
        self.assertEqual(parse_qs(urlparse(fetch.call_args_list[0].args[0]).query)['name'],['London'])

    def test_failed_live_query_does_not_use_model(self):
        with patch('live_information.fetch',side_effect=OSError('offline')),patch.object(desktop,'build_opener') as model:
            answer,_=desktop.ask_ollama([], 'What is the weather?')
            model.assert_not_called()
        self.assertIn('could not retrieve',answer)

    def test_stale_weather_is_not_reported_as_current(self):
        data=weather_data();data['current']['time']='2020-01-01T10:00'
        with patch('live_information.fetch',side_effect=[{'results':[{'name':'Hyderabad','latitude':17,'longitude':78}]},data]):
            answer=LiveInformation().answer('weather')
        self.assertIn('old reading',answer)

    def test_conceptual_questions_use_general_model(self):
        info=LiveInformation()
        with patch('live_information.fetch') as network:
            for text in ['Explain weather patterns','What causes rain?','Explain the meaning of news']:
                self.assertIsNone(info.answer(text))
            network.assert_not_called()

    def test_news_attributes_publishers_and_excludes_stale_items(self):
        recent=format_datetime(datetime.now(timezone.utc)-timedelta(hours=1))
        stale=format_datetime(datetime.now(timezone.utc)-timedelta(days=10))
        xml=f'''<rss><channel><item><title>A recent headline - Example News</title><pubDate>{recent}</pubDate><source>Example News</source><link>https://example.com/story</link></item><item><title>Old headline</title><pubDate>{stale}</pubDate><link>https://example.com/old</link></item></channel></rss>'''.encode()
        info=LiveInformation()
        with patch('live_information.fetch',return_value=xml):answer=info.answer('latest technology news')
        self.assertIn('From Example News',answer)
        self.assertNotIn('Old headline',answer)
        self.assertEqual(info.sources,[('A recent headline','https://example.com/story')])

    def test_missing_measurement_does_not_become_zero(self):
        data=weather_data();data['current']['temperature_2m']=None
        with patch('live_information.fetch',side_effect=[{'results':[{'name':'Hyderabad','latitude':17,'longitude':78}]},data]):
            answer=LiveInformation().answer('weather')
        self.assertIn('could not retrieve',answer)


if __name__=='__main__':unittest.main()
