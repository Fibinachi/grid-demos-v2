"""Check route tables for internet gateway."""
import subprocess, json

result = subprocess.run([
    "aws", "ec2", "describe-route-tables", "--region", "us-east-1",
    "--filters", "Name=vpc-id,Values=vpc-0d823c7a55049ca7d",
    "--query", 'RouteTables[].{Id:RouteTableId,Routes:Routes[?DestinationCidrBlock==`0.0.0.0/0`].{Dest:DestinationCidrBlock,Gw:GatewayId},Assoc:Associations[].SubnetId}',
    "--output", "json"
], capture_output=True, text=True)

data = json.loads(result.stdout)
for rt in data:
    print(f"Route table: {rt['Id']}")
    for r in rt.get('Routes', []):
        print(f"  -> {r['Dest']} via {r.get('Gw','direct')}")
    for a in rt.get('Assoc', []):
        s = a[0] if isinstance(a, list) else a
        print(f"  Subnet: {s}")
    print()
