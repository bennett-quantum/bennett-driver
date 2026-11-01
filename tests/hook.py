import json, os, pathlib, shutil, subprocess, tempfile
root=pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root/'.tmp',prefix='hook-') as temp:
    d=pathlib.Path(temp);repo=d/'repo';repo.mkdir();(repo/'scripts').mkdir()
    def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.STDOUT).decode().strip()
    git('init','-q');git('config','user.name','Gate Test');git('config','user.email','test@example.invalid')
    shutil.copy(root/'scripts/pre-push',repo/'scripts/pre-push')
    (repo/'Cargo.toml').write_text('committed')
    (repo/'.gitignore').write_text('.tmp/\n')
    git('add','.');git('commit','-qm','fixture');sha=git('rev-parse','HEAD')
    (repo/'Cargo.toml').write_text('dirty')
    bin=d/'bin';bin.mkdir();stub=bin/'cargo'
    stub.write_text('''#!/usr/bin/python3
import json,os,pathlib,subprocess,sys
p=pathlib.Path(sys.argv[sys.argv.index('--manifest-path')+1]);assert p.read_text()=='committed'
assert '--offline' in sys.argv and 'test' in sys.argv
assert not subprocess.check_output(['git','-C',str(p.parent),'status','--porcelain']).strip()
assert subprocess.run(['git','-C',str(p.parent),'symbolic-ref','-q','HEAD'],stdout=subprocess.DEVNULL).returncode!=0
assert all(x not in os.environ for x in ('DISPLAY','WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS','BROWSER'))
pathlib.Path(os.environ['STUB_LOG']).write_text(str(p.parent))
''');stub.chmod(0o755)
    env=dict(os.environ,PATH=str(bin)+':'+os.environ['PATH'],STUB_LOG=str(d/'receipt'),DISPLAY='bad')
    p=subprocess.run(['bash',str(repo/'scripts/pre-push')],cwd=repo,env=env,
        input=f'refs/heads/main {sha} refs/heads/main {"0"*40}\n',text=True,capture_output=True)
    assert p.returncode==0,p.stdout+p.stderr
    wt=pathlib.Path((d/'receipt').read_text());assert wt!=repo and not wt.exists()
    assert (repo/'Cargo.toml').read_text()=='dirty'
