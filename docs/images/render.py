"""Render a static evidence figure from the executed local-model summaries."""
import hashlib
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
paths = [ROOT / 'docs/evidence/live-reference/summary.json', ROOT / 'docs/evidence/live-candidate/summary.json', ROOT / 'docs/evidence/comparison/gate.json']
a, b, gate = [json.loads(p.read_text(encoding='utf-8')) for p in paths]
assert a['mode'] == b['mode'] == 'live'

def total(result, key):
    return sum(row[key] for row in result['results'])

parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="560" viewBox="0 0 1000 560" role="img" aria-labelledby="title desc">', '<title id="title">Executed local model evaluation and release gate</title>', '<desc id="desc">Two prompt versions evaluated with actual local inference. Task success and unsafe recommendations are separate. Both versions are blocked.</desc>', '<rect width="1000" height="560" fill="#f8fafc"/>', '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#172b43}.small{font-size:17px}.label{font-size:20px}.value{font-size:29px;font-weight:bold}</style>']

def text(x, y, value, cls='label'):
    parts.append(f'<text x="{x}" y="{y}" class="{cls}">{escape(str(value))}</text>')

text(36, 42, 'LOCAL MODEL EVALUATION / RELEASE EVIDENCE', 'small')
text(36, 84, 'More successful tasks do not erase unsafe recommendations.', 'value')
text(36, 116, 'Qwen2.5-1.5B-Instruct · six synthetic scenario classes · two seeds each', 'small')
for i, (artifact, label) in enumerate([(a,'Reference prompt'), (b,'Summary-first candidate')]):
    x = 36 + i*480
    parts.append(f'<rect x="{x}" y="145" width="448" height="273" rx="8" fill="#ffffff" stroke="#cbd5e1"/>')
    text(x+22, 180, label)
    text(x+22, 218, f"{artifact['task_successes']} / {artifact['runs']} successful tasks", 'value')
    parts.append(f'<rect x="{x+22}" y="235" width="398" height="14" rx="4" fill="#e2e8f0"/>')
    parts.append(f'<rect x="{x+22}" y="235" width="{398*artifact["task_successes"]/artifact["runs"]:.2f}" height="14" rx="4" fill="#2563eb"/>')
    text(x+22, 288, f"{total(artifact,'unsafe_recommendations')} unsafe recommendations", 'label')
    text(x+22, 322, f"{artifact['unauthorized_effects']} unauthorized · {artifact['duplicate_effects']} duplicate effects", 'small')
    # The candidate decision comes from the saved gate; evaluate reference with the same implementation.
    import sys
    sys.path.insert(0, str(ROOT / 'src'))
    from gtm_agent.releases import compare
    decision = compare(artifact, artifact)['decision'] if i == 0 else gate['decision']
    text(x+22, 379, f"RELEASE: {decision.upper()}", 'value')
text(36, 454, 'Critical failures and unsafe recommendations block promotion.', 'label')
text(36, 486, 'Guards preventing a bad effect do not make an incorrect model decision successful.', 'small')
text(36, 517, 'Actual local inference; small synthetic suite, not production readiness or a population success rate.', 'small')
parts.append('<metadata>'+escape(json.dumps({p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, sort_keys=True))+'</metadata>')
parts.append('</svg>')
Path(__file__).with_name('live-evaluation.svg').write_text('\n'.join(parts)+'\n',encoding='utf-8')
print('Rendered actual live evaluation evidence.')
