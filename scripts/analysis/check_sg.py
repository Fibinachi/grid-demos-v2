"""Check and fix hub security group for port 8080 access."""
import subprocess, json

# Get current SG rules for port 8080
result = subprocess.run([
    "aws", "ec2", "describe-security-groups", "--region", "us-east-1",
    "--group-ids", "sg-0a6dca698b58814e0",
    "--query", 'SecurityGroups[].IpPermissions[?FromPort==`8080`||ToPort==`8080`]',
    "--output", "json"
], capture_output=True, text=True)

print("Current 8080 rules:")
print(result.stdout or result.stderr)

# Also describe the full SG
result2 = subprocess.run([
    "aws", "ec2", "describe-security-groups", "--region", "us-east-1",
    "--group-ids", "sg-0a6dca698b58814e0",
    "--query", 'SecurityGroups[0].IpPermissions[].{From:FromPort,To:ToPort,IpRanges:IpRanges[].CidrIp}',
    "--output", "table"
], capture_output=True, text=True)

print("\nAll SG rules:")
print(result2.stdout or result2.stderr)
