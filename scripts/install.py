#!/usr/bin/env python3
"""Copy selected public skills into a local agent's skill directory.

Standard library only. No package installs, network calls, models, account changes
or media processing. Existing differing installations are never overwritten.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ('producer', 'editor', 'video-enhance', 'podcast-audio-repair',
          'that-radio-voice', 'podcast-packager', 'short-form-clips', 'video-motion-graphics')
DEPENDENCIES = {'that-radio-voice': ('podcast-audio-repair',)}
AGENT_DIRS = {'codex': '.agents/skills', 'claude': '.claude/skills',
              'cursor': '.agents/skills', 'copilot': '.agents/skills',
              'antigravity': '.agents/skills'}
IGNORED = {'__pycache__', '.pytest_cache', '.venv', 'venv', '.DS_Store', 'Thumbs.db'}

def linked(path):
    return path.is_symlink() or bool(getattr(path, 'is_junction', lambda: False)())

def files(folder):
    result = {}
    for path in folder.rglob('*'):
        if any(part in IGNORED for part in path.relative_to(folder).parts) or path.suffix in ('.pyc', '.pyo'):
            continue
        if linked(path):
            raise ValueError('Skill bundles must contain real files, not links: ' + str(path))
        if path.is_file():
            result[path.relative_to(folder).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result

def selection(requested):
    selected = set(requested or SKILLS)
    if not selected <= set(SKILLS):
        raise ValueError('Unknown skill: ' + ', '.join(sorted(selected - set(SKILLS))))
    for name in tuple(selected):
        selected.update(DEPENDENCIES.get(name, ()))
    return [name for name in SKILLS if name in selected]

def destination(agent, project=None, user=False, skills_dir=None):
    if skills_dir is not None:
        return Path(skills_dir).expanduser().resolve()
    if user and agent == 'antigravity':
        raise ValueError('Antigravity personal paths vary by surface; use --skills-dir with its documented location.')
    base = Path.home() if user else Path(project).expanduser().resolve()
    return base / AGENT_DIRS[agent]

def install(target, requested=None, dry_run=False, source=None):
    source = Path(source or ROOT / 'skills').resolve()
    target = Path(target).expanduser().resolve()
    if target == source or target in source.parents or source in target.parents:
        raise ValueError('Install into the agent skill directory, not the source tree or its parent.')
    selected = selection(requested)
    plan = []
    for name in selected:
        src, dst = source / name, target / name
        if not (src / 'SKILL.md').is_file() or not (src / 'LICENSE').is_file():
            raise ValueError('Incomplete source skill: ' + name)
        header = (src / 'SKILL.md').read_text(encoding='utf-8')
        if not re.match(r'^---\s*\nname:\s*' + re.escape(name) + r'\s*\n', header):
            raise ValueError('Invalid source skill metadata: ' + name)
        expected = files(src)
        if linked(dst):
            raise ValueError('Existing skill is a link; review it manually: ' + str(dst))
        if dst.exists():
            if not dst.is_dir() or files(dst) != expected:
                raise ValueError('Existing skill differs; nothing was overwritten. Back it up and review before replacing: ' + str(dst))
            state = 'unchanged'
        else:
            state = 'install'
        plan.append({'name': name, 'source': str(src), 'destination': str(dst), 'action': state})
    if dry_run:
        return {'dry_run': True, 'skills_directory': str(target), 'skills': plan}
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ai-media-stage-', dir=target) as staging:
        staging = Path(staging)
        for item in plan:
            if item['action'] == 'install':
                shutil.copytree(item['source'], staging / item['name'],
                                ignore=shutil.ignore_patterns(*IGNORED, '*.pyc', '*.pyo'))
        for item in plan:
            if item['action'] == 'install':
                dst = Path(item['destination'])
                if dst.exists() or linked(dst):
                    raise ValueError('Destination changed during installation; review: ' + str(dst))
                shutil.move(str(staging / item['name']), str(dst))
                item['action'] = 'installed'
    return {'dry_run': False, 'skills_directory': str(target), 'skills': plan,
            'next': 'Skill files are installed. Ask your local agent to verify discovery and run Producer doctor. Restart its session if needed. Install only selected processing dependencies in an isolated environment.'}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--project', help='Install into this project directory.')
    scope.add_argument('--user', action='store_true', help='Install for your user account.')
    scope.add_argument('--skills-dir', help='Explicit parent skill directory for another agent or custom setup.')
    parser.add_argument('--agent', choices=AGENT_DIRS, default='codex')
    parser.add_argument('--skills', nargs='+', choices=SKILLS, help='Selected skills; default: the complete pack.')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = install(destination(args.agent, args.project, args.user, args.skills_dir), args.skills, args.dry_run)
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
