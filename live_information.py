"""Live weather and attributed news headlines. No language-model guessing."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import json
import math
import os
import re
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import xml.etree.ElementTree as ET


WEATHER = {0:'clear skies',1:'mainly clear skies',2:'partly cloudy skies',3:'overcast skies',
           45:'fog',48:'freezing fog',51:'light drizzle',53:'drizzle',55:'heavy drizzle',
           56:'freezing drizzle',57:'freezing drizzle',61:'light rain',63:'rain',65:'heavy rain',
           66:'freezing rain',67:'freezing rain',71:'light snow',73:'snow',75:'heavy snow',
           77:'snow grains',80:'light rain showers',81:'rain showers',82:'heavy rain showers',
           85:'snow showers',86:'heavy snow showers',95:'thunderstorms',96:'thunderstorms with hail',99:'thunderstorms with hail'}


CAPABILITIES = ('I can answer questions, explain things, follow our recent conversation, tell '
                'the time and date, fetch Hyderabad weather and forecasts, and read recent '
                'news headlines. Weather, news, and the natural female voice need an internet '
                'connection. I cannot control your apps or browse arbitrary websites.')


def fetch(url, *, json_data=True):
    request = Request(url, headers={'User-Agent':'Andy-Personal-Assistant/1.0'})
    with urlopen(request, timeout=8) as response:
        data = response.read(2_000_001)
    if len(data)>2_000_000:
        raise ValueError('Unexpectedly large response')
    return json.loads(data) if json_data else data


def clean(text, limit=240):
    text=re.sub(r'<[^>]*>', '', html.unescape(text or ''))
    return ' '.join(''.join(c for c in text if c.isprintable() or c.isspace()).split())[:limit]


def number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('Missing weather measurement')
    return round(value)


class LiveInformation:
    def __init__(self):
        self.city=os.getenv('ANDY_WEATHER_CITY','Hyderabad, India')
        self.sources=[]
        self.last_error=None

    def answer(self,text):
        lower=text.lower().strip().replace('’', "'")
        self.last_error=None
        question=re.sub(r'[^a-z0-9\s]', '', lower)
        question=re.sub(r'^(?:hey )?andy\s+', '', question)
        question=' '.join(question.split())
        if question in {'what can you do','what can you do for me','what do you do',
                        'how can you help','how can you help me','what are your capabilities',
                        'what are your features','tell me what you can do','tell me about yourself'}:
            return CAPABILITIES
        # Restrict the common speech homophone to weather-request phrases.
        lower=re.sub(r"\b(?:what'?s|what is|how'?s|how is|current|today'?s|tomorrow'?s)\s+(?:the\s+)?whether\b", 'weather', lower)
        weather_words=re.search(r'\b(weather|temperature|forecast|rain|raining)\b',lower)
        conditions=re.search(r"\b(?:how (?:hot|cold) is it|(?:hot|cold) outside|need (?:an? )?umbrella)\b",lower)
        conceptual=re.search(r'\b(explain|define|causes|meaning)\b|^what (?:is|causes) (?:weather|rain)\??$|^why does it rain',lower)
        if (weather_words or conditions) and not conceptual:
            self.sources=[]
            query=text
            if 'weather' in lower and not re.search(r'\bweather\b',text,re.I):
                query=re.sub(r'\bwhether\b','weather',query,flags=re.I)
            return self.retrieve('weather',query)
        news_words=re.search(r"\b(news|headlines|latest updates|current events)\b|what'?s happening (?:in|around) (?:the )?world",lower)
        if news_words and not re.search(r'\b(explain|define|meaning)\b',lower):
            self.sources=[]
            return self.retrieve('news',lower)
        capabilities=re.search(r'\b(internet|online|external information|external tools|tools|web)\b',lower)
        asking=re.search(r'\b(can you|do you|are you able|have access|access to|what tools|your capabilities)\b',lower)
        if capabilities and asking:
            return CAPABILITIES
        return None

    def retrieve(self,kind,text):
        try:
            return self.weather(text) if kind=='weather' else self.news(text)
        except Exception as error:
            self.last_error='HTTP '+str(error.code) if isinstance(error,HTTPError) else type(error).__name__
            topic='live weather' if kind=='weather' else 'recent news'
            return f'I tried the online service but could not retrieve {topic} just now. The service or connection may be unavailable. Please try again later.'

    def weather(self,text):
        match=re.search(r'\b(?:in|for|at)\s+(.+)',text,re.I)
        city=self.city
        if not match:
            prefix=re.match(r'([A-Za-z][A-Za-z ,.-]{1,70}?)\s+(?:weather|forecast)\b',text)
            if prefix and not re.search(r'\b(what|is|the|tell|me|today|tomorrow|latest|current)\b',prefix[1],re.I):
                city=prefix[1].strip()
        if match:
            city=re.sub(r'\b(?:today|tomorrow|right now|now|please|tonight)\b.*','',match[1],flags=re.I).strip(' ,.!?')
            if not city:city=self.city
        if re.search(r'\b(yesterday|last week|next week|weekend)\b',text,re.I):
            return 'I can check current weather and tomorrow’s forecast. Which of those would you like?'
        geo_url='https://geocoding-api.open-meteo.com/v1/search?'+urlencode({'name':city,'count':1,'language':'en','format':'json'})
        places=fetch(geo_url).get('results',[])
        if not places:
            return 'I could not find that city. Please say its name and country.'
        place=places[0]
        name=clean(place['name'],80)
        label=name + (', '+clean(place['country'],60) if place.get('country') else '')
        url='https://api.open-meteo.com/v1/forecast?'+urlencode({
            'latitude':place['latitude'],'longitude':place['longitude'],
            'current':'temperature_2m,apparent_temperature,weather_code',
            'daily':'temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code',
            'timezone':'auto','forecast_days':2})
        data=fetch(url)
        self.city=city
        if re.search(r'\b(tomorrow|tonight|forecast)\b',text,re.I) or re.search(r'\b(rain|raining|umbrella)\b',text,re.I):
            if re.search(r'\btonight\b',text,re.I):
                return 'I have current conditions and a daily forecast, but not an hourly forecast for tonight. Try asking for tomorrow’s weather.'
            daily=data['daily']
            day=1 if re.search(r'\btomorrow\b',text,re.I) else 0
            local_date=(datetime.now(timezone.utc)+timedelta(seconds=int(data.get('utc_offset_seconds',0)),days=day)).date()
            if daily['time'][day]!=local_date.isoformat():
                return 'The forecast is out of date. Please try again later.'
            description=WEATHER.get(daily['weather_code'][day],'mixed conditions')
            when='Tomorrow' if day else 'Today'
            answer=f"{when} in {label}, the forecast is {description}, with a high of {number(daily['temperature_2m_max'][day])} and a low of {number(daily['temperature_2m_min'][day])} degrees Celsius. The maximum chance of precipitation is {number(daily['precipitation_probability_max'][day])} percent. Source: Open-Meteo."
        else:
            current=data['current']
            stamp=datetime.fromisoformat(current['time'])
            # Compare with the API's local timezone offset to reject stale readings.
            local_now=datetime.now(timezone.utc)+timedelta(seconds=int(data.get('utc_offset_seconds',0)))
            age=local_now.replace(tzinfo=None)-stamp.replace(tzinfo=None)
            if not timedelta(hours=-1)<=age<=timedelta(hours=3):
                return 'The weather service returned an old reading, so I cannot give you current conditions. Please try again later.'
            description=WEATHER.get(current['weather_code'],'mixed conditions')
            answer=f"In {label}, Open-Meteo reports {number(current['temperature_2m'])} degrees Celsius with {description}, feeling like {number(current['apparent_temperature'])} degrees. The reading is from {stamp.strftime('%I:%M %p').lstrip('0')} local time."
        self.sources=[('Open-Meteo weather data',url),('Open-Meteo attribution','https://open-meteo.com/')]
        return answer

    def news(self,text):
        query=re.sub(r'\b(?:andy|hey|please|tell|me|give|read|what|are|is|the|latest|recent|today|todays|some|news|headlines|updates|current|events|happening|going|around|about|on|in|for)\b', ' ',text.lower())
        query=' '.join(re.sub(r'[^a-z0-9 -]',' ',query).split())[:100]
        params={'hl':'en-IN','gl':'IN','ceid':'IN:en'}
        endpoint='https://news.google.com/rss'
        if query:
            endpoint+='/search';params['q']=query+' when:2d'
        url=endpoint+'?'+urlencode(params)
        root=ET.fromstring(fetch(url,json_data=False))
        now=datetime.now(timezone.utc)
        articles=[];seen=set()
        for item in root.findall('./channel/item'):
            try:date=parsedate_to_datetime(item.findtext('pubDate',''))
            except (ValueError,TypeError):continue
            if date.tzinfo is None:date=date.replace(tzinfo=timezone.utc)
            if not now-timedelta(hours=48)<=date<=now+timedelta(hours=1):continue
            title=clean(item.findtext('title',''))
            publisher=clean(item.findtext('source',''),70)
            link=item.findtext('link','').strip()
            if not title or title.lower() in seen or urlparse(link).scheme!='https':continue
            seen.add(title.lower())
            if publisher and title.endswith(' - '+publisher):title=title[:-(len(publisher)+3)]
            articles.append((date,title,publisher or 'the publisher',link))
        articles.sort(key=lambda a:a[0],reverse=True)
        articles=articles[:3]
        if not articles:return 'I could not find fresh headlines from the last two days for that topic.'
        self.sources=[(title,link) for _,title,_,link in articles]
        spoken=[f"From {publisher}: {title}." for _,title,publisher,_ in articles]
        return 'Here are recent headlines via Google News. '+' '.join(spoken)+' These are headlines, not full article summaries.'
