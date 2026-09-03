"""Test SSM send-command with simple quoting."""
import subprocess, shlex, json, os, time, shutil

aws = shutil.which("aws")
env = os.environ.copy()

# Send command - use simple parameters format
send_cmd = (
    'ssm send-command --region us-east-1 --instance-ids i-0e7b9eb30a01e2f1d '
    '--document-name AWS-RunShellScript '
    '--parameters commands="curl -s http://localhost:8080/status" '
    '--query Command.CommandId --output text'
)
parts = [aws] + shlex.split(send_cmd)
print(f"Running SSM send...")
result = subprocess.run(parts, capture_output=True, text=True, timeout=15, env=env)
print(f"RC: {result.returncode}")
print(f"STDOUT: {result.stdout.strip()[:100]}")
print(f"STDERR: {result.stderr[:200]}")

if result.returncode == 0:
    cmd_id = result.stdout.strip()
    print(f"\nCommand ID: {cmd_id}")
    time.sleep(3)
    
    # Get result
    get_cmd = (
        f'ssm get-command-invocation --region us-east-1 --command-id {cmd_id} '
        f'--instance-id i-0e7b9eb30a01e2f1d --query StandardOutputContent --output text'
    )
    parts2 = [aws] + shlex.split(get_cmd)
    result2 = subprocess.run(parts2, capture_output=True, text=True, timeout=15, env=env)
    print(f"\nGet RC: {result2.returncode}")
    print(f"Get STDOUT: {result2.stdout.strip()[:500]}")
    print(f"Get STDERR: {result2.stderr[:200]}")
    
    if result2.stdout.strip():
        try:
            data = json.loads(result2.stdout.strip())
            print(f"\nParsed: {json.dumps(data, indent=2)}")
        except:
            print("Couldn't parse as JSON")
