"""Public web search and read-only page extraction for Andy."""
from dataclasses import dataclass,field
from datetime import datetime,timezone
from html.parser import HTMLParser
import ipaddress
import os
import re
import socket
from urllib.parse import urlparse
from urllib.request import Request,HTTPRedirectHandler,build_opener


def public_url(url,resolve=False):
    parsed=urlparse(url)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Use a public HTTP or HTTPS URL without login credentials.')
    if parsed.port not in (None,80,443):raise ValueError('Use a standard web port.')
    host=parsed.hostname.lower()
    if host=='localhost' or host.endswith(('.localhost','.local','.internal')):
        raise ValueError('Private addresses are not web sources.')
    try:addresses=[ipaddress.ip_address(host)]
    except ValueError:
        addresses=[]
        if resolve:
            addresses=[ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host,parsed.port or 443,type=socket.SOCK_STREAM)]
    if any(not address.is_global for address in addresses):raise ValueError('Private addresses are not web sources.')
    if resolve and not addresses:raise ValueError('Could not resolve the website.')
    return url


class PublicRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        public_url(newurl,resolve=True)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


class PageText(HTMLParser):
    hidden_tags={'script','style','nav','footer','header','aside','noscript','svg'}
    def __init__(self):super().__init__(convert_charrefs=True);self.hidden=0;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in self.hidden_tags:self.hidden+=1
        if not self.hidden and tag in ('p','h1','h2','h3','li','br'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in self.hidden_tags:self.hidden=max(0,self.hidden-1)
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)


def read_page(url):
    public_url(url,resolve=True)
    opener=build_opener(PublicRedirect())
    request=Request(url,headers={'User-Agent':'Andy-Personal-Assistant/1.0'})
    with opener.open(request,timeout=10) as response:
        public_url(response.geturl(),resolve=True)
        kind=response.headers.get('Content-Type','').lower()
        if not any(t in kind for t in ('text/html','text/plain','application/xhtml')):
            raise ValueError('This reader supports public HTML and text pages.')
        data=response.read(1_000_001)
        if len(data)>1_000_000:raise ValueError('The page is too large.')
        text=data.decode(response.headers.get_content_charset() or 'utf-8',errors='replace')
    if 'html' in kind:
        parser=PageText();parser.feed(text);text=' '.join(parser.parts)
    text=' '.join(text.split())
    if len(text)<60:raise ValueError('No readable public article text was found.')
    return text[:3500]


@dataclass
class WebReply:
    answer:str|None=None
    evidence:list=field(default_factory=list)


class WebTools:
    def __init__(self):self.results=[];self.sources=[]

    def handle(self,text,explicit_only=False):
        text=text.strip()
        command=re.sub(r'^(?:(?:hey\s+)?andy[,.]?\s+|please\s+|(?:can|could|would) you\s+)+','',text,flags=re.I)
        read=re.fullmatch(r'(?:read|summarize|read out)(?: me)?(?: the)? (first|second|third|1|2|3)(?: search)? (?:result|page|source)[.!?]?',command,re.I)
        if read:
            index={'first':0,'second':1,'third':2,'1':0,'2':1,'3':2}[read[1].lower()]
            if index>=len(self.results):return WebReply('Search the web first, then ask me to read a result.')
            return self.page(self.results[index]['url'],self.results[index]['title'])
        url=re.fullmatch(r'(?:read|summarize)(?: the page at)?\s+(https?://\S+)',command,re.I)
        if url:return self.page(url[1].rstrip('.,!?'),'Requested web page')
        if command.lower().strip(' .!?') in ('search','search the web','search the internet','look up'):
            return WebReply('What would you like me to search for?')
        search=re.match(r'(?:search(?: the (?:web|internet))?(?: for)?|look up|find information (?:about|on)|check online (?:for|about))\s+(.+)',command,re.I)
        current=re.search(r'\b(latest|current|right now|as of today|stock price|exchange rate)\b|who is (?:the )?(?:president|prime minister|chief minister|ceo)',command,re.I)
        if explicit_only:current=None
        if not search and not current:return None
        query=(search[1] if search else command).strip()
        return self.search(query)

    def search(self,query):
        self.sources=[];self.results=[]
        try:
            from ddgs import DDGS
            client=DDGS(timeout=8,proxy=os.getenv('HTTPS_PROXY') or os.getenv('https_proxy'),
                        verify=os.getenv('SSL_CERT_FILE') or True)
            found=client.text(query[:350],region='in-en',safesearch='moderate',max_results=3,backend='duckduckgo,brave')
            for item in found:
                url=item.get('href','')
                try:public_url(url)
                except ValueError:continue
                title=' '.join(str(item.get('title','')).split())[:160]
                snippet=' '.join(str(item.get('body','')).split())[:400]
                if title and snippet:self.results.append({'title':title,'url':url,'text':snippet})
            self.sources=[(item['title'],item['url']) for item in self.results]
            if not self.results:return WebReply('I could not find usable web results. Please rephrase the search.')
            return WebReply(evidence=self.results.copy())
        except Exception:
            return WebReply('I could not complete the web search. Check your connection and that the search dependency is installed. Please try again.')

    def page(self,url,title):
        self.sources=[]
        try:
            text=read_page(url)
            self.sources=[(title,url)]
            return WebReply(evidence=[{'title':title,'url':url,'text':text}])
        except Exception:
            return WebReply('I could not read that public page. It may require a login, block automated access, or need JavaScript. Try a different source.')
