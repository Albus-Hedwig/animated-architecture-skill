#!/usr/bin/env python3
"""Install the repository's skill; preserve an existing local copy as a backup."""
import argparse
import os
import shutil
from datetime import datetime
from pathlib import Path


def install(destination):
    source=Path(__file__).resolve().parent.parent/'skills/animate-architecture'
    destination=destination.expanduser().resolve(); destination.parent.mkdir(parents=True,exist_ok=True)
    backup=None
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink():
            raise ValueError('Destination is a symlink; choose a real skill directory instead')
        if not (destination/'SKILL.md').is_file():
            raise ValueError('Existing destination is not a skill; choose another directory')
        backup_root=destination.parent.parent/'skill-backups'
        backup_root.mkdir(parents=True,exist_ok=True)
        backup=backup_root/(destination.name+'-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        shutil.copytree(destination,backup)
    temporary=destination.parent/('.'+destination.name+'-install-'+datetime.now().strftime('%Y%m%d%H%M%S%f'))
    shutil.copytree(source,temporary,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.DS_Store'))
    try:
        if destination.exists():
            shutil.rmtree(destination)
        temporary.rename(destination)
    except Exception:
        if backup and not destination.exists():
            shutil.copytree(backup,destination)
        raise
    print('Installed '+str(destination))
    if backup:
        print('Previous version saved at '+str(backup))


if __name__=='__main__':
    default=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills/animate-architecture'
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',type=Path,default=default)
    args=parser.parse_args()
    install(args.destination)
