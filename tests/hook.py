"""Exercise the pinned-tool hook protocol without invoking Git or a gate."""
import json, os, pathlib, shutil, subprocess, tempfile

root=pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='hook-') as temp:
    d=pathlib.Path(temp); repo=d/'repo with spaces'; (repo/'scripts').mkdir(parents=True)
    shutil.copy(root/'scripts/pre-push',repo/'scripts/pre-push')
    # A dirty working-tree config must never choose the gate tool.
    (repo/'gate.toml').write_text('tool_sha = "dirty working tree"\n')
    pin='a'*40
    (d/'head-config').write_text(f'tool_sha = "{pin}"\n')
    tool_source=d/'tool.py'
    tool_source.write_text('''import json,os,pathlib,sys
assert all(x not in os.environ for x in ('GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','DISPLAY','WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS','BROWSER'))
pathlib.Path(os.environ['STUB_RECEIPT']).write_text(json.dumps(dict(argv=sys.argv[1:],stdin=sys.stdin.read())))
raise SystemExit(int(os.environ.get('STUB_EXIT','0')))
''')
    bin=d/'bin'; bin.mkdir()
    # This is a protocol double, not a call to a real repository or Git binary.
    (bin/'git').write_text('''#!/usr/bin/python3
import json,os,pathlib,sys
args=sys.argv[1:]; base=pathlib.Path(os.environ['STUB_ROOT']); d=base.parent
assert args[:1]==['-C'],args
with (d/'git-calls').open('a') as log: log.write(json.dumps(args)+'\\n')
command=args[2:]
if command==['rev-parse','--show-toplevel']: print(base)
elif command==['rev-parse','--path-format=absolute','--git-common-dir']: print(base/'.git')
elif command==['config','--path','--get','core.hooksPath']:
 if not os.environ.get('STUB_HOOKS_PATH'): raise SystemExit(1)
 print(os.environ['STUB_HOOKS_PATH'])
elif command==['show','HEAD:gate.toml']:
 if os.environ.get('STUB_MISSING_HEAD'): raise SystemExit(1)
 print((d/'head-config').read_text(),end='')
elif command==['show','a'*40+':tools/gate_run.py']:
 assert pathlib.Path(args[1])==d/'bennett'
 if os.environ.get('STUB_BAD_EXTRACT'):
  print('partial extract'); raise SystemExit(9)
 print((d/'tool.py').read_text(),end='')
else: raise AssertionError(args)
'''); (bin/'git').chmod(0o755)
    env=dict(os.environ,PATH=str(bin)+':'+os.environ['PATH'],STUB_ROOT=str(repo),
        STUB_RECEIPT=str(d/'receipt'),DISPLAY='bad',WAYLAND_DISPLAY='bad',
        DBUS_SESSION_BUS_ADDRESS='bad',BROWSER='bad',GIT_DIR='bad',GIT_WORK_TREE='bad',GIT_INDEX_FILE='bad')
    refs=f'refs/heads/main {"b"*40} refs/heads/main {"0"*40}\n'
    def invoke(**extra):
        return subprocess.run(['bash',str(repo/'scripts/pre-push'),'origin','ssh://example.invalid/repo'],
            cwd=repo,env=dict(env,**extra),input=refs,text=True,capture_output=True)
    p=invoke(BENNETT_GATE_HOOK_PROBE='1')
    assert p.returncode==0 and p.stdout==f'bennett-gate-hook-chained {repo}\n',p
    assert not (repo/'.tmp/gate/tool').exists() and not (d/'receipt').exists()
    p=invoke(); assert p.returncode==0,p.stdout+p.stderr
    receipt=json.loads((d/'receipt').read_text())
    assert receipt==dict(argv=['run','--repo',str(repo),'--tool-sha',pin,'origin','ssh://example.invalid/repo'],stdin=refs),receipt
    cached=repo/f'.tmp/gate/tool/gate_run-{pin}.py'
    assert cached.read_bytes()==tool_source.read_bytes()
    def extracts():
        return sum(json.loads(line)[2:]==['show',pin+':tools/gate_run.py'] for line in (d/'git-calls').read_text().splitlines())
    assert extracts()==1
    p=invoke(STUB_EXIT='17'); assert p.returncode==17 and extracts()==1
    cached.unlink()
    p=invoke(STUB_BAD_EXTRACT='1'); assert p.returncode and not cached.exists(),p
    p=invoke(); assert p.returncode==0 and cached.read_bytes()==tool_source.read_bytes(),p
    p=invoke(STUB_MISSING_HEAD='1'); assert p.returncode==3 and 'HEAD has no gate.toml' in p.stderr,p
    for invalid in ('short','g'*40,'a'*39):
        (d/'head-config').write_text(f'tool_sha = "{invalid}"\n')
        p=invoke(); assert p.returncode==3 and 'no full tool_sha' in p.stderr,p
    (d/'head-config').write_text(f'tool_sha = "{pin}"\n')
    shutil.copy(root/'scripts/install-hooks.sh',repo/'scripts/install-hooks.sh')
    for configured in ('','.beads/hooks',str(d/'custom hooks')):
        hooks=pathlib.Path(configured) if configured else repo/'.git/hooks'
        if not hooks.is_absolute(): hooks=repo/hooks
        install_env=dict(env,STUB_HOOKS_PATH=configured)
        p=subprocess.run(['bash',str(repo/'scripts/install-hooks.sh')],cwd=repo,env=install_env,text=True,capture_output=True)
        assert p.returncode==0,p.stdout+p.stderr
        effective=hooks/'pre-push'
        assert effective.is_symlink() and effective.resolve()==repo/'scripts/pre-push',effective
        p=subprocess.run([effective],cwd=repo,env=dict(install_env,BENNETT_GATE_HOOK_PROBE='1'),text=True,capture_output=True)
        assert p.returncode==0 and p.stdout==f'bennett-gate-hook-chained {repo}\n',p
    print('Pinned hook: probe, HEAD pin, extraction/cache, argv/stdin, scrubbed environment and failures verified')
