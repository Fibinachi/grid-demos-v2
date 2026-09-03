import subprocess, os

KEY = os.path.expanduser("~/.ssh/grantwizard-key.pem")

def ssh(ip, cmd, timeout=10):
    full = ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=5',
            '-i', KEY, f'ubuntu@{ip}', cmd]
    try:
        r = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"

# Test the combined command on each instance
instances = {
    "Phase 1 Chunk 0": ("18.118.169.15", "ec2_deep_scrape", "deep_profiles.csv"),
    "Phase 1 Chunk 1": ("18.188.95.190", "ec2_phones_scraper", "scraped_chunk_1.csv"),
    "Phase 1 Chunk 2": ("18.191.145.108", "ec2_phones_scraper", "scraped_chunk_2.csv"),
    "IRS Finder 0": ("3.19.141.81", "ec2_find_websites", "found_chunk_0.csv"),
    "IRS Finder 1": ("18.191.24.204", "ec2_find_websites", "found_chunk_0.csv"),
    "IRS Finder 2": ("3.138.187.55", "ec2_find_websites", "found_chunk_0.csv"),
}

for name, (ip, proc, outfile) in instances.items():
    ckpt = outfile.replace('.csv', '_ckpt.csv')
    cmd = (
        f"running=$(ps aux | grep '{proc}' | grep -v grep | grep python | wc -l); "
        f"main=$(ls ~/{outfile} 1>/dev/null 2>/dev/null && wc -l ~/{outfile} | cut -d' ' -f1 || echo 0); "
        f"ckpt=$(ls ~/{ckpt} 1>/dev/null 2>/dev/null && wc -l ~/{ckpt} | cut -d' ' -f1 || echo 0); "
        f'echo "$running|$main|$ckpt"'
    )
    result = ssh(ip, cmd, timeout=10)
    print(f"{name}: {result}")
