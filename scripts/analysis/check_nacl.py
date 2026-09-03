"""Check VPC NACLs for the hub's VPC."""
import subprocess, json

# Describe NACLs
result = subprocess.run([
    "aws", "ec2", "describe-network-acls", "--region", "us-east-1",
    "--filters", "Name=vpc-id,Values=vpc-0d823c7a55049ca7d",
    "--query", "NetworkAcls[].Entries[]",
    "--output", "json"
], capture_output=True, text=True)

nacls = json.loads(result.stdout)
print("NACL entries:")
for e in sorted(nacls, key=lambda x: x.get("RuleNumber", 999)):
    print(f"  Rule {e.get('RuleNumber'):>4}: {'ALLOW' if e.get('RuleAction')=='allow' else 'DENY':6s} "
          f"{e.get('Protocol',''):>4}  Port {e.get('PortRange',{}).get('From','all'):>5}-{e.get('PortRange',{}).get('To','all'):<5}  "
          f"{e.get('CidrBlock','')}  {'EGRESS' if e.get('Egress') else 'INGRESS'}")

# Also check subnet association
result2 = subprocess.run([
    "aws", "ec2", "describe-network-acls", "--region", "us-east-1",
    "--filters", "Name=vpc-id,Values=vpc-0d823c7a55049ca7d",
    "--query", "NetworkAcls[].Associations[].{Subnet:SubnetId,NetAcl:NetworkAclId}",
    "--output", "table"
], capture_output=True, text=True)
print(f"\nNACL associations:")
print(result2.stdout)
