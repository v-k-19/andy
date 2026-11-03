"""Check Andy's live services directly, without the microphone or Ollama."""
from pathlib import Path
import subprocess
from live_information import LiveInformation


def main():
    root=Path(__file__).resolve().parent
    print('Andy project:',root)
    try:
        version=subprocess.run(['git','rev-parse','--short','HEAD'],cwd=root,capture_output=True,text=True,timeout=5,check=True).stdout.strip()
        print('Git version:',version)
    except (OSError,subprocess.SubprocessError):
        print('Git version: unavailable')
    for label,question in [('Weather','What is the weather?'),('News','Read the latest news')]:
        info=LiveInformation()
        answer=info.answer(question)
        usable=bool(info.sources) and not info.last_error
        print(f'\n{label}: '+('OK' if usable else 'FAILED'))
        if info.last_error:print('Error type:',info.last_error)
        print(answer)
    print('\nThis checks providers directly. A successful result means neither Ollama nor voice recognition is needed for these answers.')


if __name__=='__main__':main()
