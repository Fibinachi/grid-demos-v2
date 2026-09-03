"""Debug dashboard to test SSH calls"""
import streamlit as st
import subprocess, os, concurrent.futures

st.set_page_config(page_title="Debug SSH")
st.title("Debug SSH Test")

KEY = os.path.expanduser("~/.ssh/grantwizard-key.pem")

def ssh(ip, cmd, timeout=10):
    full = ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=5',
            '-i', KEY, f'ubuntu@{ip}', cmd]
    try:
        r = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except:
        return None

INSTANCES = {
    "Phase 1 Chunk 0": ("18.118.169.15", "ec2_deep_scrape", "deep_profiles.csv"),
    "Phase 1 Chunk 1": ("18.188.95.190", "ec2_phones_scraper", "scraped_chunk_1.csv"),
    "Phase 1 Chunk 2": ("18.191.145.108", "ec2_phones_scraper", "scraped_chunk_2.csv"),
    "IRS Finder 0": ("3.19.141.81", "ec2_find_websites", "found_chunk_0.csv"),
    "IRS Finder 1": ("18.191.24.204", "ec2_find_websites", "found_chunk_0.csv"),
    "IRS Finder 2": ("3.138.187.55", "ec2_find_websites", "found_chunk_0.csv"),
}

def check_instance(ip, proc, outfile):
    ckpt = outfile.replace('.csv', '_ckpt.csv')
    cmd = (
        f"running=$(ps aux | grep '{proc}' | grep -v grep | grep python | wc -l); "
        f"main=$(ls ~/{outfile} 1>/dev/null 2>/dev/null && wc -l ~/{outfile} | cut -d' ' -f1 || echo 0); "
        f"ckpt=$(ls ~/{ckpt} 1>/dev/null 2>/dev/null && wc -l ~/{ckpt} | cut -d' ' -f1 || echo 0); "
        f'echo "$running|$main|$ckpt"'
    )
    r = ssh(ip, cmd, timeout=10)
    if r and '|' in r:
        parts = r.split('|')
        return parts[0].strip(), parts[1].strip(), parts[2].strip()
    return '0', '0', '0'

if st.button("Test SSH"):
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {}
        for name, (ip, proc, outfile) in INSTANCES.items():
            futures[executor.submit(check_instance, ip, proc, outfile)] = name
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                running, main_out, ckpt_out = future.result()
                results[name] = (running, main_out, ckpt_out)
            except Exception as e:
                results[name] = (f'ERR:{e}', '0', '0')
    
    for name, (running, main_out, ckpt_out) in results.items():
        st.write(f"**{name}**: running={running} main={main_out} ckpt={ckpt_out}")
    
    total_running = sum(1 for r, _, _ in results.values() if r and r.strip() != "0")
    st.metric("Total Running", total_running)
