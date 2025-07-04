import meraki
import pandas as pd
import os
import time
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed


# === CONFIGURATION ===
# TODO: Move these to environment variables or a config file
# ⚠️ Replace these values with your own before running the script
API_KEY = 'YOUR_API_KEY_HERE'
ORG_ID = 'YOUR_ORG_ID_HERE'
DAYS_BACK = 7
MAX_THREADS = 10 

# This just saves the output to the folder where the script is ran
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wireless_clients.xlsx')

# Initialises to the dashboard and turns off logging
dashboard = meraki.DashboardAPI(API_KEY, suppress_logging=True)
since_time = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).isoformat()

# === FUNCTION TO FETCH CLIENTS FOR ONE NETWORK ===
def fetch_clients_for_network(net):
    results = []
    net_id = net['id']
    net_name = net['name']

# Skip networks that do not have wireless capabilities
    if 'wireless' not in net.get('productTypes', []):
        return results

    print(f"[+] Processing: {net_name}")
    try:
        clients = dashboard.networks.getNetworkClients(
            net_id,
            timespan=DAYS_BACK * 86400,
            perPage=1000,
            total_pages='all'
        )

        wireless_clients = 0
        for client in clients:
            if client.get('ssid'):  # Only wireless clients have SSID
                wireless_clients += 1
                results.append({
                    'Network Name': net_name,
                    'Client Name': client.get('description') or '',
                    'MAC Address': client.get('mac'),
                    'IP Address': client.get('ip') or 'Unavailable',
                    'Device/OS Type': client.get('os') or 'Unknown',
                    'SSID': client.get('ssid')
                })

        print(f"[✓] {net_name}: {wireless_clients} wireless clients found.")

    except Exception as e:
        print(f"[!] Error with {net_name}: {e}")

    return results

# === MAIN SCRIPT ===
if __name__ == "__main__":
    start_time = time.perf_counter()
    all_data = []

    print("Fetching network list...")
    networks = dashboard.organizations.getOrganizationNetworks(ORG_ID)
    print(f"Found {len(networks)} networks.")

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        future_to_network = {executor.submit(fetch_clients_for_network, net): net['name'] for net in networks}
        for future in as_completed(future_to_network):
            all_data.extend(future.result())

    # Export to Excel
    df = pd.DataFrame(all_data)
    df.to_excel(OUTPUT_FILE, index=False)

    print(f"\n✅ Done. {len(df)} wireless clients exported to:\n{OUTPUT_FILE}")

    elapsed = time.perf_counter() - start_time
    print(f"⏱️ Elapsed time: {elapsed:.2f} seconds")
