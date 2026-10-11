"""Restore selected local artifacts from the original graduation.zip.

Models and videos are deliberately ignored by Git. This script never extracts
the archived Git history, private payment image or knowledge-base documents.
"""
import argparse
from pathlib import Path, PurePosixPath
import shutil
import zipfile

REPO = Path(__file__).resolve().parent.parent


def selected_members(archive, kind):
    for entry in archive.infolist():
        path = PurePosixPath(entry.filename)
        if entry.is_dir() or path.is_absolute() or '..' in path.parts:
            continue
        if kind == 'models' and path.parts[:2] == ('graduation', 'model'):
            yield entry, REPO / 'model' / Path(*path.parts[2:])
        elif kind == 'videos' and path.parts[:2] == ('graduation', 'video'):
            yield entry, REPO / 'media/videos' / Path(*path.parts[2:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True, help='Path to the original graduation.zip')
    parser.add_argument('--kind', choices=('models', 'videos'), default='models')
    parser.add_argument('--extract', action='store_true', help='Extract; otherwise only show the plan')
    args = parser.parse_args()
    with zipfile.ZipFile(args.archive) as archive:
        entries = list(selected_members(archive, args.kind))
        if not entries:
            parser.error('This archive does not contain the selected graduation artifacts.')
        total = sum(entry.file_size for entry, _ in entries)
        for entry, target in entries:
            if not target.resolve().is_relative_to(REPO.resolve()):
                raise ValueError('Archive member resolves outside the repository.')
            print(f'{entry.file_size / 2**20:8.2f} MiB  {target.relative_to(REPO)}')
        print(f'Total: {total / 2**20:.2f} MiB. Files remain ignored by Git.')
        if not args.extract:
            print('Add --extract to restore these files.')
            return
        for entry, target in entries:
            if target.exists():
                print(f'Skipped existing file: {target.relative_to(REPO)}')
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as source, target.open('wb') as dest:
                shutil.copyfileobj(source, dest)
            print(f'Restored: {target.relative_to(REPO)}')


if __name__ == '__main__':
    main()
