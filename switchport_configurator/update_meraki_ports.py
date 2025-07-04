import os
import time
import openpyxl
import requests
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

# ========== ARGUMENTS AND API KEY SETUP ==========
parser = argparse.ArgumentParser(description="Update Meraki switch ports in bulk.")
parser.add_argument(
    "--api-key",
    help="Meraki Dashboard API key (or use MERAKI_DASHBOARD_API_KEY environment variable)"
)
args = parser.parse_args()

# Use CLI arg or fallback to environment variable
MERAKI_API_KEY = args.api_key or os.getenv("MERAKI_DASHBOARD_API_KEY")

if not MERAKI_API_KEY:
    raise ValueError("❌ API key is missing. Use --api-key or set MERAKI_DASHBOARD_API_KEY as an environment variable.")
# ==================================================

# ==== CONFIGURATION ====
BASE_URL = 'https://api.meraki.com/api/v1'
MAX_THREADS = 10  # Adjust based on rate limit tolerance
EXCEL_FILENAME = 'port_descriptions.xlsx'
# ========================

# Start script timer
start_time = time.time()

# Create a session object for connection reuse
session = requests.Session()
session.headers.update({
    'X-Cisco-Meraki-API-Key': MERAKI_API_KEY,
    'Content-Type': 'application/json'
})

# Load Excel workbook from the same folder as the script
script_dir = os.path.dirname(os.path.abspath(__file__))
excel_path = os.path.join(script_dir, EXCEL_FILENAME)
wb = openpyxl.load_workbook(excel_path)
sheet = wb.active

# Group port updates by switch serial
switch_ports = defaultdict(list)

for row in sheet.iter_rows(min_row=2, values_only=True):
    switch_serial, port_number, description, port_type, vlan, voice_vlan, native_vlan, allowed_vlans = row
    switch_ports[switch_serial].append({
        'port': port_number,
        'description': description,
        'type': port_type,
        'vlan': vlan,
        'voice_vlan': voice_vlan,
        'native_vlan': native_vlan,
        'allowed_vlans': allowed_vlans
    })

# Normalize strings for comparison
def normalize(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value.lower() if value else None
    return value

# Update all ports for a given switch
def update_switch_ports(serial, ports):
    for port_data in ports:
        port_number = port_data['port']
        url = f'{BASE_URL}/devices/{serial}/switch/ports/{port_number}'

        # Get current config
        try:
            response = session.get(url)
            response.raise_for_status()
            current_config = response.json()
        except Exception as e:
            print(f"❌ Failed to fetch config for {serial} port {port_number}: {e}")
            continue

        payload = {}
        changed = False

        if normalize(port_data['description']) and normalize(current_config.get('name')) != normalize(port_data['description']):
            payload["name"] = port_data['description']
            changed = True

        port_type = normalize(port_data['type'])
        if port_type and normalize(current_config.get('type')) != port_type:
            payload["type"] = port_type
            changed = True

        if port_type == 'access':
            if port_data['vlan'] is not None and current_config.get('vlan') != int(port_data['vlan']):
                payload["vlan"] = int(port_data['vlan'])
                changed = True
            if port_data['voice_vlan'] is not None and current_config.get('voiceVlan') != int(port_data['voice_vlan']):
                payload["voiceVlan"] = int(port_data['voice_vlan'])
                changed = True

        elif port_type == 'trunk':
            if port_data['native_vlan'] is not None and current_config.get('nativeVlan') != int(port_data['native_vlan']):
                payload["nativeVlan"] = int(port_data['native_vlan'])
                changed = True
            if normalize(port_data['allowed_vlans']) and normalize(current_config.get('allowedVlans')) != normalize(port_data['allowed_vlans']):
                payload["allowedVlans"] = str(port_data['allowed_vlans'])
                changed = True

        if not changed:
            print(f"⏭️  Skipping port {port_number} on {serial} (no changes).")
            continue

        # Send update to Meraki
        try:
            put_response = session.put(url, json=payload)
            if put_response.status_code == 200:
                print(f"✅ Updated port {port_number} on {serial}")
            else:
                print(f"❌ Failed port {port_number} on {serial}: {put_response.status_code} {put_response.text}")
        except Exception as e:
            print(f"⚠️  Error updating port {port_number} on {serial}: {e}")

# Run switch updates in parallel (one thread per switch)
with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
    for serial, ports in switch_ports.items():
        executor.submit(update_switch_ports, serial, ports)

# End and report script duration
elapsed = time.time() - start_time
minutes, seconds = divmod(elapsed, 60)
print(f"\n⏱️ Script completed in {int(minutes)} min {int(seconds)} sec.")

input("\nPress Enter to exit...")
