import argparse
import os
import sys
import requests
import ipaddress
import csv
import time
import random
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://api.meraki.com/api/v1"

def request_api(endpoint, api_key, retries=5, backoff_factor=1.5):
    url = f"{BASE_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    for attempt in range(retries):
        response = requests.get(url, headers=headers)
        if response.status_code == 429:
            wait = backoff_factor * (2 ** attempt) + random.uniform(0, 1)
            print(f"⏳ Rate limit hit. Retrying in {wait:.1f}s...")
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response.json()
    raise Exception(f"Too many 429 responses. Giving up on {endpoint}")

def get_all_orgs(api_key):
    print("🔍 Fetching accessible organizations...")
    return request_api("/organizations", api_key)

def get_devices_in_org(api_key, org_id):
    print(f"   ↳ Fetching networks and MX/vMX devices for org {org_id}...")
    devices = []
    nets = request_api(f"/organizations/{org_id}/networks", api_key)
    for net in nets:
        try:
            serials = request_api(f"/networks/{net['id']}/devices", api_key)
            for dev in serials:
                if dev.get("model", "").startswith(("MX", "vMX")):
                    dev["networkId"] = net["id"]
                    devices.append(dev)
        except:
            continue
    return devices

def get_device_uplinks_config(api_key, serial):
    return request_api(f"/devices/{serial}/appliance/uplinks/settings", api_key)

def get_org_uplinks_status(api_key, org_id):
    return request_api(f"/organizations/{org_id}/appliance/uplink/statuses", api_key)

def get_network_name(api_key, network_id):
    try:
        info = request_api(f"/networks/{network_id}", api_key)
        return info.get("name", "Unknown")
    except:
        return "Unknown"

def parse_and_collect(api_key, dev, uplink_config, status_list):
    serial = dev["serial"]
    network_name = get_network_name(api_key, dev["networkId"])
    matching = next((o for o in status_list if o["serial"] == serial), {})
    live_map = {u["interface"]: u for u in matching.get("uplinks", [])}
    rows = []

    for iface, uplink in uplink_config.get("interfaces", {}).items():
        live = live_map.get(iface, {})
        static_ip = uplink.get("svis", {}).get("ipv4", {}).get("address", "")
        cidr, mask = "N/A", "N/A"
        if "/" in static_ip:
            suffix = static_ip.split("/")[-1]
            cidr = f"/{suffix}"
            try:
                mask = str(ipaddress.IPv4Network(f"0.0.0.0/{suffix}").netmask)
            except:
                mask = "Invalid"

        rows.append({
            "Org ID": dev["organizationId"],
            "Network Name": network_name,
            "Serial": serial,
            "Interface": iface,
            "Enabled": uplink.get("enabled"),
            "VLAN Tagging": uplink.get("vlanTagging", {}).get("enabled"),
            "PPPoE": uplink.get("pppoe", {}).get("enabled"),
            "Status": live.get("status"),
            "IP Assigned By": live.get("ipAssignedBy"),
            "Public IP": live.get("publicIp"),
            "LAN IP": live.get("ip"),
            "Gateway IP": live.get("gateway"),
            "Subnet Mask": mask,
            "CIDR": cidr,
            "Primary DNS": live.get("primaryDns"),
            "Secondary DNS": live.get("secondaryDns"),
        })
    return rows

def main(api_key, csv_path, max_threads):
    start_time = time.time()
    all_rows = []
    orgs = get_all_orgs(api_key)

    for org in orgs:
        org_id = org["id"]
        devices = get_devices_in_org(api_key, org_id)
        if not devices:
            print(f"   ↳ No MX/vMX devices found in org {org_id}.")
            continue

        print(f"   ↳ Found {len(devices)} MX/vMX devices in org {org_id}.")
        status_list = get_org_uplinks_status(api_key, org_id)

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = {
                executor.submit(get_device_uplinks_config, api_key, dev["serial"]): dev
                for dev in devices
            }
            for future in tqdm(as_completed(futures), total=len(futures), desc=f"Processing org {org_id}", unit="device"):
                dev = futures[future]
                try:
                    uplink_config = future.result()
                    rows = parse_and_collect(api_key, {**dev, "organizationId": org_id}, uplink_config, status_list)
                    all_rows.extend(rows)
                except Exception as e:
                    tqdm.write(f"⚠️  Error with device {dev['serial']}: {e}")

    if all_rows:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"\n✅ CSV saved to: {csv_path}")
    else:
        print("❌ No data to write. Exiting.")

    elapsed = time.time() - start_time
    print(f"⏱️  Total elapsed time: {elapsed:.2f} seconds")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Report MX/vMX WAN config + status across all orgs")
    parser.add_argument("--api-key", help="Meraki API key or use MERAKI_DASHBOARD_API_KEY")
    parser.add_argument("--csv", help="CSV filename (default ./meraki_wan_report_ALL.csv)")
    parser.add_argument("--threads", type=int, default=5, help="Number of threads to use (default 5)")
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("MERAKI_DASHBOARD_API_KEY")
    if not api_key:
        print("❌ Missing API key. Use --api-key or set MERAKI_DASHBOARD_API_KEY.")
        sys.exit(1)

    csv_path = args.csv or "meraki_wan_report_ALL.csv"
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(os.getcwd(), csv_path)

    main(api_key, csv_path, args.threads)
