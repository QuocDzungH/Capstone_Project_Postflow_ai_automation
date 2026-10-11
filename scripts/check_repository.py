"""Check public repository files for broken local links and packaging mistakes."""
import ast
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent


def main():
    result = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                            cwd=ROOT, capture_output=True, check=True)
    paths = [ROOT / name for name in result.stdout.decode('utf-8').split('\0') if name]
    failures = []
    secret_patterns = [
        re.compile(r'sk-(?:ant-)?[A-Za-z0-9_-]{24,}'),
        re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}'),
        re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
        re.compile(r'postgres(?:ql)?://[^\s:/]+:[^\s@]{4,}@'),
    ]
    for path in paths:
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if path.stat().st_size > 25 * 2**20:
            failures.append(f'Large file in public set: {rel}')
        if path.name == '.env' or path.suffix.lower() in {'.pt', '.pth', '.safetensors', '.db', '.zip', '.rar', '.mp4', '.mov'}:
            failures.append(f'Local artifact in public set: {rel}')
        if path.suffix.lower() not in {'.py', '.md', '.json', '.js', '.html', '.h', '.ino', '.txt', '.yml', '.yaml'}:
            continue
        text = path.read_text(encoding='utf-8-sig')
        if any(pattern.search(text) for pattern in secret_patterns):
            failures.append(f'Possible credential in: {rel}')
        if path.suffix == '.py':
            try:
                ast.parse(text, filename=rel)
            except SyntaxError as error:
                failures.append(f'Python syntax: {rel}:{error.lineno}')
        if path.suffix == '.md':
            for raw in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)', text):
                target = raw.strip().split(' "', 1)[0].strip('<>')
                if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                    continue
                target = unquote(target.split('#', 1)[0])
                if target and not (path.parent / target).exists():
                    failures.append(f'Broken link in {rel}: {target}')
    print(f'Checked {len(paths)} public files.')
    if failures:
        print('\n'.join(failures))
        return 1
    print('Local links, Python syntax, file sizes and targeted credential checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
