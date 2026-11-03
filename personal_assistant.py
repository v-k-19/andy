"""Local personal records and reminders. No model or cloud service is used."""
from datetime import datetime, timedelta
import json
import copy
import math
import os
from pathlib import Path
import re
import tempfile
import threading
import time

NUMBERS = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(),range(20)))
NUMBERS.update(dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(),range(20,100,10))))


def duration_seconds(text):
    words = text.lower().replace('-', ' ').split()
    total, quantity, consumed = 0., 0., False
    for word in words:
        if word in ('and',):
            continue
        if word in ('a','an'):
            quantity = quantity or 1
        elif word == 'half':
            quantity = .5
        elif word in NUMBERS:
            quantity += NUMBERS[word]
        elif re.fullmatch(r'\d+(?:\.\d+)?',word):
            quantity += float(word)
        elif word in ('second','seconds','minute','minutes','hour','hours'):
            if quantity <= 0:
                return None
            total += quantity * {'second':1,'minute':60,'hour':3600}[word.rstrip('s')]
            quantity, consumed = 0., True
        else:
            return None
    return total if consumed and quantity == 0 and 0 < total <= 366*86400 else None


class PersonalAssistant:
    def __init__(self, path=None):
        base = Path(os.getenv('XDG_DATA_HOME',str(Path.home()/'.local/share')))
        self.path = Path(path) if path else base/'andy'/'personal.json'
        self.lock = threading.RLock()
        self.state = {'notes':[], 'todos':[], 'alerts':[]}
        if self.path.exists():
            if self.path.stat().st_size > 2_000_000:
                raise RuntimeError('Andy’s personal data file is too large to load.')
            loaded = json.loads(self.path.read_text())
            if not isinstance(loaded,dict) or any(not isinstance(loaded.get(k),list) for k in self.state):
                raise RuntimeError('Andy’s personal data file is invalid. It has not been overwritten.')
            for kind in self.state:
                if len(loaded[kind]) > 1000:
                    raise RuntimeError('Andy’s personal list is too large.')
                seen = set()
                for entry in loaded[kind]:
                    valid = isinstance(entry,dict) and isinstance(entry.get('id'),int) and entry['id'] > 0 and entry['id'] not in seen and isinstance(entry.get('text'),str)
                    if valid and kind == 'alerts':
                        valid = entry.get('kind') in ('timer','reminder') and isinstance(entry.get('due'),(int,float)) and math.isfinite(entry['due']) and 0 <= entry['due'] <= 253402214400
                    if not valid:
                        raise RuntimeError('Andy’s personal data is invalid. It has not been overwritten.')
                    seen.add(entry['id'])
            self.state = loaded

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd, temporary = tempfile.mkstemp(dir=self.path.parent,prefix='.personal-',suffix='.json')
        try:
            with os.fdopen(fd,'w') as stream:
                json.dump(self.state,stream,ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary,self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def add(self, collection, **fields):
        if len(self.state[collection]) >= 1000:
            return 'That list is full. Delete an older entry first.'
        entry = {'id':max((x['id'] for x in self.state[collection]),default=0)+1, **fields}
        self.state[collection].append(entry)
        self.save()
        return entry

    def due(self, now=None):
        now = time.time() if now is None else now
        with self.lock:
            due = [entry for entry in self.state['alerts'] if not entry.get('delivered') and entry['due'] <= now]
            for entry in due:
                entry['delivered'] = True
            if due:
                try:
                    self.save()
                except OSError:
                    for entry in due:entry['delivered']=False
                    return []
            return [f"Your timer is finished." if entry['kind']=='timer' else 'Reminder: '+entry['text'] for entry in due]

    def handle(self, text, now=None):
        with self.lock:
            original = copy.deepcopy(self.state)
            try:
                return self._handle(text, now)
            except OSError:
                self.state = original
                return 'I could not save the change to your personal data. Check the data folder permissions.'

    def _handle(self, text, now=None):
        command = re.sub(r'^(?:(?:hey )?andy[, ]+|please |(?:can|could|would) you )+', '', text.strip(),flags=re.I).strip(' .!?')
        current = now or datetime.now().astimezone()
        lower = command.lower().replace('to-do', 'to do')
        with self.lock:
            if lower in ('read my notes','list my notes','what are my notes','show my notes'):
                entries=self.state['notes']
                return 'You have no saved notes.' if not entries else ' '.join(f"Note {x['id']}: {x['text']}." for x in entries[-10:])
            note = re.fullmatch(r'(?:remember that|take a note(?: that)?|make a note(?: that)?|note that)[: ]+(.+)',command,re.I)
            if note:
                entry=self.add('notes',text=note[1][:2000])
                return f"Saved note {entry['id']}." if isinstance(entry,dict) else entry
            if lower in ('read my to do list','read my todo list','list my tasks','what are my tasks','show my to do list'):
                entries=[x for x in self.state['todos'] if not x.get('done')]
                return 'Your to-do list is empty.' if not entries else ' '.join(f"Task {x['id']}: {x['text']}." for x in entries[:10])
            task = re.fullmatch(r'add (.+) to (?:my )?(?:to[ -]?do list|tasks)',command,re.I)
            if task:
                entry=self.add('todos',text=task[1][:2000],done=False)
                return f"Added task {entry['id']}: {entry['text']}." if isinstance(entry,dict) else entry
            change = re.fullmatch(r'(complete|delete) (task|note) (\d+)|mark task (\d+) (?:as )?done',command,re.I)
            if change:
                operation, kind, identifier = ('complete','task',int(change[4])) if change[4] else (change[1].lower(),change[2].lower(),int(change[3]))
                collection=self.state['todos' if kind=='task' else 'notes']
                entry=next((x for x in collection if x['id']==identifier),None)
                if entry is None:return f'I could not find {kind} {identifier}.'
                if operation=='complete' and kind=='note':return 'Notes cannot be completed. Say delete note and its number to remove one.'
                if operation=='delete':collection.remove(entry)
                else:entry['done']=True
                self.save()
                return f"{kind.capitalize()} {identifier} {'deleted' if operation=='delete' else 'completed'}."
            timer = re.fullmatch(r'(?:set|start) (?:a |an )?timer (?:for )?(.+)|(?:set|start) (?:a |an )?(.+?) timer',command,re.I)
            if timer:
                duration=duration_seconds(timer[1] or timer[2])
                if duration is None:return 'Say a duration, such as set a timer for five minutes.'
                entry=self.add('alerts',kind='timer',due=current.timestamp()+duration,text='',delivered=False)
                return f"Timer {entry['id']} set for {timer[1] or timer[2]}. Keep Andy running to hear it." if isinstance(entry,dict) else entry
            remind = re.fullmatch(r'remind me to (.+) in (.+)',command,re.I)
            if remind:
                duration=duration_seconds(remind[2])
                if duration is None:return 'Say a duration, such as remind me to drink water in twenty minutes.'
                entry=self.add('alerts',kind='reminder',due=current.timestamp()+duration,text=remind[1][:2000],delivered=False)
                return f"Reminder {entry['id']} set. Keep Andy running to receive it." if isinstance(entry,dict) else entry
            absolute = re.fullmatch(r'remind me to (.+) at (.+)',command,re.I)
            if absolute:
                clock=re.fullmatch(r'(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?(?: (today|tomorrow))?',absolute[2],re.I)
                if not clock:return 'Say a time with AM or PM, such as remind me to drink water at nine PM today. Use digits for the hour if recognition spells it incorrectly.'
                hour,minute=(int(clock[1]) if clock[1].isdigit() else NUMBERS[clock[1].lower()]),int(clock[2] or 0)
                period=(clock[3] or '').replace('.','').lower()
                if minute>59 or hour>23 or (period and not 1<=hour<=12) or (not period and hour<=12):
                    return 'Please specify a valid time with AM or PM.'
                if period:hour=hour%12+(12 if period=='pm' else 0)
                target=current.replace(hour=hour,minute=minute,second=0,microsecond=0)
                if clock[4] and clock[4].lower()=='tomorrow':target+=timedelta(days=1)
                elif target<=current:
                    if clock[4]:return 'That time has already passed today. Say tomorrow to schedule it for tomorrow.'
                    target+=timedelta(days=1)
                entry=self.add('alerts',kind='reminder',due=target.timestamp(),text=absolute[1][:2000],delivered=False)
                return f"Reminder {entry['id']} set for {target.strftime('%I:%M %p on %B %d')}, using your PC’s timezone. Keep Andy running." if isinstance(entry,dict) else entry
            if lower in ('list my timers','list my reminders','what are my reminders'):
                kind='timer' if 'timers' in lower else 'reminder'
                entries=[x for x in self.state['alerts'] if x['kind']==kind and not x.get('delivered')]
                return 'There are none pending.' if not entries else ' '.join(f"{kind.capitalize()} {x['id']}: {x['text'] or 'timer'}, due {datetime.fromtimestamp(x['due']).astimezone().strftime('%I:%M %p on %B %d')}." for x in entries[:10])
            cancel=re.fullmatch(r'cancel (timer|reminder) (\d+)',command,re.I)
            if cancel:
                entry=next((x for x in self.state['alerts'] if x['kind']==cancel[1].lower() and x['id']==int(cancel[2]) and not x.get('delivered')),None)
                if not entry:return 'I could not find that pending alert.'
                self.state['alerts'].remove(entry);self.save()
                return f'{cancel[1].capitalize()} {cancel[2]} cancelled.'
            if lower.startswith(('remind me','set a reminder','set an alarm')):
                return 'Try remind me to drink water in twenty minutes, or remind me to drink water at 9 PM today.'
            return None
