"""Test AWS CLI commands for dashboard."""
import subprocess, json, shutil, os

aws = shutil.which("aws")
env = os.environ.copy()

# Test EC2 describe
ec2_cmd = (
    'ec2 describe-instances --region us-east-1 '
    '--query "Reservations[].Instances[].[InstanceId,'
    'Tags[?Key==`Name`].Value|[0],PublicIpAddress,InstanceType,'
    'State.Name,LaunchTime]" --output json'
)

# Use a list to avoid shell interference
import shlex
parts = [aws] + shlex.split(ec2_cmd)
result = subprocess.run(parts, capture_output=True, text=True, timeout=15, env=env)
print("=== EC2 DESCRIBE ===")
print("RC:", result.returncode)
print("STDOUT:", result.stdout[:2000] if result.stdout else "(empty)")
print("STDERR:", result.stderr[:500] if result.stderr else "(empty)")

# Test SSM
ssm_cmd = (
    'ssm list-commands --region us-east-1 --max-results 10 '
    '--query "Commands[].[CommandId,Status,TargetCount,CompletedCount,'
    'RequestedDateTime]" --output json'
)
parts2 = [aws] + shlex.split(ssm_cmd)
result2 = subprocess.run(parts2, capture_output=True, text=True, timeout=15, env=env)
print("\n=== SSM COMMANDS ===")
print("RC:", result2.returncode)
print("STDOUT:", result2.stdout[:2000] if result2.stdout else "(empty)")
print("STDERR:", result2.stderr[:500] if result2.stderr else "(empty)")

# Test S3
s3_cmd = (
    's3 ls s3://grantwizard-scripts/overture_religion_results/ --region us-east-1 --recursive '
    '--query "Contents[].{Key:Key,Size:Size}" --output json'
)
parts3 = [aws] + shlex.split(s3_cmd)
result3 = subprocess.run(parts3, capture_output=True, text=True, timeout=15, env=env)
print("\n=== S3 OVERTURE ===")
print("RC:", result3.returncode)
print("STDOUT:", result3.stdout[:2000] if result3.stdout else "(empty)")
print("STDERR:", result3.stderr[:500] if result3.stderr else "(empty)")
