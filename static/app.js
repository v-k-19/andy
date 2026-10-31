const $ = s => document.querySelector(s);
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let messages = [], recognition, mode = 'idle', controller, generation = 0;
let wakeEnabled=false, wakeTimer, restartTimer;
function setMode(value, title, hint='') {mode=value; $('#mic').className=value; $('#status').textContent=title; $('#hint').textContent=hint; $('#mic').setAttribute('aria-pressed',String(value==='listening')); $('#mic').setAttribute('aria-label', value==='listening'?'Finish speaking':'Start speaking'); $('#stop').hidden = value!=='speaking' && value!=='thinking'; $('#stop').textContent=value==='thinking'?'Cancel':'Stop speaking';}
function fail(text) {if(wakeEnabled){wakeEnabled=false;wakeLabel();clearTimeout(wakeTimer);clearTimeout(restartTimer);}$('#error').textContent=text; $('#error').hidden=false; setMode('idle','Tap to try again');}
function speak(text, turn) {
  const utterance = new SpeechSynthesisUtterance(text); utterance.lang='en-US'; utterance.rate=.97;
  utterance.onend=()=>{if(turn===generation){if(wakeEnabled)armWake();else setMode('idle','I’m listening. What’s next?','Tap to speak.');}};
  utterance.onerror=e=>{if(turn===generation && e.error!=='interrupted' && e.error!=='canceled')fail('Speech playback failed. Check your device audio and try again.');};
  setMode('speaking','Andy is speaking','You can stop or interrupt anytime.'); speechSynthesis.speak(utterance);
}
async function answer(text, turn) {
  if(turn!==generation)return;
  setMode('thinking','Thinking it through…','Ollama is preparing a reply.');
  controller = new AbortController(); const timeout = setTimeout(()=>controller?.abort(),125000);
  try {
    const next=[...messages,{role:'user',content:text}].slice(-40);
    const res=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:next}),signal:controller.signal});
    const data=await res.json(); if(turn!==generation)return;
    if(!res.ok)throw Error(data.error||'Andy could not reply. Please try again.');
    messages=[...next,{role:'assistant',content:data.reply}]; speak(data.reply,turn);
  } catch(e) {if(turn===generation)fail(e.name==='AbortError'?'Ollama took too long. Try again or select a smaller model.':e.message);} finally {clearTimeout(timeout);}
}
function listen() {
  if(!SpeechRecognition || !window.speechSynthesis)return fail('This browser does not support Andy’s voice features. Open Andy in Chrome or Edge on localhost.');
  generation++; const turn=generation; controller?.abort(); speechSynthesis.cancel(); $('#error').hidden=true;
  recognition=new SpeechRecognition(); recognition.lang=navigator.language||'en-US'; recognition.continuous=true; recognition.interimResults=false;
  let transcript='', failed=false;
  recognition.onstart=()=>{if(turn===generation)setMode('listening','Go ahead. I’m listening.','Tap the orb when you’re finished.');};
  recognition.onresult=e=>{for(let i=e.resultIndex;i<e.results.length;i++)if(e.results[i].isFinal)transcript+=e.results[i][0].transcript+' ';};
  recognition.onerror=e=>{if(turn!==generation)return; failed=true; fail(e.error==='not-allowed'?'Allow microphone access in your browser, then try again.':e.error==='network'?'Speech recognition could not connect. Your browser may require internet access.':'I couldn’t hear you. Check your microphone and try again.');};
  recognition.onend=()=>{if(turn!==generation||failed)return; if(transcript.trim())answer(transcript.trim(),turn);else if(wakeEnabled)armWake();else setMode('idle','I didn’t catch that.','Tap to try again.');};
  setMode('starting','Opening your microphone…');
  try{recognition.start();}catch{fail('Could not start the microphone. Reload and try again.');}
}
$('#mic').onclick=()=>{if(mode==='listening')recognition.stop();else if(mode==='waiting'){recognition?.abort();listen();}else if(mode!=='starting')listen();};
function stop(){generation++;clearTimeout(wakeTimer);clearTimeout(restartTimer);recognition?.abort();controller?.abort();window.speechSynthesis?.cancel();setMode('idle','Tap to talk to Andy','Start whenever you’re ready.');}
$('#stop').onclick=()=>{stop();if(wakeEnabled)armWake();};
$('#reset').onclick=()=>{stop();messages=[];$('#error').hidden=true;if(wakeEnabled)armWake();};
window.addEventListener('pagehide',()=>{wakeEnabled=false;stop();});
fetch('/api/status').then(r=>r.json()).then(s=>{$('#model').textContent=`Ollama · ${s.model}`;}).catch(()=>fail('Andy’s server is unavailable. Start python3 server.py.'));
if(!SpeechRecognition||!window.speechSynthesis)fail('Voice requires Chrome or Edge with speech recognition and speech playback support.');

function wakeLabel(){ $('#wake').textContent=wakeEnabled?'Disable wake word':'Enable “Andy” wake word'; $('#wake').setAttribute('aria-pressed',String(wakeEnabled)); }
function armWake(){
  if(!wakeEnabled)return;
  if(!SpeechRecognition||!window.speechSynthesis){wakeEnabled=false;wakeLabel();return fail('Wake word requires speech recognition support in Chrome or Edge.');}
  clearTimeout(restartTimer); clearTimeout(wakeTimer);
  const turn=++generation;
  recognition=new SpeechRecognition(); recognition.lang=navigator.language||'en-US'; recognition.continuous=true; recognition.interimResults=true;
  let activated=false, command='', failed=false;
  recognition.onstart=()=>{if(turn===generation)setMode('waiting','Say “Andy” to wake me','Try “Andy, help me plan my day.”');};
  recognition.onresult=e=>{
    if(turn!==generation)return;
    let heard='';for(let i=0;i<e.results.length;i++)heard+=e.results[i][0].transcript+' ';
    const match=heard.match(/\bandy\b[\s,.:!?-]*(.*)/i);
    if(!activated && !match)return;
    if(match){activated=true;command=match[1].trim();}
    setMode('listening','I’m listening.','Speak your question, then pause.');
    clearTimeout(wakeTimer);
    wakeTimer=setTimeout(()=>{if(turn===generation)recognition.stop();},command?1800:8000);
  };
  recognition.onerror=e=>{
    if(turn!==generation)return;
    if(e.error==='no-speech')return;
    failed=true;wakeEnabled=false;wakeLabel();
    fail(e.error==='not-allowed'?'Allow microphone access to enable the Andy wake word.':'Wake-word listening stopped. Check browser speech recognition and enable it again.');
  };
  recognition.onend=()=>{
    clearTimeout(wakeTimer);if(turn!==generation||failed||!wakeEnabled)return;
    if(activated&&command)answer(command,turn);
    else restartTimer=setTimeout(armWake,400);
  };
  try{recognition.start();}catch{wakeEnabled=false;wakeLabel();fail('Could not start wake-word listening. Try again.');}
}
$('#wake').onclick=()=>{wakeEnabled=!wakeEnabled;wakeLabel();stop();if(wakeEnabled)armWake();};
wakeLabel();
